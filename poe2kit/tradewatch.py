"""Wanted items on the Wishlist: saved trade-site searches the player checks by hand (the author, 2026-11-21: "if there's a
specific item that's on the market, you can paste the link ... this will help people get items that they need,
like an expensive staff with specific stats").

Input: a trade-site link (www.pathofexile.com/trade2/search/poe2/<league>/<id>) or the item itself (Ctrl+C in game).
A link's search id is the search itself, gzip-compressed and base64-encoded, so it is read locally with no request.
Links with ?q=<search> (the overlay's "Open on trade") work too.

Rules (the same as the overlay's live prices, poe2kit/trade.py; the same Settings switch `live_trade`):
  - the trade site is only contacted when the player presses Check now (or asks the Oracle to check);
  - one search + one fetch per check (a second fetch only to confirm listings that left the results);
  - GGG's X-Rate-Limit headers are obeyed; the same search can't be checked again within a minute;
  - nothing runs in the background. For instant news of new listings: GGG's own live search (Open live search).

Sold or taken down: every listing has an id. Each check compares with the last one; a listing that left the
results is fetched by id, and if the trade site no longer has it, it's "gone (sold or taken down)". The trade site
doesn't say which. A pinned listing is fetched on every check: still there, re-priced, or gone.

Open this listing: the trade site has no address for one listing, so a search is built from that listing's exact
stats and price (the author, 2026-11-21: "I think it can be based on stats") and run once when the player presses the
button; the link the trade site returns is opened (it shows that listing, or the few identical ones).
No seller account names are stored; the trade site's own whisper text (with the seller's character name) is kept
only for the listings currently shown, so the player can copy it into the game."""

import base64
import copy
import gzip
import json
import re
import statistics
import time
import urllib.parse
import uuid

from . import db

KEY = 'wishlist:trade'
MAX = 30
COOLDOWN = 60          # seconds between checks of the same search
HISTORY = 200
SITE = 'https://www.pathofexile.com'


def _load(con):
    try:
        return [x for x in json.loads(db.kv_get(con, KEY) or '[]') if isinstance(x, dict) and x.get('id')]
    except ValueError:
        return []


def _save(con, w):
    db.kv_set(con, KEY, json.dumps(w[:MAX]))
    con.commit()


def decode_id(sid):
    """A trade search id -> the search (dict), or None for ids that aren't a compressed search."""
    try:
        raw = gzip.decompress(base64.urlsafe_b64decode(sid + '=' * (-len(sid) % 4)))
        q = json.loads(raw)
        return q if isinstance(q, dict) else None
    except Exception:
        return None


def encode_query(q):
    """The search -> an id the trade site understands (the same format, so links open the same search)."""
    raw = json.dumps(q, separators=(',', ':')).encode()
    return base64.urlsafe_b64encode(gzip.compress(raw, mtime=0)).decode().rstrip('=')


def _stat_texts():
    try:
        from . import trade
        by = trade._stats()['by']
        return {i: t for kind in by.values() for t, ids in kind.items() for i in ids}
    except Exception:
        return {}


def describe(q):
    """Short words for a search: the item and its stat filters."""
    texts = _stat_texts()
    head = ' '.join(x for x in (q.get('name'), q.get('type')) if x)
    cat = ((((q.get('filters') or {}).get('type_filters') or {}).get('filters') or {}).get('category') or {}).get('option')
    if not head and cat:
        head = cat.replace('.', ' ').replace('weapon', '').strip().title() or 'Any item'
    labels = [head or 'Any item']
    for g in q.get('stats') or []:
        fl = [f for f in g.get('filters') or [] if not f.get('disabled')]
        for f in fl:
            t = texts.get(f.get('id'), f.get('id', '?'))
            v = f.get('value') or {}
            if 'min' in v:
                t = t.replace('#', f"{v['min']:g}+", 1)
            elif 'max' in v:
                t = t.replace('#', f"{v['max']:g} or less", 1)
            labels.append(re.sub(r'\s*\(Local\)$', '', t))
        if g.get('type') == 'count' and fl:
            labels.append(f"(any {((g.get('value') or {}).get('min') or 1):g} of the {len(fl)} above)")
    return labels


