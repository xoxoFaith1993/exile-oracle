"""Live trade-site price check for the overlay, the way Exiled Exchange 2 does it (the author's decision, 2026-11-20).

Rules (PLAN.md "Price-check overlay"):
  - only when the player copies an item, ONE search + ONE fetch of the 10 cheapest listings;
  - GGG's X-Rate-Limit headers are read after every call and obeyed; if a wait would be long we skip and say so;
  - no login, no background or bulk searches; results are cached for 5 minutes;
  - the stat list (data/stats) is fetched at most once a day.
Our own code: Exiled Exchange 2 was only read to learn the request shapes (its AI policy asks for no AI code)."""

import json
import math
import os
import re
import statistics
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config

SITE = 'https://www.pathofexile.com'
STATS_FILE = os.path.join(config.DATA_DIR, 'trade-stats.json')
MAX_WAIT = 4.0          # seconds we are willing to wait for the rate limit before giving up on this copy
CACHE_S = 300
ROLL_SLACK = 0.10       # default: search for at least 90% of each roll (overlay setting search_range_pct)


def _slack():
    try:
        return max(0.0, min(0.5, float(config.settings().get('search_range_pct', 10)) / 100))
    except (TypeError, ValueError):
        return ROLL_SLACK
LOCAL_CLASSES = ('Bows', 'Crossbows', 'Wands', 'Staves', 'Quarterstaves', 'Sceptres', 'Spears', 'Flails',
                 'One Hand Maces', 'Two Hand Maces', 'One Hand Swords', 'Two Hand Swords', 'One Hand Axes',
                 'Two Hand Axes', 'Daggers', 'Claws', 'Talismans', 'Body Armours', 'Helmets', 'Gloves', 'Boots',
                 'Shields', 'Bucklers', 'Foci', 'Quivers')
RESISTS = {'Fire': 'fire', 'Cold': 'cold', 'Lightning': 'lightning', 'Chaos': 'chaos'}

_lock = threading.Lock()
_cache = {}
_limits = {'search': {'rules': [(1, 5)], 'hits': [], 'until': 0}, 'fetch': {'rules': [(1, 5)], 'hits': [], 'until': 0}}


# ---------------- stats list ----------------

_index = {'t': 0, 'by': None, 'pseudo': None}


def _norm(t):
    return re.sub(r'\+#', '#', t).strip()


def _stats():
    if _index['by'] and time.time() - _index['t'] < 86400:
        return _index
    fresh = os.path.exists(STATS_FILE) and time.time() - os.path.getmtime(STATS_FILE) < 86400
    if not fresh:
        try:
            body = _get('/api/trade2/data/stats', limiter=None)
            os.makedirs(config.DATA_DIR, exist_ok=True)
            with open(STATS_FILE, 'wb') as f:
                f.write(body)
        except Exception:
            if not os.path.exists(STATS_FILE):
                raise
    with open(STATS_FILE, encoding='utf-8') as f:
        d = json.load(f)
    by = {}
    for g in d['result']:
        for e in g['entries']:
            if e.get('option'):   # stats with a pick-list ("Allocates #") need an option id; skipped for now
                continue
            by.setdefault(g['id'], {}).setdefault(_norm(e['text']), []).append(e['id'])
    pseudo = {e['text']: e['id'] for g in d['result'] if g['id'] == 'pseudo' for e in g['entries']}
    _index.update(t=time.time(), by=by, pseudo=pseudo)
    return _index


def match(mod, cls):
    """A mod line -> (trade stat ids, value, label) or None."""
    kind = {'explicit': 'explicit', 'implicit': 'implicit', 'rune': 'rune', 'enchant': 'enchant'}.get(mod['kind'])
    if not kind or not mod['values']:
        return None
    by = _stats()['by'].get(kind, {})
    tmpl = _norm(re.sub(r'[+-]?\d+(?:\.\d+)?', '#', mod['text']))
    vals = mod['values']
    value = sum(vals) / len(vals) if tmpl.startswith('Adds # to #') else vals[0]
    tries = [(tmpl, 1)]
    for a, b in (('reduced', 'increased'), ('less', 'more'), ('increased', 'reduced')):
        if f' {a} ' in tmpl:
            tries.append((tmpl.replace(f' {a} ', f' {b} '), -1))
    for t, sign in tries:
        local = by.get(t + ' (Local)')
        ids = (local if local and cls in LOCAL_CLASSES else None) or by.get(t) or local
        if ids:
            return ids, value * sign, mod['text']
    return None


