"""Step 6: write ../unique-history.json from ../derived/uniques_merged.json + patterns.json + the source lists.
Run after build.py. Keeps the spec shape: uniques {name: {base, leagues: {league: {day: price_div}}, notes}},
patterns [{pattern, uniques, evidence, confidence}], sources [{title, url, date}], plus helper fields."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DER = os.path.join(ROOT, 'derived')
U = json.load(open(os.path.join(DER, 'uniques_merged.json'), encoding='utf-8'))
CUR = json.load(open(os.path.join(DER, 'currency_by_day.json'), encoding='utf-8'))
WB = json.load(open(os.path.join(DER, 'wayback_sources.json'), encoding='utf-8'))
WEB = json.load(open(os.path.join(HERE, 'web_sources.json'), encoding='utf-8'))
PAT = json.load(open(os.path.join(HERE, 'patterns.json'), encoding='utf-8'))
NOTES = PAT['notes']
SRC_CODE = {'poe.ninja history': 'N', 'poe.ninja history (unit inferred)': 'N~', 'Exile Oracle DB': 'D',
            'poe.ninja via Internet Archive': 'A', 'poe.ninja via Internet Archive (rate from poe2scout)': 'A~',
            'poe2scout': 'S'}
STARTS = {'Dawn of the Hunt': ['0.2', '2025-04-04'], 'Rise of the Abyssal': ['0.3', '2025-08-29'],
          'Fate of the Vaal': ['0.4', '2025-12-12'], 'Runes of Aldur': ['0.5', '2026-05-29'],
          'Forbidden Rites': ['0.5.5', '2026-09-04']}

uniques = {}
for k in PAT['focus']:
    u = U[k]
    leagues, srcs, listings = {}, {}, {}
    for lg, det in u['detail'].items():
        leagues[lg] = {d: round(v['price_div'], 4) for d, v in det.items()}
        srcs[lg] = {d: SRC_CODE[v['src']] for d, v in det.items()}
        listings[lg] = {d: v['listings'] for d, v in det.items()}
    uniques[k] = {
        'base': u['base'], 'leagues': leagues, 'notes': NOTES.get(k, ''),
        'checkpoints': {lg: {c: (row[c]['price_div'] if row.get(c) else None) for c in ['d0', 'd1', 'd3', 'd7', 'd14', 'd28', 'd42', 'end']}
                        | {'end_day': row['end']['day_used'], 'league_finished': row['end']['league_finished'],
                           'peak': row['peak'], 'ratios_vs_d1': row.get('ratios_vs_d1'), 'ratios_vs_d7': row.get('ratios_vs_d7'),
                           'share_of_mirror': row['share_of_mirror'], 'listings': row['listings']}
                        for lg, row in u['checkpoints'].items()},
        'first_seen_poe2scout': u['first_seen'],
        'day_source': srcs, 'listings': listings,
    }

out = {
    'meta': {
        'built': '2026-11-21',
        'what': 'PoE 2 unique prices by league day, in Divine Orbs. Day 0 = launch date (UTC; launches ~20:00 UTC so day 0 is a ~4 h stub), day 1 = the next UTC day.',
        'leagues': STARTS,
        'price_basis': 'Listing-based estimates (poe.ninja and poe2scout both price from public listings, not sales). One value per day: poe.ninja history > Exile Oracle DB > poe.ninja via Internet Archive > poe2scout.',
        'source_codes': {'N': 'poe.ninja item history (sourced)', 'N~': 'poe.ninja history, FR days 0-3, Exalted/Divine unit inferred (estimated)',
                         'A': 'poe.ninja overview copy on the Internet Archive (sourced)', 'A~': 'Internet Archive copy priced in Exalted with no rate; converted with poe2scout daily Ex/Div (estimated)',
                         'S': 'poe2scout history, median of that day (sourced, medium trust)', 'D': 'Exile Oracle DB (sourced)'},
        'thin_rule': 'listings < 3 = unreliable (price-fixing / single troll listing).',
        'not_covered': '0.1 Early Access (no aggregator kept unique prices). FR days 0-2 for most uniques. RoA days ~15-56 only via poe2scout and a few archive copies.',
        'full_data': 'derived/uniques_merged.json has all 140 tracked uniques (this file keeps the focus list).',
    },
    'currency': {'note': 'ex_per_div and mirror_div are daily closes from poe2scout (listing-based); mirror_div = Mirror(Ex)/Divine(Ex).', 'by_league_day': CUR},
    'uniques': uniques,
    'mageblood_vs_temporalis': PAT['mageblood_vs_temporalis'],
    'oracle_rules': PAT['oracle_rules'],
    'patterns': PAT['patterns'],
    'sources': [{k: s[k] for k in ('title', 'url', 'date')} for s in WEB] +
               [{'title': f'{len(WB)} Internet Archive copies of poe.ninja PoE 2 unique overviews (listed in derived/wayback_sources.json)',
                 'url': 'https://web.archive.org/web/2026*/poe.ninja/poe2/api/economy/stash/*', 'date': '2026-05-30 to 2026-09-24'}],
}
json.dump(out, open(os.path.join(ROOT, 'unique-history.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
print('wrote unique-history.json with', len(uniques), 'uniques')
