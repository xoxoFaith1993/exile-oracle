"""Steps 2-3: classify every patch line with ../rules.py, find the exchange items each price-relevant line touches,
and measure what those items did after the post, net of the league's drift over the same hours.

Windows (all prices in Divine Orbs, GGG public exchange history, see exchange.py):
  base  = the full hour before the post (H0), averaged (geometric mean) with the hour before that
  h24 / h72 / d7 = the single hours H0 + 24 / 72 / 168 h
  pre7  = H0 - 168 h -> H0 (the item's own trend before the post: a placebo / "was it already moving?")
Drift (the control):
  group drift  = median change of the other liquid items in the same exchange group (Omens, Breach, ...), same hours
  market drift = median change of all liquid items, same hours
  abnormal     = (1 + item change) / (1 + group drift, else market drift) - 1
Noise floor: for each event, the median |abnormal| of random unaffected liquid items over the same window.

Usage: python -I measure.py plan      -> cache/events.json (which posts and hours are needed) and the hour count
       python -I measure.py fetch     -> fetches the missing hours (2.5 s apart; resumable)
       python -I measure.py measure   -> cache/measured.json
"""
import json
import math
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))   # ../rules.py
sys.path.insert(0, HERE)
import rules  # noqa: E402
import exchange  # noqa: E402

C = os.path.join(HERE, 'cache')
DIV, EX, CHAOS = exchange.DIV, exchange.EX, exchange.CHAOS
OFFS = {'pre7': -168, 'base': 0, 'h24': 24, 'h72': 72, 'd7': 168}
MIN_UNITS = 5
PRICE_CLASSES = {'drop_source', 'drop_rate', 'farm', 'exploit_fix', 'crafting', 'vendor_recipe', 'league_mechanic'}
# exchange groups each mechanic's outputs live in (see build_names.group_of)
MECH_GROUPS = {
    'breach': ['Breach', 'Catalysts'], 'delirium': ['Delirium'], 'ritual': ['Omens', 'Ritual'],
    'expedition': ['Expedition'], 'abyss': ['Abyssal bones', 'Abyssal Bones'], 'essence': ['Essences'],
    'vaal_temple': ['Vaal', 'Soul cores'], 'ultimatum': ['Ultimatum/Sekhemas'], 'sekhemas': ['Ultimatum/Sekhemas'],
    'runes_of_aldur': ['Runes', 'Verisium'], 'strongbox': [], 'waystones': [], 'pinnacle': [],
}
FAMILY_GROUPS = {'Omens': 'Omens', 'Essences': 'Essences', 'Soul cores': 'Soul cores', 'Catalysts': 'Catalysts',
                 'Liquid emotions': 'Delirium', 'Abyssal bones': 'Abyssal bones', 'Trialmaster Fates': 'Ultimatum/Sekhemas',
                 'Runes': 'Runes', 'Uncut gems': 'Uncut gems', 'Lineage support gems': 'LineageSupportGems',
                 'Idols': 'Idols', 'Wombgifts': 'Breach', 'Expedition artifacts': 'Expedition', 'Vaal infusers': 'Vaal'}
LEAGUE_STARTS = [  # first exchange hour of each league (from leaguestart / market research; 0.1-0.3: launch time)
    ('Standard', 1733518800), ('Dawn of the Hunt', 1743796800), ('Rise of the Abyssal', 1756497600),
    ('Fate of the Vaal', 1765580400), ('Runes of Aldur', 1780095600), ('Forbidden Rites', 1788562800)]
SKIP_TITLES = ('server maintenance', 'restart', 'rolled back')


def load_meta():
    meta = json.load(open(os.path.join(C, 'meta_names.json'), encoding='utf-8'))
    by_name = {}
    for k, v in meta.items():
        by_name.setdefault(v['name'].lower(), k)
    return meta, by_name


def hour_of(iso):
    import datetime as dt
    t = dt.datetime.strptime(iso, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc)
    return int(t.timestamp()) // 3600 * 3600


