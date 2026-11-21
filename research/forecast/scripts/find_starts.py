"""Find each launch's first exchange hour (>= 30 markets for that league), like poe2kit.leaguestart.find_start.
FotV / RoA / FR come from the app DB (ls_league). The older launches are binary-searched (a handful of requests,
SPACING seconds apart; every page fetched is kept in cache/raw).
Writes cache/league_starts.json: {league: start_hour}; HC twins share the softcore start.
Usage: python -I find_starts.py <forecast_dir>"""
import gzip, json, os, sqlite3, sys, time, urllib.request

ROOT = sys.argv[1]
RAW = os.path.join(ROOT, 'cache', 'raw')
BASE = 'https://web.poecdn.com/api/currency-exchange/poe2'
UA = 'exile-oracle-personal-toolkit/0.5 (economy research; polite daily samples)'
SPACING = 3.0
# league -> (an hour before it existed, an hour inside its first day)
SEARCH = {'Standard': (1733500000, 1733616000),            # Early Access launch 2024-12-06
          'Dawn of the Hunt': (1743710400, 1743883200),    # 0.2, 2025-04-04
          'Rise of the Abyssal': (1756411200, 1756584000)}  # 0.3, 2025-08-29


def page(h):
    p = os.path.join(RAW, f'{h}.json.gz')
    if os.path.exists(p):
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            return json.load(f)
    body = urllib.request.urlopen(urllib.request.Request(f'{BASE}/{h}', headers={'User-Agent': UA}), timeout=120).read()
    with gzip.open(p, 'wb') as f:
        f.write(body)
    time.sleep(SPACING)
    return json.loads(body)


def count(h, lg):
    return sum(1 for m in page(h).get('markets', []) if m.get('league') == lg)


def find(lg, lo, hi, need=30):
    lo, hi = lo // 3600 * 3600, hi // 3600 * 3600
    while count(hi, lg) < need:      # widen if the first day is later than guessed
        hi += 86400
    while hi - lo > 3600:
        mid = (lo + hi) // 2 // 3600 * 3600
        if count(mid, lg) >= need:
            hi = mid
        else:
            lo = mid
    return hi


out = dict(sqlite3.connect('file:<data folder>/data/poe2kit.db?mode=ro', uri=True).execute(
    'SELECT league, start_hour FROM ls_league'))
for lg, (lo, hi) in SEARCH.items():
    out[lg] = find(lg, lo, hi)
    print(lg, out[lg], flush=True)
out['Hardcore'] = out['Standard']
for lg in list(out):
    if lg not in ('Standard', 'Hardcore'):
        out['HC ' + lg] = out[lg]
json.dump(out, open(os.path.join(ROOT, 'cache', 'league_starts.json'), 'w'), indent=1)
print(out)