# ---------------- rate limits ----------------

def _wait_for(name):
    """Seconds until a call is allowed (0 = now)."""
    lim = _limits[name]
    now = time.time()
    wait = max(0, lim['until'] - now)
    for mx, win in lim['rules']:
        recent = [h for h in lim['hits'] if now - h < win]
        if len(recent) >= mx:
            wait = max(wait, recent[-mx] + win - now + 0.5)
    return wait


def _note(name, headers, status):
    lim = _limits[name]
    lim['hits'].append(time.time())
    lim['hits'] = lim['hits'][-200:]
    rules = (headers.get('X-Rate-Limit-Rules') or '').split(',')
    new = []
    for r in filter(None, (x.strip() for x in rules)):
        spec, state = headers.get(f'X-Rate-Limit-{r}') or '', headers.get(f'X-Rate-Limit-{r}-State') or ''
        for s, st in zip(spec.split(','), state.split(',')):
            try:
                mx, win, _pen = (int(x) for x in s.split(':'))
                hits, _w, restricted = (int(x) for x in st.split(':'))
            except ValueError:
                continue
            new.append((max(1, mx - 1), win + 1))   # keep one request spare, add a second for clock drift
            if restricted:
                lim['until'] = max(lim['until'], time.time() + restricted)
            # the server may have counted more hits than we did (other tools on this PC): trust its count
            have = len([h for h in lim['hits'] if time.time() - h < win])
            lim['hits'].extend([time.time()] * max(0, hits - have))
    if new:
        lim['rules'] = new
    if status == 429:
        try:
            ra = float(headers.get('Retry-After') or 60)
        except ValueError:
            ra = 60
        lim['until'] = max(lim['until'], time.time() + ra)


def enabled():
    return bool(config.settings().get('live_trade', False))