def league_day(h):
    st = [s for _, s in LEAGUE_STARTS if s <= h]
    return round((h - st[-1]) / 86400, 1) if st else None


def is_content_update(title):
    t = title.lower()
    return t.startswith('content update') or 'forbidden rites patch notes' in t


def affected_ids(line, section, hits, meta, by_name):
    """metadata ids a classified line touches (named items first, else mechanic outputs)."""
    ids, how = set(), None
    named = rules.named_items(line)
    for n, kind in named:
        nl = n.lower()
        if kind == 'item':
            for cand in (nl, nl.rstrip('s')):
                if cand in by_name:
                    ids.add(by_name[cand])
                    break
        elif n in FAMILY_GROUPS:
            pass
    if ids:
        how = 'named'
    else:
        fams = [FAMILY_GROUPS[n] for n, k in named if k == 'family' and n in FAMILY_GROUPS]
        if fams:
            ids = {k for k, v in meta.items() if v['group'] in fams}
            how = 'family'
        else:
            mechs = rules.mechanics_of(line, section)
            groups = [g for m in mechs for g in MECH_GROUPS.get(m, [])]
            if groups and any(h['class'] in ('farm', 'exploit_fix', 'league_mechanic', 'drop_rate', 'drop_source') for h in hits):
                ids = {k for k, v in meta.items() if v['group'] in groups}
                how = 'mechanic'
    return sorted(ids), how


