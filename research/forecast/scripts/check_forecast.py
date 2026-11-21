"""Smoke test for forecast.py + forecast-model.json: ordered quantiles, fallbacks, no exceptions on odd input.
Usage: python -I check_forecast.py <forecast_dir>"""
import json, os, sys

sys.path.insert(0, sys.argv[1])
import forecast as fc  # noqa: E402

m = fc.load(os.path.join(sys.argv[1], 'forecast-model.json'))
o = fc.Oracle(m)
bad = 0
cases = [('Exalted Orb', 0.5, 0.02, None), ('Exalted Orb', 10, 0.004, -30), ('Orb of Annulment', 9, 0.3, 45),
         ("Hinekora's Lock", 20, 900, 60), ('Chaos Orb', 30, 0.1, 5), ('Fracturing Orb', 150, 8, None),
         ('no such item', 5, 1.0, None), ('no such item', 5, 1.0, None, 'Essences'), ('perfect exalted orb', 3, 1.2, 10)]
for c in cases:
    r = o.forecast(c[0], c[1], c[2], c[3], category=c[4] if len(c) > 4 else None)
    for h, q in r['horizons'].items():
        v = [q[k] for k in fc.QS]
        if v != sorted(v) or v[0] <= 0:
            bad += 1
            print('BAD ORDER', c, h, v)
    print(c[:2], r['confidence'], {h: (q['p10'], q['median'], q['p90']) for h, q in r['horizons'].items()}, r['notes'][:1])
for it in list(m['items'])[:400]:
    for d in (0, 2, 6, 13, 40, 90, 200):
        r = o.forecast(it, d, 1.0, 20 if d >= 7 else None)
        for h, q in r['horizons'].items():
            v = [q[k] for k in fc.QS]
            if v != sorted(v):
                bad += 1
print('problems:', bad)
