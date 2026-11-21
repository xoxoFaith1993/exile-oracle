"""Analyse series.json (first 72 h, hours since launch) + ls_price day 3-7 (app DB, read-only).
Writes analysis.json and prints summaries. Usage: python -I analyse72.py series.json analysis.json"""
import json, math, sqlite3, statistics as st, sys
from collections import defaultdict

SER, OUT = sys.argv[1], sys.argv[2]
S = {lg: {int(k): v for k, v in d.items()} for lg, d in json.load(open(SER, encoding='utf-8')).items()}
LGS = ['Fate of the Vaal', 'Runes of Aldur', 'Forbidden Rites']
SHORT = {'Fate of the Vaal': 'FotV', 'Runes of Aldur': 'RoA', 'Forbidden Rites': 'FR'}
OFF = {'Fate of the Vaal': 4, 'Runes of Aldur': 3, 'Forbidden Rites': 3}   # L = exchange offset_h + OFF
LAUNCH_UTC = {'Fate of the Vaal': 19, 'Runes of Aldur': 20, 'Forbidden Rites': 20}
con = sqlite3.connect('file:<data folder>/data/poe2kit.db?mode=ro', uri=True)
names = {k: v.get('name') for k, v in json.load(open('<data folder>/data/repoe/base_items.min.json', encoding='utf-8')).items() if v.get('name')}
cat = {}
for n, c in con.execute("SELECT DISTINCT name, category FROM price WHERE source='ninja-exchange'"):
    cat.setdefault(n, c)


def catof(n):
    if n in cat:
        return cat[n]
    if n.startswith('Omen'):
        return 'Ritual'
    if 'Rune' in n or 'Talisman' in n:
        return 'Runes'
    if n.startswith('Uncut'):
        return 'UncutGems'
    if 'Essence' in n:
        return 'Essences'
    if 'Soul Core' in n:
        return 'SoulCores'
    if 'Catalyst' in n or ('Splinter' in n and 'Breach' in n):
        return 'Breach'
    if 'Liquid' in n or 'Distilled' in n:
        return 'Delirium'
    return 'Other'


CATNAME = {'Currency': 'Currency', 'Ritual': 'Omens & Ritual', 'Essences': 'Essences', 'Runes': 'Runes',
           'SoulCores': 'Soul cores', 'UncutGems': 'Uncut gems', 'Fragments': 'Fragments',
           'Delirium': 'Liquid emotions & Delirium', 'Breach': 'Breach (catalysts, splinters)', 'Abyss': 'Abyss',
           'Expedition': 'Expedition', 'LineageSupportGems': 'Lineage gems', 'Verisium': 'Verisium',
           'Idols': 'Idols', 'Other': 'Other'}
HOURS = range(0, 73)
out = {'base': {}, 'liquidity': {}, 'items': {}, 'categories': {}, 'early_buys': [], 'fallers': []}

