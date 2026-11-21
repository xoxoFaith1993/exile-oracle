"""Fetch GGG's public Currency Exchange hourly digests for the first 72 h (plus 5 h before the app's start_hour)
of the three launches. The app's DB (ls_price) already holds DERIVED prices for hours 0-167 but not the raw
markets (low/high ratio, stock), and nothing before start_hour. This fills that gap.
Cache: cache/<hour>.json.gz holding only that league's softcore markets, so nothing is fetched twice.
Polite: 2.5 s between requests, one request at a time.
Usage: python -I fetch_hours.py <cache_dir>"""
import gzip, json, os, sys, time, urllib.request

CACHE = sys.argv[1]
BASE = 'https://web.poecdn.com/api/currency-exchange/poe2'
STARTS = {'Fate of the Vaal': 1765580400, 'Runes of Aldur': 1780095600, 'Forbidden Rites': 1788562800}
PRE, POST = 5, 72
for lg, st in STARTS.items():
    for off in range(-PRE, POST):
        h = st + off * 3600
        p = os.path.join(CACHE, f'{h}.json.gz')
        if os.path.exists(p):
            continue
        req = urllib.request.Request(f'{BASE}/{h}', headers={'User-Agent': 'poe2-personal-toolkit/0.5 (economy research)'})
        for attempt in range(3):
            try:
                body = urllib.request.urlopen(req, timeout=90).read()
                d = json.loads(body)
                keep = {'hour': h, 'league': lg, 'offset_h': off, 'next_change_id': d.get('next_change_id'),
                        'raw_bytes': len(body), 'all_markets': len(d.get('markets', [])),
                        'markets': [m for m in d.get('markets', []) if m.get('league') == lg]}
                with gzip.open(p, 'wt', encoding='utf-8') as f:
                    json.dump(keep, f)
                print(lg, off, h, len(body), len(keep['markets']), flush=True)
                break
            except Exception as e:
                print(lg, off, h, 'ERR', e, flush=True)
                time.sleep(10)
        time.sleep(2.5)
print('DONE')
