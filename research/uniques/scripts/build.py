"""Step 4: merge every source into one daily Divine series per unique per league, compute the checkpoint table
(d0/1/3/7/14/28/42/end), ratios, Mirror-relative prices, supply (listings) and first copies; write
../derived/*.json for report.py. Only reads cached files + the app DB (read-only, ?mode=ro)."""
import collections
import datetime as dt
import json
import os
import sqlite3
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, 'cache')
DER = os.path.join(ROOT, 'derived')
os.makedirs(DER, exist_ok=True)

STARTS = {  # league: (patch, start date UTC; launch ~20:00 UTC that day, so day 0 is a ~4 h stub)
    'Dawn of the Hunt': ('0.2', '2025-04-04'), 'Rise of the Abyssal': ('0.3', '2025-08-29'),
    'Fate of the Vaal': ('0.4', '2025-12-12'), 'Runes of Aldur': ('0.5', '2026-05-29'),
    'Forbidden Rites': ('0.5.5', '2026-09-04')}
ENDS = {'Dawn of the Hunt': '2025-08-28', 'Rise of the Abyssal': '2025-12-11', 'Fate of the Vaal': '2026-05-28'}
TODAY = dt.date(2026, 11, 21)
CHECK = [0, 1, 3, 7, 14, 28, 42]
TOL = {0: 0, 1: 0, 3: 1, 7: 1, 14: 2, 28: 3, 42: 4}
PRIO = {'poe.ninja history': 0, 'poe.ninja history (unit inferred)': 0, 'Exile Oracle DB': 1,
        'poe.ninja via Internet Archive': 2, 'poe.ninja via Internet Archive (rate from poe2scout)': 2, 'poe2scout': 3}


def d(s):
    return dt.date.fromisoformat(s[:10])


def lday(lg, date):
    return (date - d(STARTS[lg][1])).days


def key_for(name, base, corrupted=False, multi=False):
    k = name
    if base and base.startswith(('Runemastered', 'Runeforged')):
        k += ' [Runemastered]'
    elif multi and base:
        k += f' ({base})'
    if corrupted:
        k += ' [corrupted]'
    return k


