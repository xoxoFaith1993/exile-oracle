"""Fetch a few hourly digests of GGG's public Currency Exchange history (same endpoint the app syncs), weekly samples."""
import json, os, sys, time, urllib.request
OUT = sys.argv[1]
BASE = 'https://web.poecdn.com/api/currency-exchange/poe2'
STARTS = {'Fate of the Vaal': 1765580400, 'Runes of Aldur': 1780095600, 'Forbidden Rites': 1788562800}
DAYS = {'Fate of the Vaal': [10, 14, 21, 28, 42, 56, 70],
        'Runes of Aldur': [10, 14, 21, 28, 42, 56, 70],
        'Forbidden Rites': [10, 14, 21, 28, 42, 56]}
for lg, st in STARTS.items():
    for d in DAYS[lg]:
        h = st + d * 86400 + 12 * 3600
        p = os.path.join(OUT, f'{h}.json')
        if os.path.exists(p):
            continue
        req = urllib.request.Request(f'{BASE}/{h}', headers={'User-Agent': 'poe2-personal-toolkit/0.3 (economy research)'})
        try:
            body = urllib.request.urlopen(req, timeout=60).read()
            json.loads(body)
            open(p, 'wb').write(body)
            print(lg, d, h, len(body))
        except Exception as e:
            print(lg, d, h, 'ERR', e)
        time.sleep(2.5)
