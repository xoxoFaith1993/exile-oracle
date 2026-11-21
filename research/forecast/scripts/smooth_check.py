"""Does making the forecast path consistent (no zig-zag) cost accuracy? (the author, 2026-11-21: the fan zig-zagged,
e.g. +1 d 88, +3 d 114, +7 d 72, +14 d 92 div.)

Reads the leave-one-launch-out backtest (cache/backtest_rows.csv.gz: per item, league day and horizon, the model's
log-change quantiles and what really happened), applies poe2kit.forecast.smooth() to each item-day's four horizons,
and compares: median absolute error of the middle line, how often the 10-90% band held, direction hit rate.
Usage: python -I smooth_check.py <forecast_dir> <app_dir>"""
import csv
import gzip
import math
import os
import statistics
import sys

sys.path.insert(0, sys.argv[2])
from poe2kit.forecast import smooth, QS  # noqa: E402

rows = {}
with gzip.open(os.path.join(sys.argv[1], 'cache', 'backtest_rows.csv.gz'), 'rt') as f:
    for r in csv.DictReader(f):
        if r['set'] != 'loo':
            continue
        rows.setdefault((r['league'], r['item'], r['day']), {})[int(r['h'])] = r

stats = {k: {'err': [], 'hold': [], 'dir': [], 'zig': 0, 'n': 0} for k in ('as is', 'smoothed')}
for key, hs in rows.items():
    if len(hs) < 4:
        continue
    raw = {h: {q: math.exp(float(hs[h]['q' + q[1:] if q != 'median' else 'q50'])) for q in QS} for h in hs}
    sm = smooth({h: dict(v) for h, v in raw.items()})
    for name, out in (('as is', raw), ('smoothed', sm)):
        s = stats[name]
        med = [math.log(out[h]['median']) for h in sorted(out)]
        s['zig'] += any((b - a) * (c - b) < -1e-6 for a, b, c in zip([0] + med, med, med[1:]))
        s['n'] += 1
        for h in out:
            a = float(hs[h]['actual_logchg'])
            m = math.log(out[h]['median'])
            s['err'].append(abs(a - m))
            s['hold'].append(math.log(out[h]['p10']) <= a <= math.log(out[h]['p90']))
            if abs(m) >= math.log(1.1):
                s['dir'].append((a > 0) == (m > 0))
for name, s in stats.items():
    print(f"{name:9} item-days {s['n']:7}  zig-zag paths {100 * s['zig'] / s['n']:5.1f}%  "
          f"median error {100 * (math.exp(statistics.median(s['err'])) - 1):5.1f}%  "
          f"10-90% band held {100 * sum(s['hold']) / len(s['hold']):5.1f}%  "
          f"direction right (10%+ calls) {100 * sum(s['dir']) / max(1, len(s['dir'])):5.1f}% of {len(s['dir'])}")
