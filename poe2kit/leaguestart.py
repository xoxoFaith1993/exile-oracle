"""League start playbook: what each mechanic's loot sold for in the first 7 days of past leagues, hour by hour,
from GGG's public Currency Exchange history (documented Public API, no login, every hour since at least May 2026).

Exchange items only (currency, omens, runes, soul cores, essences, catalysts, splinters, emotions, fragments...).
Uniques never go through the exchange, so they aren't here.

Tables (F:\\PoE2Toolkit\\data\\poe2kit.db):
  ls_league (league, start_hour)            the first hour the league shows up on the exchange
  ls_price  (league, offset_h, item, price_ex, price_div, units)   one row per item per hour
The raw hourly pages are not kept (they're big); only the per-item prices."""

import json
import statistics
import time

from . import db, gamedata, money, net, ninja

BASE = 'https://web.poecdn.com/api/currency-exchange/poe2'
EX = 'Metadata/Items/Currency/CurrencyAddModToRare'      # Exalted Orb
DIV = 'Metadata/Items/Currency/CurrencyModValues'        # Divine Orb
CHAOS = 'Metadata/Items/Currency/CurrencyRerollRare'     # Chaos Orb
LEAGUES = ['Fate of the Vaal', 'Runes of Aldur', 'Forbidden Rites']
DAYS = 7
PAUSE = 1.5  # seconds between page requests: polite to GGG


def _setup(con):
    con.execute('CREATE TABLE IF NOT EXISTS ls_league (league TEXT PRIMARY KEY, start_hour INTEGER)')
    con.execute('CREATE TABLE IF NOT EXISTS ls_price (league TEXT, offset_h INTEGER, item TEXT, price_ex REAL, '
                'price_div REAL, units REAL, PRIMARY KEY (league, offset_h, item))')
    con.execute('CREATE TABLE IF NOT EXISTS ls_done (league TEXT, offset_h INTEGER, PRIMARY KEY (league, offset_h))')


def _page(con, hour):
    url = f'{BASE}/{hour}'
    d = net.get_json(url, con, min_age_minutes=60 * 24 * 365)
    con.execute('DELETE FROM http_cache WHERE url=?', (url,))  # don't keep raw pages
    return d


def _count(con, hour, league):
    return sum(1 for m in _page(con, hour).get('markets', []) if m.get('league') == league)


def find_start(con, league, lo, hi, min_markets=30):
    """Binary search for the first hour with the league on the exchange, between hours lo and hi
    (lo: before it existed, hi: during it)."""
    lo, hi = lo // 3600 * 3600, hi // 3600 * 3600
    while hi - lo > 3600:
        mid = (lo + hi) // 2 // 3600 * 3600
        if _count(con, mid, league) >= min_markets:
            hi = mid
        else:
            lo = mid
        time.sleep(PAUSE)
    return hi


def _mid(r):
    """Ratio dict {A: a, B: b} (a of A for b of B)."""
    return r


def prices_from_page(d, league):
    """item -> (price in exalts, units traded) for one hour, via each item's market against Exalted, Divine or
    Chaos (converted at that hour's rates)."""
    mk = [m for m in d.get('markets', []) if m.get('league') == league]
    pair = {}
    for m in mk:
        a, b = m['market_id'].split('|')
        lo, hi, vol = m.get('lowest_ratio') or {}, m.get('highest_ratio') or {}, m.get('volume_traded') or {}
        if vol.get(a) and vol.get(b):
            b_per_a = vol[b] / vol[a]  # volume-weighted average price that hour (the low/high ratios hold junk trades)
        else:
            rates = [r[b] / r[a] for r in (lo, hi) if r.get(a) and r.get(b)]
            if not rates:
                continue
            b_per_a = statistics.median(rates)
        pair[(a, b)] = (b_per_a, vol.get(a) or 0)
        pair[(b, a)] = (1 / b_per_a, vol.get(b) or 0)
    ex_per = {EX: 1.0}
    for base in (DIV, CHAOS):
        if (base, EX) in pair:
            ex_per[base] = pair[(base, EX)][0]
    out = {}
    items = {a for a, _ in pair}
    for it in items:
        for base in (EX, DIV, CHAOS):
            if it != base and (it, base) in pair and base in ex_per:
                rate, units = pair[(it, base)]
                tot_units = sum(u for (x, _), (_, u) in pair.items() if x == it)
                out[it] = (rate * ex_per[base], tot_units)
                break
    for base, v in ex_per.items():
        if base != EX:
            out[base] = (v, sum(u for (x, _), (_, u) in pair.items() if x == base))
    return out, ex_per.get(DIV)


def pull(con, league, start_hour, days=DAYS, log=print):
    """Fetch and store the first `days` days of a league (resumable)."""
    _setup(con)
    con.execute('INSERT OR REPLACE INTO ls_league VALUES (?,?)', (league, start_hour))
    con.commit()
    done = {r[0] for r in con.execute('SELECT offset_h FROM ls_done WHERE league=?', (league,))}
    for off in range(days * 24):
        if off in done:
            continue
        d = _page(con, start_hour + off * 3600)
        prices, ex_per_div = prices_from_page(d, league)
        rows = [(league, off, it, p, (p / ex_per_div) if ex_per_div else None, u) for it, (p, u) in prices.items()]
        con.executemany('INSERT OR REPLACE INTO ls_price VALUES (?,?,?,?,?,?)', rows)
        con.execute('INSERT OR REPLACE INTO ls_done VALUES (?,?)', (league, off))
        con.commit()
        if off % 12 == 0:
            log(f'{league}: hour {off}/{days * 24}, {len(rows)} items, 1 div = {ex_per_div and round(ex_per_div)} ex')
        time.sleep(PAUSE)


