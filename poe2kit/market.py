"""Market history (like PoE Overlay's): for every Currency Exchange item, hourly price and stock from GGG's public
exchange history, with a 7-day sparkline and change. Derived from the raw `exchange_hour` rows into a compact
`ex_price` table as new hours arrive (the exchange job calls derive())."""

import json
import statistics
import time

from . import db, leaguestart, money, ninja

EX, DIV = leaguestart.EX, leaguestart.DIV


def _setup(con):
    con.execute('CREATE TABLE IF NOT EXISTS ex_price (hour INTEGER, league TEXT, item TEXT, price_ex REAL, '
                'price_div REAL, units REAL, stock REAL, PRIMARY KEY (hour, league, item))')


def derive(con, max_hours=500):
    """Turn new raw exchange hours into per-item prices. Returns hours processed."""
    _setup(con)
    done = int(db.kv_get(con, 'ex_price_hour', '0') or 0)
    hours = [r[0] for r in con.execute('SELECT DISTINCT hour FROM exchange_hour WHERE hour > ? ORDER BY hour LIMIT ?',
                                       (done, max_hours))]
    for h in hours:
        by_league = {}
        for r in con.execute('SELECT * FROM exchange_hour WHERE hour=?', (h,)):
            by_league.setdefault(r['league'], []).append({
                'league': r['league'], 'market_id': r['market_id'],
                'volume_traded': json.loads(r['volume_json'] or 'null'),
                'lowest_ratio': json.loads(r['lowest_ratio_json'] or 'null'),
                'highest_ratio': json.loads(r['highest_ratio_json'] or 'null'),
                'highest_stock': json.loads(r['highest_stock_json'] or 'null')})
        rows = []
        for lg, mk in by_league.items():
            if len(mk) < 50:   # tiny private leagues
                continue
            prices, ex_per_div = leaguestart.prices_from_page({'markets': mk}, lg)
            stock = {}
            for m in mk:
                for k, v in (m.get('highest_stock') or {}).items():
                    stock[k] = max(stock.get(k, 0), v or 0)   # deepest single market for the item
            for it, (p, u) in prices.items():
                rows.append((h, lg, it, p, p / ex_per_div if ex_per_div else None, u, stock.get(it)))
        con.executemany('INSERT OR REPLACE INTO ex_price VALUES (?,?,?,?,?,?,?)', rows)
        db.kv_set(con, 'ex_price_hour', str(h))
        con.commit()
    return len(hours)


def _catalog(con, league):
    """name -> (category, icon) from poe.ninja rows."""
    out = {}
    for r in con.execute('SELECT name, category, MAX(icon) icon FROM price WHERE league=? GROUP BY name, category',
                         (league,)):
        if r['name'] not in out or (r['icon'] and not out[r['name']][1]):
            out[r['name']] = (r['category'], r['icon'])
    return out


def history(con, league=None, category=None, days=7, points=42):
    _setup(con)
    league = league or ninja.current_league(con)
    last = con.execute('SELECT MAX(hour) FROM ex_price WHERE league=?', (league,)).fetchone()[0]
    if not last:
        return {'league': league, 'items': [], 'categories': [], 'note': 'No exchange history derived yet.'}
    since = last - days * 24 * 3600
    names = leaguestart._names()
    cat = _catalog(con, league)
    series = {}
    for r in con.execute('SELECT hour, item, price_div, units, stock FROM ex_price WHERE league=? AND hour>=? '
                         'ORDER BY hour', (league, since)):
        series.setdefault(r['item'], []).append((r['hour'], r['price_div'], r['units'], r['stock']))
    rt = money.rates(con, league)
    items, cats = [], {}
    for it, s in series.items():
        nm = names.get(it, it.split('/')[-1])
        c, icon = cat.get(nm, ('Other', None))
        cats[c] = cats.get(c, 0) + 1
        if category and c != category:
            continue
        s = [x for x in s if x[1]]
        if not s:
            continue
        smooth = [statistics.median(x[1] for x in s[max(0, i - 2):i + 3]) for i in range(len(s))]  # drop one-hour spikes
        step = max(1, -(-len(s) // points))
        spark = [round(statistics.median(smooth[i:i + step]), 6) for i in range(0, len(smooth), step)]
        first = statistics.median(x[1] for x in s[:6])
        now = statistics.median(x[1] for x in s[-3:])
        stock_now = s[-1][3]
        units_day = sum(x[2] or 0 for x in s if x[0] > last - 24 * 3600)
        items.append({'item': nm, 'category': c, 'icon': icon, 'price_div': round(now, 6), 'price': money.fmt(now, rt),
                      'change_pct': round((now / first - 1) * 100, 1) if first else None,
                      'stock': stock_now, 'traded_24h': round(units_day), 'spark': spark,
                      'hours': len(s), 'last_hour': s[-1][0]})
    items.sort(key=lambda x: -(x['price_div'] or 0))
    return {'league': league, 'days': days, 'as_of': last, 'items': items,
            'categories': sorted(cats.items(), key=lambda x: -x[1]),
            'note': "GGG's Currency Exchange history (hourly). Price = volume-weighted average that hour; stock = the "
                    'deepest single market listing for the item.'}
