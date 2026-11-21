"""Build hourly series for the first 72 h of each launch from the cached GGG exchange digests (cache/*.json.gz).
Hour axis: L = hours since the official launch time (FotV 2025-12-12 19:00 UTC, RoA 2026-05-29 20:00 UTC,
FR 2026-09-04 20:00 UTC; GGG/Steam announcements). The digest id is a unix hour; we take it as the start of the
hour it covers (GGG doesn't document this; +-1 h).
Price method: for each item, every market it has against Exalted, Divine or Chaos gives a volume-weighted price
(units of B / units of A traded that hour); converted to Exalts at that hour's Div:Ex and Chaos:Ex rates and
combined, weighted by the Exalt value traded on each market. Low/high ratios are used only when nothing traded.
Output: series.json {league: {L: {div_ex, chaos_ex, markets, value_ex, div_spread, items: {name: [p_ex, units, value_ex]}}}}
Usage: python -I hourly.py <cache_dir> <out series.json>"""
import gzip, glob, json, os, sqlite3, statistics, sys

CACHE, OUT = sys.argv[1], sys.argv[2]
EX = 'Metadata/Items/Currency/CurrencyAddModToRare'
DIV = 'Metadata/Items/Currency/CurrencyModValues'
CHAOS = 'Metadata/Items/Currency/CurrencyRerollRare'
LAUNCH = {'Fate of the Vaal': 1765566000, 'Runes of Aldur': 1780084800, 'Forbidden Rites': 1788552000}
names = {k: v.get('name') for k, v in json.load(open('<data folder>/data/repoe/base_items.min.json', encoding='utf-8')).items() if v.get('name')}


def vwap(m, a, b):
    """units of b per 1 a, and units of a traded"""
    vol, lo, hi = m.get('volume_traded') or {}, m.get('lowest_ratio') or {}, m.get('highest_ratio') or {}
    if vol.get(a) and vol.get(b):
        return vol[b] / vol[a], vol[a], True
    rates = [r[b] / r[a] for r in (lo, hi) if r.get(a) and r.get(b)]
    return (statistics.median(rates), 0, False) if rates else (None, 0, False)


def spread(m, a, b):
    lo, hi = m.get('lowest_ratio') or {}, m.get('highest_ratio') or {}
    rs = [r[b] / r[a] for r in (lo, hi) if r.get(a) and r.get(b)]
    return (max(rs) / min(rs) - 1) if len(rs) == 2 and min(rs) > 0 else None


out = {}
for p in sorted(glob.glob(os.path.join(CACHE, '*.json.gz'))):
    d = json.load(gzip.open(p, 'rt', encoding='utf-8'))
    lg = d['league']
    L = (d['hour'] - LAUNCH[lg]) // 3600
    mk = d['markets']
    if not mk:
        out.setdefault(lg, {})[L] = {'markets': 0}
        continue
    by = {}
    for m in mk:
        a, b = m['market_id'].split('|')
        by[(a, b)] = m
    def get(a, b):
        if (a, b) in by:
            return vwap(by[(a, b)], a, b)
        if (b, a) in by:
            r, u, ok = vwap(by[(b, a)], b, a)
            if r:
                rb, ub, _ = vwap(by[(b, a)], a, b)
                return rb, ub, ok
        return None, 0, False
    div_ex, dvol, _ = get(DIV, EX)
    chaos_ex, cvol, _ = get(CHAOS, EX)
    # fallback via chaos if direct Div|Ex is missing
    if not div_ex and chaos_ex:
        dc, _, _ = get(DIV, CHAOS)
        div_ex = dc * chaos_ex if dc else None
    sp = None
    mm = by.get((DIV, EX)) or by.get((EX, DIV))
    if mm:
        a, b = mm['market_id'].split('|')
        sp = spread(mm, a, b)
    base_ex = {EX: 1.0, DIV: div_ex, CHAOS: chaos_ex}
    acc = {}
    total_value = 0.0
    for (a, b), m in by.items():
        for it, base in ((a, b), (b, a)):
            if base not in base_ex or not base_ex[base] or it == base:
                continue
            r, u, traded = vwap(m, it, base)
            if not r:
                continue
            pex = r * base_ex[base]
            val = pex * u
            if it in (EX, DIV, CHAOS) and base in (EX, DIV, CHAOS):
                pass
            acc.setdefault(it, []).append((pex, u, val, traded))
    items = {}
    for it, xs in acc.items():
        tv = sum(v for _, _, v, t in xs if t)
        if tv > 0:
            pex = sum(p * v for p, _, v, t in xs if t) / tv
        else:
            pex = statistics.median(p for p, *_ in xs)
        units = sum(u for _, u, _, t in xs if t)
        nm = names.get(it, it.split('/')[-1])
        items[nm] = [pex, units, tv]
    # base rates exactly as measured on their direct markets
    if div_ex:
        items['Divine Orb'][0] = div_ex
    if chaos_ex:
        items['Chaos Orb'][0] = chaos_ex
    items.setdefault('Exalted Orb', [1.0, 0, 0])[0] = 1.0
    total_value = sum(v[2] for k, v in items.items() if k != 'Exalted Orb') / 2  # each trade counted on both sides ~
    out.setdefault(lg, {})[L] = {'markets': len(mk), 'div_ex': div_ex, 'chaos_ex': chaos_ex, 'div_vol': dvol,
                                 'chaos_vol': cvol, 'div_spread': sp, 'value_ex': total_value,
                                 'value_div': total_value / div_ex if div_ex else None, 'items': items}
json.dump(out, open(OUT, 'w', encoding='utf-8'))
for lg, S in out.items():
    print(lg)
    for L in sorted(S):
        s = S[L]
        if L <= 12 or L % 6 == 0:
            if s['markets']:
                print(f"  L{L:3d} mk={s['markets']:4d} div_ex={s['div_ex'] and round(s['div_ex'],1)} ex/chaos={s['chaos_ex'] and round(1/s['chaos_ex'],2) if s['chaos_ex'] else None} "
                      f"chaos/div={s['div_ex']/s['chaos_ex'] if s['div_ex'] and s['chaos_ex'] else 0:.1f} divvol={s['div_vol']} spread={s['div_spread'] and round(s['div_spread'],2)} value_div={s['value_div'] and round(s['value_div'])}")
            else:
                print(f'  L{L} empty')
