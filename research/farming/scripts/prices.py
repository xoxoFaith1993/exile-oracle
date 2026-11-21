"""Build a Divine-priced curve for every Currency Exchange item, per league and per league phase.

Inputs (all read-only):
- <data folder>/data/poe2kit.db  (?mode=ro): ls_price = hourly prices for league hours 0-167 (days 0-6) of
  Fate of the Vaal, Runes of Aldur, Forbidden Rites; ex_price = the app's own hourly sync (Forbidden Rites days 63-77).
- scripts/cache/<hour>.json.gz: GGG public Currency Exchange digests, days 10-70, two hours per day (fetch_samples.py).
Prices from digests use poe2kit.leaguestart.prices_from_page (volume-weighted pair ratios, the app's own method).

Output: scripts/prices_by_phase.json
  {league: {phase: {item_name: [median_div, n_points, units]}}}, plus 'days': {league: {day: {item: div}}}.
Phases: d0-2 (hours 0-71), week1 (hours 72-167), wk2-3 (days 10/14/21), wk4-8 (days 28-56), late (day 70, + FR days 63-77).
Usage (from the repo root): python research/farming/scripts/prices.py"""
import glob, gzip, json, os, sqlite3, statistics, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, ROOT)
from poe2kit import gamedata, leaguestart  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DB = 'file:<data folder>/data/poe2kit.db?mode=ro'
STARTS = {'Fate of the Vaal': 1765580400, 'Runes of Aldur': 1780095600, 'Forbidden Rites': 1788562800}
PHASE_OF_DAY = lambda d: ('d0-2' if d <= 2 else 'week1' if d <= 9 else 'wk2-3' if d <= 24 else 'wk4-8' if d <= 59 else 'late')

names = {k: v['name'] for k, v in gamedata.load('base_items').items() if v.get('name')}
nm = lambda k: names.get(k, k.rsplit('/', 1)[-1])

# day -> item -> list of (div, units)
pts = {lg: {} for lg in STARTS}
con = sqlite3.connect(DB, uri=True)
for lg, off, it, pdv, u in con.execute('SELECT league, offset_h, item, price_div, units FROM ls_price WHERE price_div > 0'):
    pts[lg].setdefault(off // 24, {}).setdefault(nm(it), []).append((pdv, u or 0))
st = STARTS['Forbidden Rites']
for h, it, pdv, u in con.execute("SELECT hour, item, price_div, units FROM ex_price WHERE league='Forbidden Rites' AND price_div > 0"):
    d = (h - st) // 86400
    pts['Forbidden Rites'].setdefault(d, {}).setdefault(nm(it), []).append((pdv, u or 0))
for p in sorted(glob.glob(os.path.join(HERE, 'cache', '*.json.gz'))):
    with gzip.open(p, 'rt', encoding='utf-8') as f:
        page = json.load(f)
    lg = page['league']
    prices, ex_per_div = leaguestart.prices_from_page(page, lg)
    if not ex_per_div:
        continue
    for it, (pex, u) in prices.items():
        pts[lg].setdefault(page['day'], {}).setdefault(nm(it), []).append((pex / ex_per_div, u))

out = {'phases': {}, 'days': {}}
for lg, days in pts.items():
    out['days'][lg] = {}
    ph = {}
    for d, items in sorted(days.items()):
        out['days'][lg][d] = {}
        for n, v in items.items():
            good = [x for x, u in v if u >= 3] or [x for x, u in v]
            out['days'][lg][d][n] = statistics.median(good)
            ph.setdefault(PHASE_OF_DAY(d), {}).setdefault(n, []).append((statistics.median(good), sum(u for _, u in v)))
    out['phases'][lg] = {p: {n: [round(statistics.median(x for x, _ in v), 6), len(v), round(sum(u for _, u in v))]
                             for n, v in items.items()} for p, items in ph.items()}
json.dump(out, open(os.path.join(HERE, 'prices_by_phase.json'), 'w', encoding='utf-8'))
for lg in out['phases']:
    print(lg, {p: len(v) for p, v in out['phases'][lg].items()})