def parse_input(text, league):
    """Pasted text -> {'query', 'league', 'labels', 'name'} or {'error'}."""
    text = (text or '').strip()
    if not text:
        return {'error': 'Paste a trade-site link or the item (Ctrl+C in game).'}
    m = re.search(r'pathofexile\.com/trade2/(?:search|exchange)/poe2/([^/?#\s]+)(?:/([A-Za-z0-9_-]+))?', text)
    if m:
        lg = urllib.parse.unquote(m.group(1))
        if '/exchange/' in m.group(0):
            return {'error': 'That is a bulk-exchange link. For currency, add it by name above (it has a market price).'}
        q = None
        if m.group(2) and m.group(2) != 'live':
            q = decode_id(m.group(2))
        if q is None:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(text.split()[0]).query)
            if qs.get('q'):
                try:
                    q = json.loads(qs['q'][0]).get('query')
                except (ValueError, AttributeError):
                    q = None
        if not q:
            return {'error': "That link's search can't be read. Paste the item itself (Ctrl+C in game) instead, or "
                             'open the link, change any filter so the address changes, and paste the new link.'}
        return {'query': q, 'league': lg, 'labels': describe(q), 'name': q.get('name') or q.get('type')}
    from . import itemtext, trade
    it = itemtext.parse(text)
    if not it.get('rarity'):
        return {'error': 'That is neither a trade-site link nor an item copied in game (Ctrl+C).'}
    built = trade.build_query(it, league)
    if not built:
        return {'error': 'This kind of item has no trade search.'}
    return {'query': built['query']['query'], 'league': league, 'labels': built['labels'],
            'name': it.get('name') if it.get('rarity') == 'UNIQUE' else it.get('base') or it.get('name')}


def add(con, text, name=None, target=None, unit='div'):
    from . import ninja, wishlist
    league = ninja.current_league(con)
    p = parse_input(text, league)
    if p.get('error'):
        return {'ok': False, 'error': p['error']}
    tdiv = None
    if target not in (None, '') and not (isinstance(target, str) and not target.strip()):
        try:
            tv = float(target)
            if tv <= 0:
                raise ValueError
            tdiv = wishlist._to_div(con, tv, unit)
        except (TypeError, ValueError) as e:
            return {'ok': False, 'error': str(e) if 'price yet' in str(e) else 'The target must be a price above 0.'}
    w = _load(con)
    if len(w) >= MAX:
        return {'ok': False, 'error': f'Up to {MAX} wanted items: remove one first.'}
    e = {'id': uuid.uuid4().hex[:10], 'name': (name or '').strip()[:80] or p.get('name') or 'Wanted item',
         'query': p['query'], 'league': p['league'], 'labels': p['labels'][:14], 'added': time.time(),
         'target_div': tdiv, 'target_value': float(target) if tdiv else None, 'unit': unit if tdiv else None,
         'pinned': None, 'last': None, 'history': []}
    w.insert(0, e)
    _save(con, w)
    other = p['league'] != league
    return {'ok': True, 'id': e['id'], 'name': e['name'],
            'note': f"This link is for {p['league']}, not {league}: it's checked in {p['league']}." if other else None}


def remove(con, wid):
    w = _load(con)
    left = [x for x in w if x['id'] != wid]
    _save(con, left)
    return {'ok': len(left) < len(w)}


def pin(con, wid, listing_id):
    w = _load(con)
    for e in w:
        if e['id'] == wid:
            e['pinned'] = {'id': listing_id, 'since': time.time()} if listing_id else None
            if listing_id and e.get('last'):   # remember its price now, to show re-pricing later
                l = next((x for x in e['last'].get('listings') or [] if x['id'] == listing_id), None)
                if l:
                    e['pinned'].update(first=l, last=l)
            _save(con, w)
            return {'ok': True}
    return {'ok': False, 'error': 'Not found'}