def _req(path, data=None, limiter='search', max_wait=MAX_WAIT):
    if not enabled():   # switched off: never contact the trade site (stat/currency lists fall back to saved copies)
        raise RuntimeError('Live trade prices are off')
    if limiter:
        w = _wait_for(limiter)
        if w > max_wait:
            raise RuntimeError(f'Trade site limit reached: try again in {math.ceil(w)} s')
        if w:
            time.sleep(w)
    req = urllib.request.Request(SITE + path, data=json.dumps(data).encode() if data is not None else None,
                                 method='POST' if data is not None else 'GET',
                                 headers={'User-Agent': config.user_agent(), 'Accept': 'application/json',
                                          'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            if limiter:
                _note(limiter, r.headers, r.status)
            return r.read()
    except urllib.error.HTTPError as e:
        if limiter:
            _note(limiter, e.headers, e.code)
        body = e.read()[:400].decode('utf-8', 'replace')
        try:
            msg = json.loads(body)['error']['message']
        except Exception:
            msg = body[:120]
        if e.code == 429:
            raise RuntimeError('Trade site limit reached: wait a minute') from None
        raise RuntimeError(f'Trade site said {e.code}: {msg}') from None


def _get(path, limiter='fetch', max_wait=MAX_WAIT):
    return _req(path, None, limiter, max_wait)


# ---------------- query ----------------

def _fmin(v, whole=None):
    """Lowest value to search for: 90% of the roll. Small whole numbers (+3 to Level of ...) stay exact."""
    if v <= 0:
        return None
    whole = float(v).is_integer() if whole is None else whole
    if whole:
        return int(v) if v <= 5 else math.floor(v * (1 - _slack()))
    return round(v * (1 - _slack()), 2)


def _n(x):
    return str(int(x)) if float(x).is_integer() else f'{x:.2f}'.rstrip('0').rstrip('.')


def _min_for(rar, m, value, text):
    if rar == 'UNIQUE':   # only rolled lines matter; fixed lines are the same on every copy
        rr = [x for x in m['ranges'] if x]
        if not rr or rr[0][1] <= rr[0][0]:
            return None
        lo, hi = (sum(x[0] for x in rr) / len(rr), sum(x[1] for x in rr) / len(rr))
        mn = value - (hi - lo) * _slack()
        return math.floor(mn) if all(float(v).is_integer() for v in m['values']) else round(mn, 2)
    return _fmin(value, all(float(v).is_integer() for v in m['values']) or text.startswith('Adds'))


def default_filters(it):
    """The search the overlay starts with, as rows the player can tick, untick and edit:
    {'base', 'stats': [{key, text, ids, value, min, on, kind, tier}], 'mode', 'status', 'ilvl', 'sockets', ...}
    Returns None for items with no trade search."""
    rar = it.get('rarity')
    if rar not in ('RARE', 'UNIQUE', 'MAGIC', 'NORMAL', 'GEM'):
        return None
    f = {'rarity': rar, 'status': config.settings().get('listing') or 'securable', 'stats': [], 'mode': 'all',
         'base': it.get('name') if rar in ('UNIQUE', 'GEM') else it.get('base'),
         'name': it.get('name') if rar == 'UNIQUE' else None,
         'type': it.get('base') if rar != 'GEM' else it.get('name'),
         'category': it.get('cls'),
         'corrupted': bool(it.get('corrupted')),
         # white/magic bases: item level is what crafters pay for, so it's matched by default (exactly below 60,
         # where only low-level bases compare; "at least yours" from 60)
         'ilvl': {'value': it.get('ilvl'), 'on': rar in ('MAGIC', 'NORMAL'),
                  'max': it.get('ilvl') if rar in ('MAGIC', 'NORMAL') and (it.get('ilvl') or 0) < 60 else None}
         if it.get('ilvl') and rar in ('RARE', 'MAGIC', 'NORMAL') else None,
         'sockets': {'value': it['rune_sockets'], 'on': True} if it.get('rune_sockets') else None,
         'gem_level': {'value': it['gem_level'], 'on': True} if it.get('gem_level') else None,
         'waystone_tier': it.get('waystone_tier')}
    if rar not in ('RARE', 'MAGIC', 'UNIQUE') or it.get('unidentified'):
        return f
    try:
        _stats()
    except Exception:
        return f
    res, n = {}, 0
    for m in it.get('mods') or []:
        if m['kind'] not in ('explicit', 'implicit', 'rune', 'enchant'):
            continue
        try:
            r = match(m, it.get('cls'))
        except Exception:
            r = None
        if not r:
            continue
        ids, value, text = r
        n += 1
        if m['kind'] == 'explicit' and rar != 'UNIQUE':
            rm = re.match(r'^[+-]?[\d.]+% to (Fire|Cold|Lightning|Chaos) Resistance$', m['text'])
            am = re.match(r'^[+-]?[\d.]+% to all Elemental Resistances$', m['text'])
            if rm or am:   # rares: one total-resistance row instead, like the trade site's pseudo stats
                key = 'chaos' if rm and rm.group(1) == 'Chaos' else 'ele'
                res[key] = res.get(key, 0) + (value * 3 if am else value)
                res[key + '_n'] = res.get(key + '_n', 0) + (3 if am else 1)
                continue
        mn = _min_for(rar, m, value, text) if value > 0 else None
        mx = math.ceil(value * (1 - _slack())) if value < 0 and rar != 'UNIQUE' else None   # "reduced" mods
        if rar == 'UNIQUE' and mn is None:
            continue   # fixed unique lines are on every copy
        on = m['kind'] == 'explicit' and (mn is not None or mx is not None)
        f['stats'].append({'key': f's{n}', 'text': text, 'ids': ids, 'value': value, 'min': mn, 'max': mx, 'on': on,
                           'kind': 'fractured' if m.get('fractured') else 'desecrated' if m.get('desecrated')
                           else m['kind'], 'tier': m.get('tier')})
    pseudo = _index.get('pseudo') or {}
    for key, txt, label in (('chaos', '+#% total to Chaos Resistance', '% total to Chaos Resistance'),
                            ('ele', '+#% total Elemental Resistance', '% total Elemental Resistance')):
        if res.get(key) and pseudo.get(txt):
            f['stats'].insert(0, {'key': 'p' + key, 'text': f"{_n(res[key])}{label}", 'ids': [pseudo[txt]],
                                  'value': res[key], 'min': _fmin(res[key]), 'on': True, 'kind': 'pseudo',
                                  'times': res[key + '_n'], 'tier': None})
    on = [s for s in f['stats'] if s['on']]
    if rar != 'UNIQUE' and len(on) >= 4:
        f['mode'] = 'count'   # any n-1 of them: a perfect copy is rare, near-copies set the price
    return f


def build_query(it, league=None, f=None):
    """Trade-site query from the filter rows (default_filters, or the player's edited copy).
    Returns {'query', 'labels'} or None."""
    f = f or default_filters(it)
    if not f:
        return None
    rar = f['rarity']
    q = {'status': {'option': f.get('status') or 'securable'}, 'stats': [], 'filters': {}}
    labels = [f.get('base') or '']
    if f.get('name'):
        q['name'] = f['name']
    if f.get('type'):
        q['type'] = f['type']
    if rar in ('RARE', 'MAGIC', 'NORMAL'):
        q['filters']['type_filters'] = {'filters': {'rarity': {'option': 'nonunique'}}}
    if (f.get('ilvl') or {}).get('on') and f['ilvl'].get('value'):
        iv = {'min': f['ilvl']['value']}
        if f['ilvl'].get('max'):
            iv['max'] = f['ilvl']['max']
        q['filters'].setdefault('type_filters', {'filters': {}})['filters']['ilvl'] = iv
        labels.append(f"item level {f['ilvl']['value']}" + ('' if iv.get('max') else '+'))
    main, groups = [], []
    for s in f.get('stats') or []:
        if not s.get('on'):
            continue
        val = {}
        if s.get('min') not in (None, ''):
            val['min'] = float(s['min'])
        if s.get('max') not in (None, ''):
            val['max'] = float(s['max'])
        if len(s['ids']) > 1:   # same text on a local and a global stat: either may match
            groups.append({'type': 'count', 'value': {'min': 1}, 'filters': [{'id': i, 'value': val} for i in s['ids']]})
        else:
            main.append({'id': s['ids'][0], 'value': val})
        short = re.sub(r'[+-]?\d+(?:\.\d+)?', '#', s['text'])
        labels.append(short.replace('#', _n(val['min']) + '+', 1) if 'min' in val else short)
    if main:
        if f.get('mode') == 'count' and len(main) >= 3:
            q['stats'].append({'type': 'count', 'value': {'min': len(main) - 1}, 'filters': main})
            labels.append(f'(any {len(main) - 1} of these {len(main)})')
        else:
            q['stats'].append({'type': 'and', 'filters': main})
    q['stats'].extend(groups)
    if not q['stats']:
        q['stats'] = [{'type': 'and', 'filters': []}]
    misc = {}
    if not f.get('corrupted') and rar != 'GEM':
        misc['corrupted'] = {'option': 'false'}
    if (f.get('gem_level') or {}).get('on'):
        misc['gem_level'] = {'min': f['gem_level']['value']}
        labels.append(f"gem level {f['gem_level']['value']}+")
    if misc:
        q['filters']['misc_filters'] = {'filters': misc}
    if (f.get('sockets') or {}).get('on'):
        q['filters']['equipment_filters'] = {'filters': {'rune_sockets': {'min': f['sockets']['value']}}}
        labels.append(f"{f['sockets']['value']}+ rune sockets")
    if f.get('waystone_tier'):
        q['filters']['map_filters'] = {'filters': {'map_tier': {'min': f['waystone_tier'], 'max': f['waystone_tier']}}}
    return {'query': {'query': q, 'sort': {'price': 'asc'}}, 'labels': labels}


def search_url(league, built):
    if not built:
        return None
    return (f'{SITE}/trade2/search/poe2/{urllib.parse.quote(league)}?q='
            + urllib.parse.quote(json.dumps(built['query'], separators=(',', ':'))))


# ---------------- price ----------------

STATIC_FILE = os.path.join(config.DATA_DIR, 'trade-static.json')
_static = {'t': 0, 'names': {}, 'images': {}}


def currency_names():
    """Trade-site currency ids ('regal', 'aug', ...) -> item names, from data/static (fetched at most daily)."""
    if _static['names'] and time.time() - _static['t'] < 86400:
        return _static['names']
    if not (os.path.exists(STATIC_FILE) and time.time() - os.path.getmtime(STATIC_FILE) < 86400):
        try:
            body = _get('/api/trade2/data/static', limiter=None)
            os.makedirs(config.DATA_DIR, exist_ok=True)
            with open(STATIC_FILE, 'wb') as f:
                f.write(body)
        except Exception:
            if not os.path.exists(STATIC_FILE):
                return {}
    with open(STATIC_FILE, encoding='utf-8') as f:
        d = json.load(f)
    _static.update(t=time.time(), names={e['id']: e['text'] for g in d['result'] for e in g['entries'] if e.get('text')},
                   images={e['id']: 'https://web.poecdn.com' + e['image'] for g in d['result'] for e in g['entries']
                           if e.get('image', '').startswith('/')})
    return _static['names']


def currency_icon(cid):
    currency_names()
    return _static['images'].get(cid)


def _to_div(amount, cur, rt, value_of=None):
    """Listing price -> divines. value_of(name) gives poe.ninja's divine price for other currencies."""
    ex, ch = rt.get('ex_per_div'), rt.get('chaos_per_div')
    if cur == 'divine':
        return amount
    if cur == 'exalted' and ex:
        return amount / ex
    if cur == 'chaos' and ch:
        return amount / ch
    name = currency_names().get(cur)
    v = value_of(name) if value_of and name else None
    return amount * v if v else None


def _listing(r, rt, value_of):
    p, it = r['listing']['price'], r.get('item') or {}
    acc = r['listing'].get('account') or {}
    return {'amount': p.get('amount'), 'currency': p.get('currency'),
            'div': _to_div(p.get('amount') or 0, p.get('currency'), rt, value_of),
            'name': currency_names().get(p.get('currency')), 'icon': currency_icon(p.get('currency')),
            'ilvl': it.get('ilvl'), 'gem_level': next((int(re.sub(r'\D', '', str(pr['values'][0][0])) or 0)
                                                       for pr in it.get('properties') or [] if pr.get('name') == 'Level'
                                                       and pr.get('values')), None),
            'listed': r['listing'].get('indexed'), 'corrupted': bool(it.get('corrupted')),
            'online': acc.get('online') is not None, 'afk': (acc.get('online') or {}).get('status') == 'afk'}


def price(it, league, rt, value_of=None, f=None):
    built = build_query(it, league, f)
    if not built:
        return {'state': 'off', 'note': 'This kind of item has no trade search.'}
    key = json.dumps([league, built['query']], sort_keys=True)
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < CACHE_S:
            return dict(hit[1], cached=True)
    try:
        with _lock:   # one search at a time across copies
            s = json.loads(_req(f'/api/trade2/search/poe2/{urllib.parse.quote(league)}', built['query'], 'search'))
            ids = (s.get('result') or [])[:10]
            listings = []
            if ids:
                f = json.loads(_get(f"/api/trade2/fetch/{','.join(ids)}?query={s['id']}", 'fetch'))
                listings = [r for r in f.get('result') or [] if r and r.get('listing', {}).get('price')]
    except Exception as e:
        return {'state': 'error', 'error': str(e), 'filters': built['labels']}
    prices = [_listing(r, rt, value_of) for r in listings]
    divs = [p['div'] for p in prices if p['div'] is not None]
    out = {'state': 'done', 'total': s.get('total', 0), 'prices': prices, 'filters': built['labels'],
           'low_div': min(divs) if divs else None, 'median_div': statistics.median(divs) if divs else None,
           'inexact': bool(s.get('inexact')), 'searched': time.time(),
           'item_icon': next((r['item'].get('icon') for r in listings if r.get('item', {}).get('icon')), None)}
    with _lock:
        _cache[key] = (time.time(), out)
    return out
