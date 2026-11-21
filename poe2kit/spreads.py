"""Currency Exchange gaps (R24): items that trade against several currencies at prices that disagree.

GGG's public exchange history gives, per currency pair and hour, how much of each side traded and the ratios. For
an item X traded against currencies C1, C2, ... the price of X through each market, converted to Exalts with that
hour's consensus prices (ex_price, poe2kit.market), should be about the same. When it isn't, buying X through the
cheap market and selling it through the dear one would have made the gap (before the exchange's gold fee).

Honest limits (shown in the app): this is LAST HOUR'S TRADES, not live orders, so a gap may already be closed;
thin markets swing; the gold fee isn't counted. Gaps that held for several hours in a row, on markets with real
volume, rank first. Items worth under 1 Exalted are left out (not worth trading, the author's rule)."""

import json
import time

from . import db

MIN_GAP = 8          # % difference between the cheapest and dearest market
MAX_GAP = 100        # bigger "gaps" in the hourly history are thin-market noise, not trades you can repeat
MIN_HELD = 3         # the gap held this many hours in a row
MIN_SIDE_DIV = 5     # at least this much value traded on EACH side (Divines)
MIN_UNITS = 5        # units of the item traded in each market that hour
MIN_EX = 1           # item worth at least 1 Exalted
HOURS = 4            # how far back persistence is checked
BASES = ('Metadata/Items/Currency/CurrencyAddModToRare', 'Metadata/Items/Currency/CurrencyModValues',
         'Metadata/Items/Currency/CurrencyRerollRare')   # Exalted, Divine, Chaos


def _consensus(con, league, hour):
    return {r['item']: r['price_ex'] for r in
            con.execute('SELECT item, price_ex FROM ex_price WHERE league=? AND hour=?', (league, hour)) if r['price_ex']}


def _hour_gaps(con, league, hour):
    """item -> {'cheap': (via, ex, units), 'dear': (via, ex, units), 'gap': %} for one hour."""
    cons = _consensus(con, league, hour)
    if not cons:
        return {}
    via = {}
    for r in con.execute('SELECT market_id, volume_json, lowest_ratio_json, highest_ratio_json FROM exchange_hour '
                         'WHERE league=? AND hour=?', (league, hour)):
        try:
            a, b = r['market_id'].split('|')
            vol = json.loads(r['volume_json'] or '{}')
            lo = json.loads(r['lowest_ratio_json'] or '{}')
            hi = json.loads(r['highest_ratio_json'] or '{}')
        except (ValueError, AttributeError):
            continue
        for x, y in ((a, b), (b, a)):   # price of x paid in y: only via the big three (their prices are solid)
            if y not in BASES:
                continue
            if (vol.get(x) or 0) < MIN_UNITS or (vol.get(y) or 0) <= 0 or not cons.get(y):
                continue
            ex = vol[y] / vol[x] * cons[y]   # volume-weighted price that hour (the low / high ratios hold junk trades)
            via.setdefault(x, []).append((y, ex, vol.get(x) or 0))
    out = {}
    for x, lst in via.items():
        if len(lst) < 2 or (cons.get(x) or 0) < MIN_EX:
            continue
        cheap, dear = min(lst, key=lambda v: v[1]), max(lst, key=lambda v: v[1])
        gap = (dear[1] / cheap[1] - 1) * 100 if cheap[1] else 0
        if gap >= MIN_GAP:
            out[x] = {'cheap': cheap, 'dear': dear, 'gap': gap, 'consensus': cons[x]}
    return out


def find(con, league=None, limit=25):
    from . import ninja, leaguestart, money
    league = league or ninja.current_league(con)
    try:
        hours = [r[0] for r in con.execute('SELECT DISTINCT hour FROM ex_price WHERE league=? ORDER BY hour DESC LIMIT ?',
                                           (league, HOURS))]
    except Exception:   # a fresh install: no exchange history stored yet
        hours = []
    if not hours:
        return {'league': league, 'gaps': [], 'note': 'No exchange history for this league yet.'}
    per_hour = [_hour_gaps(con, league, h) for h in hours]
    names = leaguestart._names()
    ex_per_div = (money.rates(con, league) or {}).get('ex_per_div')
    rows = []
    for x, g in per_hour[0].items():
        held = 1
        for older in per_hour[1:]:
            o = older.get(x)
            if not o or o['cheap'][0] != g['cheap'][0] or o['dear'][0] != g['dear'][0]:
                break
            held += 1
        nm = lambda i: names.get(i) or i.rsplit('/', 1)[-1]
        rows.append({'item': nm(x), 'gap_pct': round(g['gap'], 1), 'held_hours': held,
                     'buy_with': nm(g['cheap'][0]), 'buy_ex': round(g['cheap'][1], 2), 'buy_units': g['cheap'][2],
                     'sell_for': nm(g['dear'][0]), 'sell_ex': round(g['dear'][1], 2), 'sell_units': g['dear'][2],
                     'value_ex': round(g['consensus'], 2),
                     'value_div': round(g['consensus'] / ex_per_div, 3) if ex_per_div else None,
                     'score': g['gap'] * min(held, HOURS) * min(g['cheap'][2], g['dear'][2]) ** 0.5})
    ex_div = ex_per_div or 1
    rows = [r for r in rows if r['held_hours'] >= MIN_HELD and r['gap_pct'] <= MAX_GAP
            and r['buy_units'] * r['buy_ex'] >= MIN_SIDE_DIV * ex_div and r['sell_units'] * r['sell_ex'] >= MIN_SIDE_DIV * ex_div]
    rows.sort(key=lambda r: -r['score'])
    for r in rows:
        r.pop('score')
    return {'league': league, 'hour': hours[0], 'age_min': round((time.time() - hours[0]) / 60),
            'gaps': rows[:limit], 'checked_hours': len(hours),
            'note': "From the last hours' trades, not live orders: a gap may already be gone, so check the exchange before "
                    "you trade, and the exchange's gold fee isn't counted. Only gaps that held 3+ hours, under 100%, with at "
                    f"least {MIN_SIDE_DIV} div traded on each side are shown (the rest of the history is thin-market noise)."}