# ---------- base rates ----------
for lg in LGS:
    rows = {}
    for L in HOURS:
        s = S[lg].get(L)
        if not s or not s.get('markets') or not s.get('div_ex'):
            continue
        rows[L] = {'div_ex': s['div_ex'], 'chaos_per_div': s['div_ex'] / s['chaos_ex'] if s.get('chaos_ex') else None,
                   'div_vol': s['div_vol'], 'markets': s['markets'], 'value_ex': s['value_ex']}

    def roll(key):
        r = {}
        for L in rows:
            xs = [rows[x][key] for x in (L - 1, L, L + 1) if x in rows and rows[x][key]]
            if xs:
                r[L] = st.median(xs)
        return r
    dx, cd = roll('div_ex'), roll('chaos_per_div')
    mv = sorted(((math.log(dx[L + 6] / dx[L]), L) for L in dx if L + 6 in dx and L >= 4), reverse=True)
    cmv = sorted((math.log(cd[L + 6] / cd[L]), L) for L in cd if L + 6 in cd and L >= 4)
    bands = {}
    for b0 in range(0, 72, 12):
        a = [dx[L] for L in range(b0, b0 + 12) if L in dx]
        c = [cd[L] for L in range(b0, b0 + 12) if L in cd]
        bands[f'{b0}-{b0 + 12}'] = {'div_ex_median': round(st.median(a), 1) if a else None,
                                    'chaos_per_div_median': round(st.median(c), 1) if c else None}
    out['base'][lg] = {'div_ex_hourly': {L: round(v, 1) for L, v in dx.items()},
                       'chaos_per_div_hourly': {L: round(v, 1) for L, v in cd.items()},
                       'div_ex_fastest_6h': [{'from_L': L, 'change_pct': round((math.exp(x) - 1) * 100)} for x, L in mv[:6]],
                       'div_ex_falling_6h': [{'from_L': L, 'change_pct': round((math.exp(x) - 1) * 100)} for x, L in mv[-4:]],
                       'chaos_gains_fastest_6h': [{'from_L': L, 'chaos_per_div_change_pct': round((math.exp(x) - 1) * 100)} for x, L in cmv[:6]],
                       'chaos_loses_fastest_6h': [{'from_L': L, 'chaos_per_div_change_pct': round((math.exp(x) - 1) * 100)} for x, L in cmv[-4:]],
                       'bands': bands, 'first_trade_L': min(L for L in S[lg] if S[lg][L].get('markets'))}
    val = {L: rows[L]['value_ex'] / rows[L]['div_ex'] for L in rows}
    ref = st.mean([val[L] for L in range(48, 73) if L in val])
    vr = {L: val[L] / ref for L in val}

    def first(th):
        for L in sorted(vr):
            if vr[L] >= th and all(vr.get(x, 0) >= th * 0.7 for x in (L + 1, L + 2) if x in vr):
                return L
    sp = {L: S[lg][L].get('div_spread') for L in rows}
    tight = next((L for L in sorted(sp) if sp[L] is not None and sp[L] < 0.15
                  and all((sp.get(x) if sp.get(x) is not None else 9) < 0.3 for x in (L + 1, L + 2))), None)
    tod = defaultdict(list)
    for L in range(24, 73):
        if L in val:
            tod[(LAUNCH_UTC[lg] + L) % 24].append(val[L])
    todm = {h: st.mean(v) for h, v in tod.items()}
    mx = max(todm.values())
    out['liquidity'][lg] = {'value_index_vs_L48_72': {L: round(v, 3) for L, v in vr.items()},
                            'first_L_10pct': first(0.10), 'first_L_25pct': first(0.25), 'first_L_50pct': first(0.5),
                            'first_L_divex_spread_under_15pct': tight,
                            'markets_hourly': {L: rows[L]['markets'] for L in rows},
                            'utc_hour_of_day_index_L24_72': {h: round(v / mx, 2) for h, v in sorted(todm.items())}}

# ---------- items ----------
tot = {}
for lg in LGS:
    for L in HOURS:
        s = S[lg].get(L)
        if not s or not s.get('div_ex'):
            continue
        for n, (p, u, v) in s['items'].items():
            tot.setdefault(n, {}).setdefault(lg, 0)
            tot[n][lg] += v / s['div_ex']


def score(n):
    xs = [tot[n].get(lg, 0) for lg in LGS]
    if sum(1 for x in xs if x > 0) < 2:
        return 0
    return sum(sorted(xs)[1:])


cands = [n for n in tot if n not in ('Exalted Orb', 'Divine Orb', 'Chaos Orb')]
cands.sort(key=score, reverse=True)
TOP = cands[:75]


def load_days(a, b):
    D = {}
    for lg in LGS:
        for it, pdiv, u in con.execute('SELECT item, price_div, units FROM ls_price WHERE league=? AND offset_h BETWEEN ? AND ? AND price_div>0', (lg, a, b)):
            D.setdefault(names.get(it, it.split('/')[-1]), {}).setdefault(lg, []).append((pdiv, u))
    return D


d3, d6 = load_days(72, 95), load_days(144, 167)
lsh = defaultdict(dict)  # (name, lg) -> offset -> price_div
for lg in LGS:
    for off, it, pdiv in con.execute('SELECT offset_h, item, price_div FROM ls_price WHERE league=? AND offset_h>=69 AND price_div>0', (lg,)):
        lsh[(names.get(it, it.split('/')[-1]), lg)][off + OFF[lg]] = pdiv