def _value_of(con, league):
    from . import cost
    idx = cost._latest_index(con, league)

    def value_of(name):
        c = [x for x in idx.get(name.lower(), []) if not x['category'].startswith('Unique')]
        return c[0]['value'] if c else None
    return value_of


def _row(r, rt, value_of):
    from . import trade
    l = trade._listing(r, rt, value_of)
    it = r.get('item') or {}
    clean = lambda m: re.sub(r'\[([^|\]]+\|)?([^\]]+)\]', r'\2', m if isinstance(m, str) else str(m.get('text') or m.get('description') or ''))
    mk = [[k, clean(m)] for k, key in (('implicit', 'implicitMods'), ('explicit', 'explicitMods'),
                                       ('explicit', 'desecratedMods'), ('explicit', 'fracturedMods'))
          for m in it.get(key) or [] if m]
    mods = (it.get('implicitMods') or []) + (it.get('explicitMods') or []) + (it.get('desecratedMods') or []) + \
        (it.get('fracturedMods') or [])
    lst = r.get('listing') or {}
    return {'mk': mk[:20], 'whisper': (lst.get('whisper') or '')[:300], 'fee': lst.get('fee'),
            'cls': it.get('typeLine'), 'id': r.get('id'), 'amount': l['amount'], 'currency': l['currency'], 'cur_name': l['name'], 'cur_icon': l['icon'],
            'div': l['div'], 'listed': l['listed'], 'online': l['online'], 'afk': l['afk'], 'ilvl': l['ilvl'],
            'corrupted': l['corrupted'], 'icon': it.get('icon'), 'item_name': ' '.join(x for x in (it.get('name'), it.get('typeLine')) if x),
            'mods': [re.sub(r'\[([^|\]]+\|)?([^\]]+)\]', r'\2', m if isinstance(m, str) else str(m.get('text') or m.get('description') or ''))
                     for m in mods if m][:12]}


