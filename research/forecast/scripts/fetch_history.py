"""Fetch GGG's public Currency Exchange history (documented Public API, no login) as daily samples for every league
it covers, from the start of the history (Dec 2024) up to where the app's own hourly sync begins (2026-11-06).

Endpoint: GET https://web.poecdn.com/api/currency-exchange/poe2/<unix hour>  ->  {"next_change_id", "markets": [...]}
Each page is one hour for ALL leagues (Standard, Hardcore, challenge, HC challenge, private/event leagues).

Sampling plan (one request at a time, SPACING seconds apart):
  * every day at 21:00 UTC (busy hour: EU evening, US afternoon);
  * plus 09:00 UTC on days 0-20 of each launch, where prices move fastest.
Cache: <cache>/raw/<hour>.json.gz = the full page, gzipped, so nothing is ever fetched twice.
Also imports the 20 pages the market research (R7) already fetched, if found.

Usage: python -I fetch_history.py <forecast_dir> [--dry]
"""
import gzip, json, os, shutil, sys, time, urllib.request

ROOT = sys.argv[1]
RAW = os.path.join(ROOT, 'cache', 'raw')
os.makedirs(RAW, exist_ok=True)
BASE = 'https://web.poecdn.com/api/currency-exchange/poe2'
UA = 'exile-oracle-personal-toolkit/0.5 (economy research; polite daily samples)'
SPACING = 3.0
FIRST = 1733529600            # 2024-12-07 00:00 UTC (history begins 2024-12-06)
LAST = 1794002400             # 2026-11-06 02:00 UTC: the app's ex_price sync starts here
# Approximate launch hours (UTC); exact starts are found later from the data (build_dataset.py)
LAUNCHES = {'EA launch 0.1 (Standard)': 1733511600, 'Dawn of the Hunt': 1743796800,
            'Rise of the Abyssal': 1756497600, 'Fate of the Vaal': 1765580400,
            'Runes of Aldur': 1780095600, 'Forbidden Rites': 1788562800}
R7_PAGES = os.environ.get('R7_PAGES', '')


def plan():
    hours = []
    for st in LAUNCHES.values():                       # launch windows first
        d0 = st // 86400 * 86400
        for d in range(0, 22):
            for hh in (9, 21):
                h = d0 + d * 86400 + hh * 3600
                if st <= h <= LAST:
                    hours.append(h)
    h = FIRST + 21 * 3600
    while h <= LAST:
        hours.append(h)
        h += 86400
    seen, out = set(), []
    for h in hours:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def path(h):
    return os.path.join(RAW, f'{h}.json.gz')


def import_r7():
    n = 0
    if R7_PAGES and os.path.isdir(R7_PAGES):
        for f in os.listdir(R7_PAGES):
            if f.endswith('.json') and f[:-5].isdigit():
                p = path(int(f[:-5]))
                if not os.path.exists(p):
                    with open(os.path.join(R7_PAGES, f), 'rb') as src, gzip.open(p, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                    n += 1
    return n


def main():
    print('imported R7 pages:', import_r7(), flush=True)
    todo = [h for h in plan() if not os.path.exists(path(h))]
    print('to fetch:', len(todo), flush=True)
    if '--dry' in sys.argv:
        return
    for i, h in enumerate(todo):
        for attempt in range(3):
            try:
                req = urllib.request.Request(f'{BASE}/{h}', headers={'User-Agent': UA})
                body = urllib.request.urlopen(req, timeout=120).read()
                d = json.loads(body)
                tmp = path(h) + '.tmp'
                with gzip.open(tmp, 'wb', compresslevel=6) as f:
                    f.write(body)
                os.replace(tmp, path(h))
                if i % 20 == 0:
                    print(i, len(todo), h, len(body), len(d.get('markets', [])), flush=True)
                break
            except Exception as e:
                print(i, h, 'ERR', e, flush=True)
                time.sleep(15 * (attempt + 1))
        time.sleep(SPACING)
    print('DONE', flush=True)


if __name__ == '__main__':
    main()
