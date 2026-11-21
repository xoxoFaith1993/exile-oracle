"""The Oracle's market advice: what the last three league launches say about NOW.

Research (datapack/market-trends.json, R7): price patterns by league phase, strategies, and day-by-day curves in
Divine Orbs for 42 exchange items across Fate of the Vaal, Runes of Aldur and Forbidden Rites. This module works out
the current league day, the phase, what to do now, and for each tracked item where it usually goes next (sell now /
hold / steady), next to its live price from the app's own exchange sync."""

import json
import math
import time

from . import config, db

MIN_EX = 1   # items worth less than one Exalted Orb aren't worth trading: left out of the outlook (the author)
PHASES = [('day 1-3', 0, 3), ('week 1', 3, 7), ('week 2-3', 7, 22), ('week 4+', 22, 10 ** 6)]
_data = {}


def data():
    if not _data:
        p = config.data_file('market-trends.json')
        if not p:
            raise FileNotFoundError('market-trends.json is missing from the data pack')
        _data.update(json.load(open(p, encoding='utf-8')))
    return _data


def league_start(con, league):
    """Unix time the league opened: the league-start table, else the first exchange hour we have for it."""
    r = con.execute('SELECT start_hour FROM ls_league WHERE league=?', (league,)).fetchone()
    if r and r[0]:
        return r[0]
    r = con.execute('SELECT MIN(hour) FROM exchange_hour WHERE league=?', (league,)).fetchone()
    return r[0] if r and r[0] else None


def phase_of(day):
    for name, lo, hi in PHASES:
        if lo <= day < hi:
            return name
    return 'week 4+'


def _curve(item, league):
    c = (data()['curves_div'].get(item) or {}).get(league) or {}
    return sorted((int(d), v) for d, v in c.items() if v)


def _at(curve, day):
    """Price on `day` by log interpolation; None outside the curve."""
    if not curve or day < curve[0][0] or day > curve[-1][0]:
        return None
    for (d0, v0), (d1, v1) in zip(curve, curve[1:]):
        if d0 <= day <= d1:
            t = (day - d0) / (d1 - d0) if d1 > d0 else 0
            return math.exp(math.log(v0) + t * (math.log(v1) - math.log(v0)))
    return curve[-1][1]


