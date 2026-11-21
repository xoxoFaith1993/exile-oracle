"""Fetch sampled hourly digests of GGG's public Currency Exchange history for league days 10-70 of the last
three PoE 2 launches (days 0-6 are already in the app DB as ls_price; FR days 63-77 are in ex_price).
Endpoint: https://web.poecdn.com/api/currency-exchange/poe2/<unix hour>  (public, no login; see poe2kit/ggg_exchange.py)
Cache: cache/<hour>.json.gz holding only that league's softcore markets, so nothing is fetched twice.
Polite: one request at a time, 2.5 s apart.
Usage: python -I fetch_samples.py <cache_dir>"""
import gzip, json, os, sys, time, urllib.request

CACHE = sys.argv[1]
BASE = 'https://web.poecdn.com/api/currency-exchange/poe2'
STARTS = {'Fate of the Vaal': 1765580400, 'Runes of Aldur': 1780095600, 'Forbidden Rites': 1788562800}
DAYS = [10, 14, 21, 28, 35, 42, 49, 56, 70]
HOURS = [6, 18]          # two hours per sampled day, 12 h apart, to damp single-hour noise
LAST = 1795240000        # nothing after today
for lg, st in STARTS.items():
    for d in DAYS:
        for hh in HOURS:
            h = st + d * 86400 + hh * 3600
            if h > LAST:
                continue
            p = os.path.join(CACHE, f'{h}.json.gz')
            if os.path.exists(p):
                continue
            req = urllib.request.Request(f'{BASE}/{h}', headers={'User-Agent': 'poe2-personal-toolkit/0.5 (economy research)'})
            for attempt in range(3):
                try:
                    body = urllib.request.urlopen(req, timeout=90).read()
                    dd = json.loads(body)
                    keep = {'hour': h, 'league': lg, 'day': d, 'offset_h': d * 24 + hh,
                            'markets': [m for m in dd.get('markets', []) if m.get('league') == lg]}
                    with gzip.open(p, 'wt', encoding='utf-8') as f:
                        json.dump(keep, f)
                    print(lg, d, hh, h, len(body), len(keep['markets']), flush=True)
                    break
                except Exception as e:
                    print(lg, d, hh, h, 'ERR', e, flush=True)
                    time.sleep(10)
            time.sleep(2.5)
print('DONE')