# ---------------- analysis ----------------

def _names():
    out = {}
    for k, v in gamedata.load('base_items').items():
        if v.get('name'):
            out[k] = v['name']
    return out


def _mechanic_of(con, names):
    """item name -> mechanic, using the poe.ninja categories the Farming board uses."""
    from . import farm
    cat_mech = {}
    for mech, cfg in farm.MECHANICS.items():
        for c in cfg['categories']:
            cat_mech[c] = mech
    out = {}
    for r in con.execute('SELECT DISTINCT name, category FROM price'):
        if r['category'] in cat_mech:
            out.setdefault(r['name'], cat_mech[r['category']])
        elif r['category'] in ('Currency',):
            out.setdefault(r['name'], 'Base currency')
    return out


def playbook(con):
    """Per league and day: each mechanic's average realistic drop value in exalts (at that day's prices; early on a
    Divine is worth far fewer exalts), the day's Divine rate, and the items that fell hardest by day 7 (sell on
    day 1) or held/rose (keep)."""
    _setup(con)
    names = _names()
    mech_of = _mechanic_of(con, names)
    leagues = [dict(r) for r in con.execute('SELECT * FROM ls_league ORDER BY start_hour')]
    if not con.execute('SELECT 1 FROM ls_price LIMIT 1').fetchone():
        from . import config
        p = config.data_file('playbook.json')
        if p:
            pb = json.load(open(p, encoding='utf-8'))
            pb['items'] = {}
            pb.setdefault('notes', []).append('From the data pack that ships with the app.')
            return pb
    res = {'leagues': [], 'mechanics': {}, 'div_rate': {}}
    per_item = {}  # name -> league -> day -> (median price_ex, units that day)
    for lg in leagues:
        L = lg['league']
        rows = con.execute('SELECT offset_h, item, price_ex, units FROM ls_price WHERE league=? AND price_ex > 0',
                           (L,)).fetchall()
        if not rows:
            continue
        hours = max(r['offset_h'] for r in rows) + 1
        res['leagues'].append({'league': L, 'start_hour': lg['start_hour'], 'hours': hours})
        by = {}
        for r in rows:
            if r['item'] == DIV:
                res['div_rate'].setdefault(L, {}).setdefault(r['offset_h'] // 24, []).append(r['price_ex'])
            nm = names.get(r['item'], r['item'].split('/')[-1])
            by.setdefault((nm, r['offset_h'] // 24), []).append((r['price_ex'], r['units']))
        for (nm, day), xs in by.items():
            per_item.setdefault(nm, {}).setdefault(L, {})[day] = (statistics.median(p for p, _ in xs),
                                                                 sum(u for _, u in xs))
        res['div_rate'][L] = {d: round(statistics.median(v), 1) for d, v in res['div_rate'].get(L, {}).items()}
    for nm, lgs in per_item.items():
        mech = mech_of.get(nm)
        if not mech:
            continue
        for L, days in lgs.items():
            for day, (price, units) in days.items():
                m = res['mechanics'].setdefault(mech, {}).setdefault(L, {}).setdefault(day, {'flow': 0, 'units': 0})
                if units >= 10:  # traded 10+ times that day across the league: a realistic drop
                    m['flow'] += price * units
                    m['units'] += units
    for mech, lgs in res['mechanics'].items():
        for L, days in lgs.items():
            for day, m in days.items():
                m['avg_ex'] = round(m['flow'] / m['units'], 3) if m['units'] else None
                m['units'] = round(m['units'])
                del m['flow']
    moves = []
    for nm, lgs in per_item.items():
        ch, d1 = [], []
        for L, days in lgs.items():
            dr = res['div_rate'].get(L, {})
            last = max(days)
            if 0 in days and last >= 5 and days[0][0] > 0 and days[0][1] >= 10 and dr.get(0) and dr.get(last):
                # change against the Divine Orb: exalts lose value all week, so raw ex prices all look like they rise
                ch.append((days[last][0] / days[0][0]) / (dr[last] / dr[0]) - 1)
                d1.append(days[0][0])
        if ch and statistics.median(d1) >= 1:  # worth at least 1 ex on day 1
            moves.append({'item': nm, 'mechanic': mech_of.get(nm, 'Other'), 'leagues': len(ch),
                          'day1_ex': round(statistics.median(d1), 2),
                          'change_by_day7_pct': round(statistics.median(ch) * 100, 1)})
    # seen in 2+ launches first (a pattern, not a one-off), then by size of the move
    res['sell_day1'] = sorted((m for m in moves if m['change_by_day7_pct'] < 0),
                              key=lambda x: (x['leagues'] < 2, x['change_by_day7_pct']))[:25]
    res['hold'] = sorted((m for m in moves if m['change_by_day7_pct'] > 0),
                         key=lambda x: (x['leagues'] < 2, -x['change_by_day7_pct']))[:25]
    res['items'] = {nm: {L: {d: {'ex': round(p, 3), 'units': round(u)} for d, (p, u) in days.items()}
                         for L, days in lgs.items()} for nm, lgs in per_item.items()}
    res['notes'] = ["From GGG's Currency Exchange history: exchange items only (no uniques).",
                    'Values are in exalts at that day\'s prices. A Divine is cheap at launch (tens of exalts) and '
                    'climbs all week, so the day\'s rate is shown above the table.',
                    'Average drop = units-weighted price of items that traded 10+ times that day.',
                    'Sell / hold lists compare each item with the Divine Orb from day 1 to day 7 (exalts lose value all '
                    'week, so in exalts almost everything looks like it rises).',
                    'Day 1 = the first 24 hours after the league appeared on the exchange.']
    return res
