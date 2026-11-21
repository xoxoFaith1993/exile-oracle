"""Step 3: poe2scout.com public read-only JSON API (no login). Listing-based unique price history (points every
~12 h) for every finished/current league it keeps: 0.2, 0.3, 0.4, 0.5, 0.5.5. Plus daily Divine (in Ex) and Mirror
(in Ex) stats for the Divine:Mirror ratio. 2.5 s between requests; cached in ../cache."""
import json, os, urllib.parse
import fetchlib as f

API = 'https://api.poe2scout.com/poe2/Leagues'
OUT = os.path.join(f.CACHE, 'scout')
os.makedirs(OUT, exist_ok=True)
LEAGUES = {  # name: (start date, end date for the daily-stats window)
    'Dawn of the Hunt': ('2025-04-04', '2025-08-29'),
    'Rise of the Abyssal': ('2025-08-29', '2025-12-12'),
    'Fate of the Vaal': ('2025-12-12', '2026-05-29'),
    'Runes of Aldur': ('2026-05-29', '2026-11-21'),
    'Forbidden Rites': ('2026-09-04', '2026-11-21'),
}
NAMES = json.load(open(os.path.join(os.path.dirname(__file__), 'unique_names.json')))


def lq(lg):
    return urllib.parse.quote(lg)


if __name__ == '__main__':
    result = {}
    for lg, (st, en) in LEAGUES.items():
        s, items = f.get_json(f'{API}/{lq(lg)}/Items')
        items = items or []
        sel = [i for i in items if i.get('Name') in NAMES and i['CategoryApiId'] not in ('currency',)]
        lres = {'items': {}, 'daily': {}}
        for it in sel:
            s, h = f.get_json(f"{API}/{lq(lg)}/Items/{it['ItemId']}/History?logCount=3000&referenceCurrency=divine")
            lres['items'][str(it['ItemId'])] = {'name': it['Name'], 'base': it['Type'], 'text': it['Text'],
                                                'history': (h or {}).get('PriceHistory', []), 'hasMore': (h or {}).get('HasMore')}
            print(lg, it['ItemId'], it['Text'], len((h or {}).get('PriceHistory', [])))
        cur = {i['ApiId']: i['ItemId'] for i in items if i['CategoryApiId'] == 'currency' and i.get('ApiId') in ('divine', 'mirror')}
        for k, iid in cur.items():
            s, d = f.get_json(f"{API}/{lq(lg)}/Items/{iid}/DailyStatsHistory?dayCount=200&endDate={en}")
            lres['daily'][k] = (d or {}).get('DailyStats', [])
            print(lg, k, len(lres['daily'][k]))
        result[lg] = lres
    json.dump(result, open(os.path.join(OUT, 'scout_histories.json'), 'w'))