def plan():
    posts = json.load(open(os.path.join(C, 'forum', 'patches_raw.json'), encoding='utf-8'))
    meta, by_name = load_meta()
    events, hours = [], set()
    for p in posts:
        if any(s in p['title'].lower() for s in SKIP_TITLES) and len(p['lines']) < 3:
            continue
        h0 = hour_of(p['date_utc']) - 3600
        lines = []
        for ln in p['lines']:
            ctx = ln['text'] if not ln.get('parent') else ln['text'] + ' (' + ln['parent'][:150] + ')'
            hits = rules.classify(ln['text'], ln['section'])
            hits = [h for h in hits if h['class'] in PRICE_CLASSES or h['direction'] in ('buff', 'nerf')]
            if not hits:
                continue
            ids, how = affected_ids(ln['text'], (ln.get('parent') or '') + ' ' + ln['section'], hits, meta, by_name)
            lines.append({'text': ln['text'], 'section': ln['section'], 'parent': ln.get('parent'), 'hits': hits,
                          'ids': ids, 'how': how})
        measurable = [l for l in lines if l['ids'] and any(h['class'] in PRICE_CLASSES for h in l['hits'])]
        ev = {'thread': p['thread'], 'title': p['title'], 'url': p['url'], 'date_utc': p['date_utc'], 'h0': h0,
              'league_day': league_day(h0), 'content_update': is_content_update(p['title']),
              'n_lines': len(p['lines']), 'lines': lines, 'measure': bool(measurable) and not is_content_update(p['title'])}
        events.append(ev)
        if ev['measure']:
            for o in OFFS.values():
                hours.add(h0 + o * 3600)
            hours.add(h0 - 3600)   # base = two-hour average
    json.dump(events, open(os.path.join(C, 'events.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    have = {int(f.split('.')[0]) for f in os.listdir(os.path.join(C, 'prices'))} if os.path.isdir(os.path.join(C, 'prices')) else set()
    need = sorted(h for h in hours if h not in have and h < 1795244400)
    json.dump(need, open(os.path.join(C, 'hours_needed.json'), 'w'))
    print(len(events), 'posts;', sum(e['measure'] for e in events), 'to measure;', len(hours), 'hours,', len(need), 'missing')


def fetch():
    need = json.load(open(os.path.join(C, 'hours_needed.json')))
    for i, h in enumerate(need):
        try:
            d = exchange.prices(h)
            if i % 20 == 0:
                print(i, len(need), h, d['league'], round(d['div_ex'] or 0), len(d['items']), d['source'], flush=True)
        except Exception as e:
            print('ERR', h, e, flush=True)


def _price(h, it):
    """two-hour average Divine price, units (needs units >= MIN_UNITS in at least one hour)."""
    vals = []
    lg = None
    for hh in (h, h - 3600):
        p = os.path.join(C, 'prices', f'{hh}.json')
        if not os.path.exists(p):
            continue
        d = _PC.get(hh)
        if d is None:
            d = _PC[hh] = json.load(open(p, encoding='utf-8'))
        lg = lg or d['league']
        if it == DIV:
            if d.get('div_ex'):
                vals.append((d['div_ex'], 999))   # Divine priced in Exalted
            continue
        x = d['items'].get(it)
        if x and x[0] and x[0] > 0:
            vals.append((x[0], x[1] or 0))
    if not vals or max(u for _, u in vals) < MIN_UNITS:
        return None, lg
    return math.exp(sum(math.log(v) for v, _ in vals) / len(vals)), lg


_PC = {}


def _league(h):
    for hh in (h, h - 3600):
        p = os.path.join(C, 'prices', f'{hh}.json')
        if os.path.exists(p):
            d = _PC.get(hh) or json.load(open(p, encoding='utf-8'))
            _PC[hh] = d
            return d['league']
    return None


def _chg(h0, h1, it):
    a, la = _price(h0, it)
    b, lb = _price(h1, it)
    if a and b and la == lb:
        return b / a - 1
    return None


def _universe(h0, h1):
    """all liquid items present at both hours, with their change."""
    d0 = _PC.get(h0) or (os.path.exists(os.path.join(C, 'prices', f'{h0}.json')) and json.load(open(os.path.join(C, 'prices', f'{h0}.json'), encoding='utf-8')))
    if not d0:
        return {}
    _PC[h0] = d0
    out = {}
    for it, (p, u) in d0['items'].items():
        if it in (DIV,) or not p or p < 0.0005 or (u or 0) < MIN_UNITS:
            continue
        c = _chg(h0, h1, it)
        if c is not None:
            out[it] = c
    return out


def measure():
    events = json.load(open(os.path.join(C, 'events.json'), encoding='utf-8'))
    meta, _ = load_meta()
    rnd = random.Random(7)
    res = []
    for ev in events:
        if not ev['measure']:
            continue
        h0 = ev['h0']
        lg0 = _league(h0)
        if not lg0:
            continue
        uni = {}
        for w, o in OFFS.items():
            if w == 'base':
                continue
            a, b = (h0 + o * 3600, h0) if o < 0 else (h0, h0 + o * 3600)
            if _league(a) != lg0 or _league(b) != lg0:
                continue
            uni[w] = _universe(a, b)
        affected_all = {i for l in ev['lines'] for i in l['ids']}
        noise = {}
        for w, u in uni.items():
            pool = [k for k in u if k not in affected_all]
            if len(pool) >= 20:
                mkt = statistics.median(u[k] for k in pool)
                sample = rnd.sample(pool, min(60, len(pool)))
                noise[w] = {'market_drift': round(mkt * 100, 1),
                            'median_abs_abnormal': round(statistics.median(abs((1 + u[k]) / (1 + mkt) - 1) for k in sample) * 100, 1),
                            'n_items': len(pool)}
        out_lines = []
        for l in ev['lines']:
            if not l['ids']:
                out_lines.append(dict(l, measured=None))
                continue
            per_item = []
            for it in l['ids']:
                g = meta.get(it, {}).get('group')
                row = {'id': it, 'name': meta.get(it, {}).get('name', it.rsplit('/', 1)[-1]), 'group': g}
                p0, _ = _price(h0, it)
                row['base_div'] = round(p0, 5) if p0 else None
                for w, u in uni.items():
                    if it not in u and it != DIV:
                        continue
                    o = OFFS[w]
                    c = u.get(it) if it != DIV else _chg(*((h0 + o * 3600, h0) if o < 0 else (h0, h0 + o * 3600)), it)
                    if c is None:
                        continue
                    peers = [u[k] for k in u if k not in affected_all and meta.get(k, {}).get('group') == g]
                    pool = [u[k] for k in u if k not in affected_all]
                    if it == DIV:   # Divine priced in Exalted: no drift control (it IS the numeraire)
                        drift, dk = 0.0, 'none (Div in Ex)'
                    elif len(peers) >= 4:
                        drift, dk = statistics.median(peers), 'group'
                    elif len(pool) >= 20:
                        drift, dk = statistics.median(pool), 'market'
                    else:
                        continue
                    row[w] = {'raw': round(c * 100, 1), 'drift': round(drift * 100, 1), 'drift_kind': dk,
                              'abnormal': round(((1 + c) / (1 + drift) - 1) * 100, 1)}
                if any(w in row for w in ('h24', 'h72', 'd7')):
                    per_item.append(row)
            m = {}
            for w in ('pre7', 'h24', 'h72', 'd7'):
                v = [r[w]['abnormal'] for r in per_item if w in r]
                if v:
                    m[w] = {'median_abnormal': round(statistics.median(v), 1), 'n_items': len(v),
                            'median_raw': round(statistics.median(r[w]['raw'] for r in per_item if w in r), 1)}
                    # placebo: the same number of random unaffected liquid items, same hours, vs market drift
                    u = uni.get(w, {})
                    pool = [k for k in u if k not in affected_all]
                    if len(pool) >= 20:
                        mk = statistics.median(u[k] for k in pool)
                        k = min(len(v), len(pool))
                        sims = sorted(abs(statistics.median(((1 + u[x]) / (1 + mk) - 1) * 100 for x in rnd.sample(pool, k)))
                                      for _ in range(200))
                        p90 = sims[int(0.9 * len(sims))]
                        m[w]['placebo_p90_abs'] = round(p90, 1)
                        m[w]['beyond_noise'] = abs(m[w]['median_abnormal']) > p90
            per_item.sort(key=lambda r: -(r.get('base_div') or 0))
            out_lines.append(dict(l, measured=m or None, items=per_item[:12], n_items_total=len(per_item)))
        res.append(dict(ev, lines=out_lines, noise=noise, league=lg0))
    json.dump(res, open(os.path.join(C, 'measured.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print(len(res), 'events measured')


if __name__ == '__main__' and not sys.argv[1].startswith('phase'):
    {'plan': plan, 'fetch': fetch, 'measure': measure}[sys.argv[1]]()


# ---------------- cross-league phase control ----------------
# Same item, same league-day window, in other leagues: removes the normal league-life drift (soul cores peaking on
# day 10, emotions crashing in week 1, ...), which the same-hour group control cannot when a whole group is affected.
PHASE_COMP = {'Dawn of the Hunt': ['Rise of the Abyssal', 'Fate of the Vaal'],
              'Rise of the Abyssal': ['Dawn of the Hunt', 'Fate of the Vaal'],
              'Fate of the Vaal': ['Runes of Aldur', 'Forbidden Rites'],
              'Runes of Aldur': ['Fate of the Vaal', 'Forbidden Rites'],
              'Forbidden Rites': ['Runes of Aldur', 'Fate of the Vaal']}
START = dict(LEAGUE_STARTS)
LAST_HOUR = 1795244400
PHASE_W = {'base': 0, 'h72': 72, 'd7': 168}


def league_at(h):
    st = [(s, n) for n, s in LEAGUE_STARTS if s <= h]
    return st[-1][1] if st else None


def phase_hours(ev):
    lg = league_at(ev['h0'])
    out = []
    for comp in PHASE_COMP.get(lg, []):
        off = ev['h0'] - START[lg]
        for w, o in PHASE_W.items():
            h = START[comp] + off + o * 3600
            if h <= LAST_HOUR:
                out.append((w, comp, h))
    return lg, out


def phase_plan():
    events = json.load(open(os.path.join(C, 'events.json'), encoding='utf-8'))
    need = set()
    for ev in events:
        if ev['measure']:
            _, hs = phase_hours(ev)
            need |= {(c, h) for _, c, h in hs}
    d = os.path.join(C, 'prices_lg')
    have = set(os.listdir(d)) if os.path.isdir(d) else set()
    miss = sorted((c, h) for c, h in need if f"{c.replace(' ', '_')}_{h}.json" not in have)
    json.dump(miss, open(os.path.join(C, 'phase_needed.json'), 'w'))
    print(len(need), 'phase hours,', len(miss), 'missing')


def phase_fetch():
    miss = json.load(open(os.path.join(C, 'phase_needed.json')))
    for i, (c, h) in enumerate(miss):
        try:
            d = exchange.prices_league(h, c)
            if i % 20 == 0:
                print(i, len(miss), c, h, len(d['items']), flush=True)
        except Exception as e:
            print('ERR', c, h, e, flush=True)


def _plg(league, h, it):
    p = os.path.join(C, 'prices_lg', f"{league.replace(' ', '_')}_{h}.json")
    if not os.path.exists(p):
        return None
    d = _PC.get(p)
    if d is None:
        d = _PC[p] = json.load(open(p, encoding='utf-8'))
    x = d['items'].get(it)
    if not x or not x[0] or (x[1] or 0) < MIN_UNITS:
        return None
    return x[0]


def comp_market(league, h0, h1):
    """median change of all liquid items in a league between two hours (phase-control market drift)."""
    k = ('mkt', league, h0, h1)
    if k in _PC:
        return _PC[k]
    p0 = os.path.join(C, 'prices_lg', f"{league.replace(' ', '_')}_{h0}.json")
    if not os.path.exists(p0):
        _PC[k] = None
        return None
    d0 = json.load(open(p0, encoding='utf-8'))
    ch = []
    for it, (pr, u) in d0['items'].items():
        if it == DIV or not pr or pr < 0.0005 or (u or 0) < MIN_UNITS:
            continue
        b = _plg(league, h1, it)
        if b:
            ch.append(b / pr - 1)
    _PC[k] = statistics.median(ch) if len(ch) >= 20 else None
    return _PC[k]


def phase_measure():
    """adds phase_drift / phase_abnormal to cache/measured.json items and lines (h72, d7)."""
    res = json.load(open(os.path.join(C, 'measured.json'), encoding='utf-8'))
    for ev in res:
        lg, hs = phase_hours(ev)
        by = {}
        for w, c, h in hs:
            by.setdefault(c, {})[w] = h
        for l in ev['lines']:
            if not l.get('measured'):
                continue
            for w in ('h72', 'd7'):
                vals, drifts = [], []
                for row in l.get('items', []):
                    if w not in row or row['id'] == DIV:
                        continue
                    cs = []
                    mk = (ev.get('noise', {}).get(w) or {}).get('market_drift')
                    if mk is None:
                        continue
                    for c, hh in by.items():
                        if 'base' in hh and w in hh:
                            a, b = _plg(c, hh['base'], row['id']), _plg(c, hh[w], row['id'])
                            cmk = comp_market(c, hh['base'], hh[w])
                            if a and b and cmk is not None:
                                cs.append(((1 + row[w]['raw'] / 100) / (b / a)) / ((1 + mk / 100) / (1 + cmk)) - 1)
                    if cs:
                        row[w]['phase_abnormal'] = round(statistics.median(cs) * 100, 1)
                        row[w]['phase_leagues'] = len(cs)
                        vals.append(row[w]['phase_abnormal'])
                        drifts.append(0)
                if vals and w in l['measured']:
                    l['measured'][w]['median_phase_abnormal'] = round(statistics.median(vals), 1)
                    l['measured'][w]['median_phase_drift'] = round(statistics.median(drifts), 1)
                    l['measured'][w]['n_items_phase'] = len(vals)
    json.dump(res, open(os.path.join(C, 'measured.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('phase control added')


if __name__ == '__main__' and sys.argv[1].startswith('phase'):
    {'phase_plan': phase_plan, 'phase_fetch': phase_fetch, 'phase_measure': phase_measure}[sys.argv[1]]()