def check(con, wid):
    """One manual check: search, fetch the cheapest 10 (+ any that left the results, + the pinned one)."""
    from . import money, trade
    w = _load(con)
    e = next((x for x in w if x['id'] == wid), None)
    if not e:
        return {'ok': False, 'error': 'Not found'}
    if not trade.enabled():
        return {'ok': False, 'off': True, 'error': 'Trade-site checks are off (the same switch as the overlay\'s live prices).'}
    last = e.get('last') or {}
    if time.time() - (last.get('ts') or 0) < COOLDOWN:
        return {'ok': False, 'error': f"Checked {int(time.time() - last['ts'])} s ago: wait a minute between checks "
                                      '(the trade site limits how often anyone can search).'}
    league = e['league']
    rt = money.rates(con, league) or {}
    if not rt.get('ex_per_div'):
        from . import ninja
        rt = money.rates(con, ninja.current_league(con))
    value_of = _value_of(con, league)
    lq = urllib.parse.quote(league)
    try:
        s = json.loads(trade._req(f'/api/trade2/search/poe2/{lq}', {'query': e['query'], 'sort': {'price': 'asc'}}, 'search'))
        ids = s.get('result') or []
        total = s.get('total', len(ids))
        top = ids[:10]
        got = {}
        if top:
            f = json.loads(trade._get(f"/api/trade2/fetch/{','.join(top)}?query={s['id']}", 'fetch'))
            for r in f.get('result') or []:
                if r and r.get('listing', {}).get('price'):
                    got[r['id']] = r
        # listings from last time (and the pinned one) that aren't in the cheapest 10 now
        prev = [x['id'] for x in last.get('listings') or []]
        pid = (e.get('pinned') or {}).get('id')
        complete = total <= len(ids)   # the search returned every match: an id missing from it is gone for sure
        ask = [i for i in prev + ([pid] if pid else []) if i and i not in top and (i not in ids or i == pid)]
        ask = list(dict.fromkeys(ask))
        gone_ids = set()
        still = {}
        if ask:
            sure_gone = [i for i in ask if complete and i not in ids and i != pid]
            gone_ids.update(sure_gone)
            need = [i for i in ask if i not in sure_gone][:10]
            if need:
                f2 = json.loads(trade._get(f"/api/trade2/fetch/{','.join(need)}?query={s['id']}", 'fetch'))
                found = {r['id']: r for r in f2.get('result') or [] if r}
                for i in need:
                    if i in found and found[i].get('listing', {}).get('price'):
                        still[i] = found[i]
                    else:
                        gone_ids.add(i)
    except Exception as ex:
        return {'ok': False, 'error': str(ex)}
    listings = [_row(got[i], rt, value_of) for i in top if i in got]
    old = {x['id']: x for x in last.get('listings') or []}
    for l in listings:
        o = old.get(l['id'])
        l['new'] = bool(last) and o is None
        if o and (o['amount'], o['currency']) != (l['amount'], l['currency']):
            l['was'] = {'amount': o['amount'], 'currency': o['currency'], 'div': o.get('div')}
    gone = [dict(old[i], gone_at=time.time()) for i in gone_ids if i in old]
    seen = {g['id'] for g in gone}
    earlier = [g for g in last.get('gone') or [] if g.get('id') not in seen]
    divs = [l['div'] for l in listings if l['div'] is not None]
    now = time.time()
    e['last'] = {'ts': now, 'total': total, 'listings': listings, 'search_id': s['id'],
                 'low_div': min(divs) if divs else None, 'median_div': statistics.median(divs) if divs else None,
                 'gone': (gone + [g for g in earlier if now - g.get('gone_at', 0) < 7 * 86400])[:20],
                 'prev_total': last.get('total')}
    if pid:
        pr = got.get(pid) or still.get(pid)
        if pr:
            row = _row(pr, rt, value_of)
            e['pinned'].update(state='listed', last=row)
            e['pinned'].setdefault('first', row)
        elif pid in gone_ids:
            e['pinned'].update(state='gone', gone_at=now)
    e['history'] = (e.get('history') or [])[-(HISTORY - 1):] + [{'ts': now, 'total': total, 'low_div': e['last']['low_div'],
                                                                  'median_div': e['last']['median_div']}]
    _save(con, w)
    return dict(view_one(e, rt), ok=True)


def listing_query(e, l):
    """A search only this listing (or identical copies) matches: the saved search + its exact stats + its price."""
    from . import trade
    q = copy.deepcopy(e['query'])
    exact, groups = [], []
    for kind, text in l.get('mk') or []:
        vals = [float(x) for x in re.findall(r'[+-]?\d+(?:\.\d+)?', text)]
        if not vals:   # lines without numbers ("Legacy of Basalt"): match the exact text
            try:
                ids = trade._stats()['by'].get(kind, {}).get(trade._norm(text))
            except Exception:
                ids = None
            if ids and len(ids) == 1:
                exact.append({'id': ids[0], 'value': {}})
            elif ids:
                groups.append({'type': 'count', 'value': {'min': 1}, 'filters': [{'id': i, 'value': {}} for i in ids]})
            continue
        try:
            m = trade.match({'kind': kind, 'values': vals, 'text': text}, None)
        except Exception:
            m = None
        if not m:
            continue
        ids, value, _ = m
        v = round(value, 2)
        val = {'min': v, 'max': v}
        if len(ids) > 1:   # local and global versions of the same text: either may be the one
            groups.append({'type': 'count', 'value': {'min': 1}, 'filters': [{'id': i, 'value': val} for i in ids]})
        else:
            exact.append({'id': ids[0], 'value': val})
    q['stats'] = [g for g in q.get('stats') or [] if g.get('filters')] + ([{'type': 'and', 'filters': exact}] if exact else []) + groups
    if not q['stats']:
        q['stats'] = [{'type': 'and', 'filters': []}]
    if l.get('currency') and l.get('amount') is not None:
        tf = q.setdefault('filters', {}).setdefault('trade_filters', {'filters': {}}).setdefault('filters', {})
        tf['price'] = {'option': l['currency'], 'min': l['amount'], 'max': l['amount']}
    return q


