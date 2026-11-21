import json, statistics, sys
D = json.load(open(sys.argv[1], encoding='utf-8'))
S, cat = D['series'], D['cat']
PH = [('day 1-3', '0', '2'), ('week 1', '2', '6'), ('week 2-3', '6', '21'), ('week 4+', '21', '56'), ('week 1->6', '6', '42'), ('day1->wk6', '0', '42')]
MINU = 5


def p(lg, d, n):
    x = S[lg].get(d, {}).get('items', {}).get(n)
    return x if x and x[0] and x[1] >= MINU else None


out = {'cat': {}, 'items': {}}
allnames = set()
for lg in S:
    for d in S[lg].values():
        allnames |= set(d['items'])
for n in allnames:
    c = cat.get(n, 'Other')
    for ph, a, b in PH:
        ch = {}
        for lg in S:
            pa, pb = p(lg, a, n), p(lg, b, n)
            if pa and pb:
                ch[lg] = pb[0] / pa[0] - 1
        if ch:
            out['items'].setdefault(n, {'cat': c})[ph] = ch
            for lg, v in ch.items():
                out['cat'].setdefault(c, {}).setdefault(ph, {}).setdefault(lg, []).append(v)
print('CATEGORY median change in DIVINE terms (n items)')
for c, phs in sorted(out['cat'].items()):
    line = []
    for ph, *_ in PH:
        lgs = phs.get(ph, {})
        line.append(ph + ': ' + ', '.join(f"{lg.split()[0][:4]} {statistics.median(v)*100:+.0f}% ({len(v)})" for lg, v in lgs.items()))
    print(c); [print('   ', l) for l in line]
json.dump(out, open(sys.argv[2], 'w', encoding='utf-8'))