def dmed(D, n, lg, minu=1):
    xs = [p for p, u in D.get(n, {}).get(lg, []) if u >= minu]
    return st.median(xs) if xs else None


def curves(lg, n):
    raw = {}
    for L in HOURS:
        s = S[lg].get(L)
        if not s or not s.get('div_ex'):
            continue
        it = s['items'].get(n)
        if not it:
            continue
        raw[L] = (it[0] / s['div_ex'], it[1], it[2])
    sm = {}
    for L in raw:
        xs = [raw[x] for x in (L - 1, L, L + 1) if x in raw and raw[x][1] > 0]
        if xs:
            w = sum(x[2] for x in xs)
            sm[L] = (sum(x[0] * x[2] for x in xs) / w if w else st.median(x[0] for x in xs), raw[L][1])
    return raw, sm


for n in TOP + ['Divine Orb', 'Exalted Orb', 'Chaos Orb']:
    rec = {'category': CATNAME.get(catof(n), catof(n)), 'leagues': {}}
    for lg in LGS:
        raw, sm = curves(lg, n)
        if not sm:
            continue
        umax = max(u for _, u in sm.values())
        ok = {L: p for L, (p, u) in sm.items() if u >= max(2, 0.05 * umax)}
        if len(ok) < 6:
            rec['leagues'][SHORT[lg]] = {'hourly_div': {L: float(f'{raw[L][0]:.4g}') for L in raw}, 'thin': True}
            continue
        pk = max(ok, key=ok.get)
        bt = min(ok, key=ok.get)

        def band(a, b):
            xs = [ok[L] for L in range(a, b) if L in ok]
            return st.median(xs) if xs else None
        bm = {f'{a}-{a + 12}': band(a, a + 12) for a in range(0, 72, 12)}
        umed = st.median(u for _, u in sm.values())
        liq = next((L for L in sorted(sm) if sm[L][1] >= max(3, 0.5 * umed)), None)
        p_d3, p_d6 = dmed(d3, n, lg), dmed(d6, n, lg)
        rec['leagues'][SHORT[lg]] = {
            'hourly_div': {L: float(f'{raw[L][0]:.4g}') for L in raw},
            'units_hourly': {L: round(raw[L][1]) for L in raw},
            'peak_L': pk, 'peak_div': float(f'{ok[pk]:.4g}'), 'bottom_L': bt, 'bottom_div': float(f'{ok[bt]:.4g}'),
            'first_trade_L': min(raw), 'usable_liquidity_L': liq,
            'band_median_div': {k: (float(f'{v:.4g}') if v else None) for k, v in bm.items()},
            'day3_div': p_d3 and float(f'{p_d3:.4g}'), 'day6_div': p_d6 and float(f'{p_d6:.4g}'),
            'units_72h': round(sum(u for _, u, _ in raw.values())), 'value_div_72h': round(tot[n].get(lg, 0), 1)}
    out['items'][n] = rec

# ---------- categories ----------
cats = {}
for n, rec in out['items'].items():
    if n in ('Divine Orb', 'Exalted Orb', 'Chaos Orb'):
        continue
    for lg, r in rec['leagues'].items():
        if r.get('thin'):
            continue
        bm = r['band_median_div']
        vals = [v for v in bm.values() if v]
        if len(vals) < 4:
            continue
        med = st.median(vals)
        x = {k: (v / med if v else None) for k, v in bm.items()}
        if r.get('day6_div'):
            x['day6'] = r['day6_div'] / med
        cats.setdefault(rec['category'], {}).setdefault(lg, []).append(x)
for c, lgs in cats.items():
    res = {}
    for lg, lst in lgs.items():
        keys = list(lst[0].keys()) + (['day6'] if 'day6' not in lst[0] else [])
        res[lg] = {k: (round(st.median([x[k] for x in lst if x.get(k)]), 2) if any(x.get(k) for x in lst) else None) for k in keys}
        res[lg]['n_items'] = len(lst)
    out['categories'][c] = res