def main():
    series = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list)))
    bases = collections.defaultdict(set)
    names = set(json.load(open(os.path.join(HERE, 'unique_names.json'), encoding='utf-8')))

    # base multiplicity (Grand Spectrum Emerald/Ruby/Sapphire ...) from the poe.ninja overview
    ov = json.load(open(os.path.join(CACHE, 'ninja', 'overview_rows.json'), encoding='utf-8'))
    plain = collections.defaultdict(set)
    for r in ov:
        if not (r['base'] or '').startswith(('Runemastered', 'Runeforged')):
            plain[r['name']].add(r['base'])
    multi = {n for n, b in plain.items() if len(b) > 1}
    for r in ov:
        bases[key_for(r['name'], r['base'], r['corrupted'], r['name'] in multi)].add(r['base'])

    # 1. poe2scout (0.2-0.5.5): listing-based, points every ~12 h, in Divine
    scout = json.load(open(os.path.join(CACHE, 'scout', 'scout_histories.json'), encoding='utf-8'))
    first_seen = collections.defaultdict(dict)
    currency = collections.defaultdict(dict)
    for lg, L in scout.items():
        launch = dt.datetime.fromisoformat(STARTS[lg][1] + 'T20:00:00')
        for iid, it in L['items'].items():
            k = key_for(it['name'], it['base'], False, it['name'] in multi)
            bases[k].add(it['base'])
            pts = sorted(it['history'], key=lambda p: p['Time'])
            if pts:
                p0 = pts[0]
                first_seen[k][lg] = {'time_utc': p0['Time'][:16] + 'Z',
                                     'league_day': round((dt.datetime.fromisoformat(p0['Time'][:19]) - launch).total_seconds() / 86400, 2),
                                     'price_div': round(p0['Price'], 2), 'listings': p0.get('Quantity'), 'source': 'poe2scout'}
            byday = collections.defaultdict(list)
            for p in pts:
                byday[lday(lg, d(p['Time']))].append(p)
            for day, ps in byday.items():
                series[k][lg][day].append((st.median(p['Price'] for p in ps), max(p.get('Quantity') or 0 for p in ps), 'poe2scout'))
        dv = {x['Time']: x for x in L['daily'].get('divine', [])}
        mr = {x['Time']: x for x in L['daily'].get('mirror', [])}
        for t, x in dv.items():
            day = lday(lg, d(t))
            rec = currency[lg].setdefault(day, {})
            if x.get('Close'):
                rec['ex_per_div'] = round(x['Close'], 1)
                if t in mr and mr[t].get('Close'):
                    rec['mirror_div'] = round(mr[t]['Close'] / x['Close'], 0)
                    rec['mirror_listings'] = mr[t].get('Volume')

    # 2. poe.ninja item history (RoA from ~day 57, FR from day 4), Divine, daily
    nh = json.load(open(os.path.join(CACHE, 'ninja', 'histories.json'), encoding='utf-8'))
    for v in nh.values():
        m = v['meta']
        k = key_for(m['name'], m['base'], m['corrupted'], m['name'] in multi)
        hist = v['history'] or []
        later = [float(p['value']) for p in hist if lday(m['league'], TODAY - dt.timedelta(days=p['daysAgo'])) >= 4][:3]
        anchor = st.median(later) if later else None
        for p in hist:
            date = TODAY - dt.timedelta(days=p['daysAgo'])
            day = lday(m['league'], date)
            val = float(p['value'])
            # poe.ninja quoted PoE 2 in Exalted for the first days of a league (FR: archived Sep 6-7 copies have
            # core.primary 'exalted'), and its history keeps SOME of those days in Exalted. For FR days 0-3 pick the
            # unit (raw = Div, or raw / Ex-per-Div) that lands closer to the item's day 4-6 Divine price.
            if m['league'] == 'Forbidden Rites' and day <= 3:
                rate = currency[m['league']].get(day, {}).get('ex_per_div')
                if not rate or not anchor or val <= 0:
                    continue
                import math
                if abs(math.log(val / rate / anchor)) < abs(math.log(val / anchor)):
                    val /= rate
                series[k][m['league']][day].append((val, p.get('count'), 'poe.ninja history (unit inferred)'))
                continue
            series[k][m['league']][day].append((val, p.get('count'), 'poe.ninja history'))

    # 3. Internet Archive copies of poe.ninja overviews (explicit unit + rate in core)
    caps = json.load(open(os.path.join(CACHE, 'wayback', 'captures.json'), encoding='utf-8'))
    wb_sources = []
    for c in caps:
        if 'overview' not in c['url']:
            continue
        tag = 'poe.ninja via Internet Archive'
        lg = 'Runes of Aldur' if 'Runes+of+Aldur' in c['url'] else 'Forbidden Rites'
        ts = c['timestamp']
        date = dt.date(int(ts[:4]), int(ts[4:6]), int(ts[6:8]))
        core = c['data'].get('core', {})
        prim, rates = core.get('primary'), core.get('rates', {})
        if prim == 'exalted':
            conv = rates.get('divine')
            if conv is None:  # FR Sep 6-7 copies carry no rate: use poe2scout's daily Ex/Div close
                rec = currency[lg].get(lday(lg, date), {})
                conv = 1 / rec['ex_per_div'] if rec.get('ex_per_div') else None
                tag = 'poe.ninja via Internet Archive (rate from poe2scout)'
        else:
            conv = 1.0
        if conv is None:
            continue
        wb_sources.append({'title': f"Internet Archive copy of poe.ninja PoE 2 {c['url'].split('type=')[1]} overview ({lg})",
                           'url': c['wayback'], 'date': date.isoformat()})
        for ln in c['data'].get('lines', []):
            if ln['name'] not in names:
                continue
            k = key_for(ln['name'], ln.get('baseType'), ln.get('corrupted'), ln['name'] in multi)
            series[k][lg][lday(lg, date)].append((ln['primaryValue'] * conv, ln.get('listingCount'), tag))

    # 4. the app's own DB (read-only): today's Forbidden Rites values
    con = sqlite3.connect('file:<data folder>/data/poe2kit.db?mode=ro', uri=True)
    for day, lg, name, base, val, n in con.execute('SELECT day, league, name, base, value_div, listings FROM unique_daily'):
        if name in names and val and lg in STARTS:
            # unique_daily has no corrupted flag: match the value against today's poe.ninja corrupted line
            corr = any(r['league'] == lg and r['name'] == name and r['corrupted'] and abs((r['value'] or 0) - val) < 0.01 for r in ov)
            k = key_for(name, base, corr, name in multi)
            series[k][lg][lday(lg, d(day))].append((val, n, 'Exile Oracle DB'))

    def pick(entries):
        e = sorted(entries, key=lambda x: PRIO[x[2]])
        best = [x for x in e if x[2] == e[0][2]]
        return {'price_div': round(st.median(x[0] for x in best), 4), 'listings': max((x[1] or 0) for x in best),
                'src': best[0][2], 'others': {x[2]: round(x[0], 3) for x in e if x[2] != best[0][2]}}

    def at(daily, k, tol):
        for off in sorted(range(-tol, tol + 1), key=abs):
            if k + off in daily:
                return daily[k + off], k + off
        return None, None

    out = {}
    for k in sorted(series):
        if k.split(' [')[0].split(' (')[0] not in names:
            continue
        leagues, detail, ck = {}, {}, {}
        for lg in STARTS:
            if lg not in series[k]:
                continue
            daily = {day: pick(v) for day, v in sorted(series[k][lg].items()) if day >= 0}
            # glitch filter (from day 7 on, when prices are settled): drop a day that is >5x off the median of
            # the 3 days either side (e.g. a poe2scout Mageblood point of 1.6 div between 114 and 110)
            for day in [x for x in daily if x >= 7]:
                nb = [daily[x]['price_div'] for x in daily if x != day and abs(x - day) <= 3]
                if len(nb) >= 2 and daily[day]['price_div'] > 0 and st.median(nb) > 0:
                    r = daily[day]['price_div'] / st.median(nb)
                    if r > 5 or r < 0.2:
                        daily[day]['dropped_glitch'] = True
            daily = {x: v for x, v in daily.items() if not v.get('dropped_glitch')}
            if not daily:
                continue
            leagues[lg] = {str(day): x['price_div'] for day, x in daily.items()}
            detail[lg] = {str(day): x for day, x in daily.items()}
            row = {}
            for c in CHECK:
                x, used = at(daily, c, TOL[c])
                row[f'd{c}'] = None if x is None else {'price_div': x['price_div'], 'day_used': used, 'listings': x['listings'], 'src': x['src']}
            last = max(daily)
            row['end'] = {'price_div': daily[last]['price_div'], 'day_used': last, 'listings': daily[last]['listings'],
                          'src': daily[last]['src'], 'league_finished': lg in ENDS}
            ok = [dd for dd in daily if (daily[dd]['listings'] or 0) >= 3] or list(daily)
            peak = max(ok, key=lambda dd: daily[dd]['price_div'])
            low = min([dd for dd in ok if dd >= 1] or ok, key=lambda dd: daily[dd]['price_div'])
            row['peak'] = {'price_div': daily[peak]['price_div'], 'day': peak}
            row['low'] = {'price_div': daily[low]['price_div'], 'day': low}
            row['listings'] = {f'd{c}': (at(daily, c, TOL[c])[0] or {}).get('listings') for c in CHECK}
            row['listings']['end'] = daily[last]['listings']
            ref = row['d1'] or row['d3']
            if ref and ref['price_div'] > 0:
                row['ratios_vs_d1'] = {c: (round(row[c]['price_div'] / ref['price_div'], 2) if row.get(c) else None)
                                       for c in ['d0', 'd1', 'd3', 'd7', 'd14', 'd28', 'd42', 'end']}
            if row['d7'] and row['d7']['price_div'] > 0:
                row['ratios_vs_d7'] = {c: (round(row[c]['price_div'] / row['d7']['price_div'], 2) if row.get(c) else None)
                                       for c in ['d14', 'd28', 'd42', 'end']}
            mrow = {}
            for c in [f'd{c}' for c in CHECK] + ['end']:
                x = row.get(c)
                if x:
                    cur, _ = at(currency[lg], x['day_used'], 3)
                    if cur and cur.get('mirror_div'):
                        mrow[c] = round(x['price_div'] / cur['mirror_div'], 4)
            row['share_of_mirror'] = mrow
            ck[lg] = row
        if leagues:
            out[k] = {'base': ' / '.join(sorted(b for b in bases[k] if b)), 'leagues': leagues,
                      'first_seen': first_seen.get(k, {}), 'checkpoints': ck, 'detail': detail}

    json.dump(out, open(os.path.join(DER, 'uniques_merged.json'), 'w', encoding='utf-8'), indent=0, ensure_ascii=False)
    json.dump({lg: {str(k): v for k, v in sorted(c.items())} for lg, c in currency.items()},
              open(os.path.join(DER, 'currency_by_day.json'), 'w', encoding='utf-8'), indent=0)
    json.dump(wb_sources, open(os.path.join(DER, 'wayback_sources.json'), 'w', encoding='utf-8'), indent=0)
    print(len(out), 'uniques;', sum(len(v['leagues']) for v in out.values()), 'unique-league series')


if __name__ == '__main__':
    main()
