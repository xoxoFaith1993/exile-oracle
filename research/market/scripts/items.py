import json, statistics, sys
D = json.load(open(sys.argv[1], encoding='utf-8'))
P = json.load(open(sys.argv[2], encoding='utf-8'))
S, cat = D['series'], D['cat']
mode = sys.argv[3]
if mode == 'key':
    names = sys.argv[4].split('|')
    for n in names:
        print('==', n, cat.get(n))
        for lg in S:
            row = []
            for d in ['0', '1', '2', '4', '6', '10', '14', '21', '28', '42', '56', '70', '77']:
                x = S[lg].get(d, {}).get('items', {}).get(n)
                if x:
                    row.append(f"d{d}:{x[0]:.3g}" + ('' if x[1] >= 5 else '*'))
            print('  ', lg[:4], ' '.join(row))
elif mode == 'movers':
    ph = sys.argv[4]
    res = []
    for n, v in P['items'].items():
        ch = v.get(ph)
        if not ch or len(ch) < 2:
            continue
        vals = list(ch.values())
        if all(x > 0.5 for x in vals) or all(x < -0.5 for x in vals):
            # day-0 / day-6 price must be >= 0.02 div in each league to matter
            res.append((statistics.median(vals), n, v['cat'], {k[:4]: round(x * 100) for k, x in ch.items()}))
    res.sort()
    for r in res[:40]:
        print(f"{r[0]*100:+6.0f}%  {r[1]} [{r[2]}] {r[3]}")
    print('...')
    for r in res[-40:]:
        print(f"{r[0]*100:+6.0f}%  {r[1]} [{r[2]}] {r[3]}")
elif mode == 'top':
    # most valuable items on day 42 of each league, by div
    for lg in S:
        d = S[lg].get(sys.argv[4], {}).get('items', {})
        top = sorted(((v[0], n) for n, v in d.items() if v[1] >= 2), reverse=True)[:25]
        print(lg, [(n, round(p, 2), cat.get(n)) for p, n in top])
