"""Daily price paths of every exchange item in the last three launches, for the price forecast chart's faint
past-launch lines (the author, 2026-11-21: most items showed only the fan; the Oracle's curves cover 42 key items).

Input:  <forecast>/cache/prices-value.db (build_dataset.py <dir> value: each item priced from the market with the
        most VALUE traded, the app's corrected method): day(league, day, item, price_div)
Output: datapack/forecast-paths.json
  {"leagues": [three launch names], "max_day": N, "items": {name: [[price or null per day] per league]}}
Prices in Divine Orbs, 3 significant figures, one per league day (day 0 = launch day).
Usage: python -I paths.py <forecast_dir> <out.json> [prices db file name, default prices-value.db]"""
import json
import math
import sqlite3
import sys

LEAGUES = ['Fate of the Vaal', 'Runes of Aldur', 'Forbidden Rites']   # the same launches as the Oracle's curves
MAX_DAY = 140


def sig3(x):
    if not x or x <= 0:
        return None
    d = 3 - int(math.floor(math.log10(x))) - 1
    return round(x, max(0, d)) if d > 0 else float(round(x))


def main(root, out, dbname='prices-value.db'):
    db = sqlite3.connect(f'file:{root}/cache/{dbname}?mode=ro', uri=True)
    names = dict(db.execute('SELECT item, name FROM item'))
    items = {}
    for league_i, lg in enumerate(LEAGUES):
        for item, day, p in db.execute('SELECT item, day, price_div FROM day WHERE league=? AND day<=?', (lg, MAX_DAY)):
            n = names.get(item)
            if not n or p is None:
                continue
            row = items.setdefault(n, [[None] * (MAX_DAY + 1) for _ in LEAGUES])
            row[league_i][day] = sig3(p)
    for n, rows in items.items():   # trim trailing gaps
        for r in rows:
            while r and r[-1] is None:
                r.pop()
    keep = {n: rows for n, rows in items.items() if sum(1 for r in rows for v in r if v is not None) >= 5}
    json.dump({'leagues': LEAGUES, 'max_day': MAX_DAY, 'items': keep,
               'note': 'Daily price (Divine Orbs) by league day in each launch, from GGG Currency Exchange history.'},
              open(out, 'w', encoding='utf-8'), separators=(',', ':'))
    print(f'{len(keep)} items -> {out}')


if __name__ == '__main__':
    main(*sys.argv[1:4])
