"""Step 5 helper: print markdown checkpoint tables + an automatic shape classification from ../derived/uniques_merged.json.
Usage: python tables.py [focus|all|shapes|first|mirror|currency]"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
U = json.load(open(os.path.join(ROOT, 'derived', 'uniques_merged.json'), encoding='utf-8'))
CUR = json.load(open(os.path.join(ROOT, 'derived', 'currency_by_day.json'), encoding='utf-8'))
SHORT = {'Dawn of the Hunt': '0.2 DotH', 'Rise of the Abyssal': '0.3 RotA', 'Fate of the Vaal': '0.4 FotV',
         'Runes of Aldur': '0.5 RoA', 'Forbidden Rites': '0.5.5 FR'}
COLS = ['d0', 'd1', 'd3', 'd7', 'd14', 'd28', 'd42', 'end']


def fmt(x):
    if x is None:
        return '-'
    p = x['price_div']
    s = f'{p:,.0f}' if p >= 100 else (f'{p:.1f}' if p >= 1 else f'{p:.2f}')
    n = x.get('listings')
    if n is not None and n < 3:
        s += '*'
    return s


def shape(row):
    r = row.get('ratios_vs_d1') or {}
    d3 = (row.get('d3') or row.get('d1') or {}).get('price_div')
    end = row['end']['price_div']
    peak = row['peak']
    if not d3:
        return 'n/a'
    up = peak['price_div'] / d3
    if peak['day'] <= 10 and end / peak['price_div'] < 0.3:
        return f'early peak (d{peak["day"]}) then crash'
    if end / d3 >= 3 or (up >= 4 and peak['day'] >= 14 and end / d3 >= 1.5):
        return f'climber (peak d{peak["day"]}, x{up:.1f} over d3)'
    if end / d3 <= 0.3:
        return 'crasher'
    if up >= 3 and end / peak['price_div'] < 0.5:
        return f'mid spike (d{peak["day"]}) then fade'
    return 'roughly flat'


def table(keys):
    print('| Unique | League | ' + ' | '.join(COLS) + ' | peak (day) | end/d1 |')
    print('|' + '---|' * (len(COLS) + 4))
    for k in keys:
        if k not in U:
            continue
        for lg, row in U[k]['checkpoints'].items():
            r = row.get('ratios_vs_d1') or {}
            print(f'| {k} | {SHORT[lg]} | ' + ' | '.join(fmt(row.get(c)) for c in COLS) +
                  f" | {fmt(row['peak'])} (d{row['peak']['day']}) | {r.get('end') if r.get('end') is not None else '-'} |")


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'all'
    keys = sys.argv[2:] or sorted(U)
    if what == 'table':
        table(keys)
    elif what == 'shapes':
        for k in keys:
            if k in U:
                print(k, '|', '; '.join(f'{SHORT[lg]}: {shape(r)}' for lg, r in U[k]['checkpoints'].items()))
    elif what == 'first':
        for k in keys:
            if k in U and U[k]['first_seen']:
                print(k, '|', '; '.join(f"{SHORT[lg]} {v['time_utc']} (d{v['league_day']}) {v['price_div']} div n={v['listings']}"
                                       for lg, v in U[k]['first_seen'].items()))
    elif what == 'currency':
        for lg, c in CUR.items():
            print(SHORT[lg], {d: c.get(str(d)) for d in [0, 1, 2, 3, 7, 14, 28, 42, 56, 70, 90, 120, 150]})