# ---------- early buys and fast fallers (whole universe) ----------
allnames = set(d6) | set(tot)
for n in allnames:
    gains, early, peakL = {}, {}, {}
    for lg in LGS:
        raw, sm = curves(lg, n)
        e = [p for L, (p, u) in sm.items() if 12 <= L < 24 and u >= 1]
        p6 = dmed(d6, n, lg, 3)
        if len(e) >= 4 and p6:
            early[lg] = st.median(e)
            gains[lg] = p6 / early[lg] - 1
    if len(gains) < 2:
        continue
    rowbase = {'item': n, 'category': CATNAME.get(catof(n), catof(n)),
               'early_div_L12_24': {SHORT[l]: float(f'{v:.3g}') for l, v in early.items()},
               'gain_pct_by_day6': {SHORT[l]: round(g * 100) for l, g in gains.items()},
               'median_gain_pct': round(st.median(gains.values()) * 100), 'leagues': len(gains),
               'value_div_72h': {SHORT[l]: round(tot.get(n, {}).get(l, 0), 1) for l in gains}}
    if min(gains.values()) > 0.3:
        hh = {}
        for lg in gains:
            raw, sm = curves(lg, n)
            half = early[lg] * (1 + gains[lg] / 2)
            hit = next((L for L in sorted(sm) if L >= 12 and sm[L][0] >= half and sm[L][1] >= 1), None)
            if hit is None:
                seq = lsh.get((n, lg), {})
                hit = next((L for L in sorted(seq) if L > 72 and seq[L] >= half), 170)
            hh[SHORT[lg]] = hit
        rowbase['half_gain_reached_L'] = hh
        out['early_buys'].append(rowbase)
    if max(gains.values()) < -0.4:
        out['fallers'].append(rowbase)
out['early_buys'].sort(key=lambda r: (r['leagues'], r['median_gain_pct']), reverse=True)
out['fallers'].sort(key=lambda r: -sum(r['value_div_72h'].values()))
out['top_items'] = TOP
json.dump(out, open(OUT, 'w', encoding='utf-8'), indent=1)

# ---------- print ----------
for lg in LGS:
    b, q = out['base'][lg], out['liquidity'][lg]
    print(lg, 'first trade L', b['first_trade_L'], 'liq10/25/50', q['first_L_10pct'], q['first_L_25pct'], q['first_L_50pct'],
          'tight spread L', q['first_L_divex_spread_under_15pct'])
    print('  bands', b['bands'])
    print('  fastest div_ex 6h', b['div_ex_fastest_6h'], 'falling', b['div_ex_falling_6h'])
    print('  chaos gains', b['chaos_gains_fastest_6h'], 'chaos loses', b['chaos_loses_fastest_6h'])
    print('  tod', q['utc_hour_of_day_index_L24_72'])
    print('  liq idx', {L: v for L, v in q['value_index_vs_L48_72'].items() if L % 3 == 0})
print('\nCATEGORIES (band median / item 72h median)')
for c, r in out['categories'].items():
    print(c, {lg: [v for k, v in x.items()] for lg, x in r.items()})
print('\nTOP ITEMS')
for n in TOP:
    rec = out['items'][n]
    s = []
    for lg, r in rec['leagues'].items():
        if r.get('thin'):
            s.append(f'{lg}:thin')
            continue
        bm = r['band_median_div']
        s.append(f"{lg}: pk{r['peak_L']} bt{r['bottom_L']} liq{r['usable_liquidity_L']} "
                 + '/'.join(f'{v:.3g}' if v else '-' for v in bm.values()) + f" d3 {r['day3_div']} d6 {r['day6_div']} v{r['value_div_72h']}")
    print(f"{n} [{rec['category']}] | " + ' | '.join(s))
print('\nEARLY BUYS')
for r in out['early_buys'][:50]:
    print(r['item'], r['category'], r['early_div_L12_24'], r['gain_pct_by_day6'], r['half_gain_reached_L'], r['value_div_72h'])
print('\nFALLERS')
for r in out['fallers'][:40]:
    print(r['item'], r['category'], r['early_div_L12_24'], r['gain_pct_by_day6'], r['value_div_72h'])
