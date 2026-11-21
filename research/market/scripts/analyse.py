"""Build per-league price series (in Divine) for day 0-6 (ls_price), sampled days 10-70 (fetched pages),
and Forbidden Rites late days (ex_price). Read-only on the app DB."""
import json, os, sqlite3, statistics, sys
PAGES, OUT = sys.argv[1], sys.argv[2]
EX = 'Metadata/Items/Currency/CurrencyAddModToRare'
DIV = 'Metadata/Items/Currency/CurrencyModValues'
CHAOS = 'Metadata/Items/Currency/CurrencyRerollRare'
STARTS = {'Fate of the Vaal': 1765580400, 'Runes of Aldur': 1780095600, 'Forbidden Rites': 1788562800}


def prices_from_page(d, league):
    mk = [m for m in d.get('markets', []) if m.get('league') == league]
    pair = {}
    for m in mk:
        a, b = m['market_id'].split('|')
        lo, hi, vol = m.get('lowest_ratio') or {}, m.get('highest_ratio') or {}, m.get('volume_traded') or {}
        if vol.get(a) and vol.get(b):
            b_per_a = vol[b] / vol[a]
        else:
            rates = [r[b] / r[a] for r in (lo, hi) if r.get(a) and r.get(b)]
            if not rates:
                continue
            b_per_a = statistics.median(rates)
        pair[(a, b)] = (b_per_a, vol.get(a) or 0)
        pair[(b, a)] = (1 / b_per_a, vol.get(b) or 0)
    ex_per = {EX: 1.0}
    for base in (DIV, CHAOS):
        if (base, EX) in pair:
            ex_per[base] = pair[(base, EX)][0]
    out = {}
    for it in {a for a, _ in pair}:
        for base in (EX, DIV, CHAOS):
            if it != base and (it, base) in pair and base in ex_per:
                rate, _ = pair[(it, base)]
                tot = sum(u for (x, _), (_, u) in pair.items() if x == it)
                out[it] = (rate * ex_per[base], tot)
                break
    for base, v in ex_per.items():
        if base != EX:
            out[base] = (v, sum(u for (x, _), (_, u) in pair.items() if x == base))
    return out, ex_per.get(DIV), len(mk)


con = sqlite3.connect('file:<data folder>/data/poe2kit.db?mode=ro', uri=True)
names = {k: v.get('name') for k, v in json.load(open('<data folder>/data/repoe/base_items.min.json', encoding='utf-8')).items() if v.get('name')}
cat = {}
for n, c in con.execute("SELECT DISTINCT name, category FROM price WHERE source='ninja-exchange'"):
    cat.setdefault(n, c)

series = {}   # league -> day -> {'div_ex':..., 'chaos_per_div':..., 'items': {name: [div_price, units]}}
for lg, st in STARTS.items():
    S = series.setdefault(lg, {})
    rows = con.execute('SELECT offset_h, item, price_ex, price_div, units FROM ls_price WHERE league=?', (lg,)).fetchall()
    by = {}
    for off, it, pex, pdiv, u in rows:
        by.setdefault(off // 24, {}).setdefault(it, []).append((pex, pdiv, u))
    for day, its in by.items():
        dx = statistics.median(p for p, _, _ in its.get(DIV, [(None, None, 0)]) if p)
        ch = its.get(CHAOS)
        cx = statistics.median(p for p, _, _ in ch) if ch else None
        S[day] = {'div_ex': dx, 'chaos_per_div': dx / cx if cx else None, 'items': {}}
        for it, xs in its.items():
            pd = [p for _, p, _ in xs if p]
            if pd:
                S[day]['items'][names.get(it, it.split('/')[-1])] = [statistics.median(pd), sum(u for *_, u in xs)]
    for f in os.listdir(PAGES):
        h = int(f[:-5])
        day = round((h - st - 12 * 3600) / 86400)
        if not (0 < h - st < 120 * 86400):
            continue
        d = json.load(open(os.path.join(PAGES, f), encoding='utf-8'))
        pr, dx, n = prices_from_page(d, lg)
        if n < 50 or not dx:
            continue
        cx = pr.get(CHAOS, (None,))[0]
        S[day] = {'div_ex': dx, 'chaos_per_div': dx / cx if cx else None, 'items': {}}
        for it, (p, u) in pr.items():
            S[day]['items'][names.get(it, it.split('/')[-1])] = [p / dx, u]
# Forbidden Rites late league from ex_price (hour = unix seconds)
st = STARTS['Forbidden Rites']
by = {}
for h, it, pex, pdiv, u in con.execute("SELECT hour, item, price_ex, price_div, units FROM ex_price WHERE league='Forbidden Rites'"):
    by.setdefault((h - st) // 86400, {}).setdefault(it, []).append((pex, pdiv, u))
for day, its in by.items():
    if day not in (63, 70, 77):
        continue
    dx = statistics.median(p for p, _, _ in its.get(DIV, []) if p)
    ch = its.get(CHAOS)
    cx = statistics.median(p for p, _, _ in ch) if ch else None
    S = series['Forbidden Rites']
    S[day] = {'div_ex': dx, 'chaos_per_div': dx / cx if cx else None, 'items': {}}
    for it, xs in its.items():
        pd = [p for _, p, _ in xs if p]
        if pd:
            S[day]['items'][names.get(it, it.split('/')[-1])] = [statistics.median(pd), sum(u for *_, u in xs)]

json.dump({'series': {lg: {str(k): v for k, v in sorted(s.items())} for lg, s in series.items()}, 'cat': cat},
          open(OUT, 'w', encoding='utf-8'))
for lg, s in series.items():
    print(lg, [(d, round(v['div_ex']), v['chaos_per_div'] and round(v['chaos_per_div'], 1), len(v['items'])) for d, v in sorted(s.items())])