def outlook(item, day, ahead=7):
    """Median change in Divines from `day` to `day + ahead` across the researched leagues, and the typical peak day."""
    changes, peaks = [], []
    for lg in (data()['curves_div'].get(item) or {}):
        cv = _curve(item, lg)
        a, b = _at(cv, day), _at(cv, day + ahead)
        if a and b:
            changes.append(b / a - 1)
        if cv:
            peaks.append(max(cv, key=lambda x: x[1])[0])
    changes.sort()
    med = changes[len(changes) // 2] if changes else None
    return {'change_pct': round(med * 100) if med is not None else None, 'leagues': len(changes),
            'peak_day': sorted(peaks)[len(peaks) // 2] if peaks else None}


_ids = {}


def _id_of(item):
    """Exchange table ids are game metadata paths: name -> id from the game data (same map the market uses)."""
    if not _ids:
        try:   # needs the community game data (downloaded on first start); without it there are no live prices yet
            from . import leaguestart
            for k, v in leaguestart._names().items():
                _ids.setdefault(v, k)
        except (OSError, ValueError):
            return item
    return _ids.get(item, item)


def _live(con, league, item):
    rows = con.execute('SELECT hour, price_div FROM ex_price WHERE league=? AND item=? ORDER BY hour DESC LIMIT 400',
                       (league, _id_of(item))).fetchall()
    if not rows:
        return None, None
    now_p = rows[0][1]
    week = [p for h, p in rows if h <= rows[0][0] - 7 * 86400]
    return now_p, (round((now_p / week[0] - 1) * 100, 1) if week and week[0] else None)


def advice(con=None, league=None, day=None):
    """Phase, strategies for now (and the next phase), and the item outlook for the next 7 days."""
    con = con or db.connect()
    from . import ninja
    league = league or ninja.current_league(con)
    start = league_start(con, league)
    if start:
        _now_day['d'] = (time.time() - start) / 86400
    if day is None:
        day = (time.time() - start) / 86400 if start else None
    d = data()
    out = {'league': league, 'day': round(day, 1) if day is not None else None, 'about': d.get('about'),
           'caveats': d.get('caveats') or []}
    if day is None:
        out['note'] = 'League start unknown: the exchange history for this league has not synced yet.'
        return out
    ph = phase_of(day)
    nxt = next((p for p in PHASES if p[1] > day), None)
    out['phase'] = ph
    out['next_phase'] = {'name': nxt[0], 'in_days': round(nxt[1] - day, 1)} if nxt else None
    out['do_now'] = [s for s in d['strategies'] if s['phase'] in (ph, 'any')]
    out['coming_up'] = [s for s in d['strategies'] if nxt and s['phase'] == nxt[0]]
    out['patterns_now'] = [p for p in d['patterns'] if p['phase'] == ph]
    items = []
    from . import money
    live_ex = (money.rates(con, league) or {}).get('ex_per_div')
    skipped = 0
    for item in d['curves_div']:
        o = outlook(item, day)
        price, chg7 = _live(con, league, item)
        worth = _worth_ex(item, day, price, live_ex)
        if worth is not None and worth < MIN_EX:
            skipped += 1
            continue
        c = o['change_pct']
        if c is None:
            verdict = 'past the researched days' if day > 70 else 'no data'
        elif c <= -20:
            verdict = 'sell now'
        elif c >= 20:
            verdict = 'hold / buy'
        else:
            verdict = 'steady'
        items.append(dict(o, item=item, verdict=verdict, price_div=price, change_7d_pct=chg7))
    items.sort(key=lambda x: (x['change_pct'] is None, -abs(x['change_pct'] or 0)))
    out['items'] = items
    out['skipped_cheap'] = skipped
    if day > 70:
        out['note'] = ('Late league: the researched curves end around day 70, so item outlooks are mostly blank. '
                       'The week 4+ strategies still apply. From the 1.0 launch (day 0) every item has a full outlook.')
    return out


def _worth_ex(item, day, price_div, live_ex):
    """An item's worth in Exalted Orbs: today's live price when we have it (for the current day), else the median of
    what it was worth on that league day in past launches (price in div x that day's Ex per Div)."""
    if price_div is not None and live_ex and day is not None and abs(day - (_now_day.get('d') or -1)) < 1:
        return price_div * live_ex
    vals = []
    for lg in (data()['curves_div'].get(item) or {}):
        v = _at(_curve(item, lg), day)
        rt = (data().get('ratios') or {}).get(lg) or {}
        days = sorted((int(k), x.get('ex_per_div')) for k, x in rt.items() if x.get('ex_per_div'))
        if v and days:
            ex = min(days, key=lambda kv: abs(kv[0] - day))[1]
            vals.append(v * ex)
    vals.sort()
    return vals[len(vals) // 2] if vals else (price_div * live_ex if price_div is not None and live_ex else None)


_now_day = {}


def hold_note(item):
    """For the league-start playbook's 'worth holding' list: when the research says the rise reverses. Per league: the
    peak within the first six weeks and how far it falls from there by day 42."""
    curves = data()['curves_div'].get(item) or {}
    peaks, falls = [], []
    for lg in curves:
        cv = [x for x in _curve(item, lg) if x[0] <= 42]
        if len(cv) < 3:
            continue
        pk = max(cv, key=lambda x: x[1])
        late = _at(cv, 42)
        peaks.append(pk[0])
        if late:
            falls.append(late / pk[1] - 1)
    if not peaks:
        return None
    peak = sorted(peaks)[len(peaks) // 2]
    fall = sorted(falls)[len(falls) // 2] if falls else 0
    if peak <= 1 and fall < -0.4:
        return f'sell or swap right away: down {round(-fall * 100)}% by day 42'
    if fall < -0.4:
        return f'hold to about day {peak}, then sell (down {round(-fall * 100)}% from the peak by day 42)'
    if peak >= 30:
        return f'keeps rising: peaks around day {peak}'
    return None