def open_listing(con, wid, listing_id):
    """Press "Open this listing": ONE search for that listing's exact stats and price; returns the trade-site link."""
    from . import trade
    e = next((x for x in _load(con) if x['id'] == wid), None)
    if not e:
        return {'ok': False, 'error': 'Not found'}
    l = next((x for x in (e.get('last') or {}).get('listings') or [] if x['id'] == listing_id), None)
    if not l and (e.get('pinned') or {}).get('id') == listing_id:
        l = e['pinned'].get('last')
    if not l:
        return {'ok': False, 'error': 'That listing is no longer in the list: press Check now.'}
    if not trade.enabled():
        return {'ok': False, 'off': True, 'error': 'Trade-site checks are off.'}
    lq = urllib.parse.quote(e['league'])
    try:
        s = json.loads(trade._req(f'/api/trade2/search/poe2/{lq}', {'query': listing_query(e, l), 'sort': {'price': 'asc'}}, 'search'))
    except Exception as ex:
        return {'ok': False, 'error': str(ex)}
    total = s.get('total', 0)
    if not total:
        return {'ok': False, 'gone': True, 'error': 'Not found on the trade site any more: probably sold or taken down.'}
    return {'ok': True, 'url': f"{SITE}/trade2/search/poe2/{lq}/{s['id']}", 'total': total,
            'exact': listing_id in (s.get('result') or [])}


def view_one(e, rt):
    from . import money
    last = e.get('last') or {}
    lq = urllib.parse.quote(e['league'])
    sid = last.get('search_id') or encode_query(e['query'])
    out = {k: e.get(k) for k in ('id', 'name', 'league', 'labels', 'added', 'pinned', 'target_div', 'target_value', 'unit')}
    out['url'] = f'{SITE}/trade2/search/poe2/{lq}/{sid}'
    out['live_url'] = out['url'] + '/live'
    if e.get('target_div'):
        v, u = e.get('target_value'), e.get('unit') or 'div'
        out['target'] = f'{v:g} {u}' if u != 'div' else money.fmt(e['target_div'], rt)
    if last:
        out['last'] = dict(last, low=money.fmt(last.get('low_div'), rt), median=money.fmt(last.get('median_div'), rt))
        for l in out['last']['listings']:
            l['price'] = money.fmt(l['div'], rt) if l.get('div') is not None else None
        for g in out['last'].get('gone') or []:
            g['price'] = money.fmt(g.get('div'), rt) if g.get('div') is not None else None
        out['under_target'] = [l['id'] for l in last.get('listings') or []
                               if e.get('target_div') and l.get('div') is not None and l['div'] <= e['target_div']]
    out['history'] = [{'ts': h['ts'], 'total': h['total'], 'low': money.fmt(h['low_div'], rt) if h.get('low_div') else None,
                       'low_div': h.get('low_div')} for h in (e.get('history') or [])[-30:]]
    return out


def status(con):
    from . import money, ninja, trade
    rt = money.rates(con, ninja.current_league(con))
    return {'items': [view_one(e, rt) for e in _load(con)], 'enabled': trade.enabled(), 'max': MAX,
            'note': 'Checked only when you press Check now (one search, inside the trade site\'s limits). A listing that '
                    'left the results and no longer exists is "gone": sold or taken down (the trade site doesn\'t say '
                    'which). For instant news of new listings use Open live search (the trade site\'s own feature).'}
