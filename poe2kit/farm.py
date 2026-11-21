"""Farm Advisor v1: which league mechanic's loot is worth the most right now, from live poe.ninja prices and
the history the monitor stores.

What it can say from prices: how much each mechanic's drops are worth (best / typical item), how much trades
(liquidity), which way it's trending, and what that mechanic's tablets cost to run. What it can't know yet:
drop rates per map. As you farm, your own results (price memory, later) make the ranking personal."""

import statistics
import time

from . import db, money, ninja

# Upside the market view can't price: rewards that aren't the mechanic's own currency.
ALSO = {
    'Ritual': {'text': 'Ritual rewards can also offer uniques, chase ones included: players (the author included) have had Mageblood from Ritual. '
                       'No public rate exists, so it is not in the numbers; treat it as upside.',
               'examples': ['Mageblood', 'Headhunter']},
}

MECHANICS = {
    'Breach': {'categories': ['Breach'], 'words': ['breach', 'splinter', 'breachstone']},
    'Delirium': {'categories': ['Delirium'], 'words': ['delirium', 'simulacrum', 'emotion']},
    'Ritual': {'categories': ['Ritual'], 'words': ['ritual', 'omen']},
    'Expedition': {'categories': ['Expedition'], 'words': ['expedition', 'logbook', 'artifact']},
    'Abyss': {'categories': ['Abyss'], 'words': ['abyss', 'bone', 'jawbone', 'collarbone', 'rib']},
    'Essences': {'categories': ['Essences'], 'words': ['essence']},
    'Soul cores (Ultimatum)': {'categories': ['SoulCores'], 'words': ['soul core', 'ultimatum']},
    'Runes': {'categories': ['Runes'], 'words': ['rune']},
    'Idols': {'categories': ['Idols'], 'words': ['idol']},
    'Bossing (fragments)': {'categories': ['Fragments'], 'words': ['fragment', 'key', 'crisis', 'invitation']},
    'Verisium (Runes of Aldur)': {'categories': ['Verisium'], 'words': ['verisium']},
}


def _latest(con, league):
    return con.execute(
        """SELECT p.* FROM price p JOIN (SELECT item_key, category, MAX(ts) m FROM price WHERE league=?
           GROUP BY item_key, category) x ON p.item_key=x.item_key AND p.category=x.category AND p.ts=x.m
           WHERE p.league=?""", (league, league)).fetchall()


def _index_at(con, league, cats, ts):
    """Summed price of a mechanic's traded items at the snapshot nearest before ts (a simple price index)."""
    snap = con.execute('SELECT MAX(ts) FROM price WHERE league=? AND ts<=?', (league, ts)).fetchone()[0]
    if not snap:
        return None
    q = f"SELECT value, volume FROM price WHERE league=? AND ts=? AND category IN ({','.join('?' * len(cats))})"
    rows = con.execute(q, [league, snap] + cats).fetchall()
    return sum((r['value'] or 0) for r in rows if (r['volume'] or 0) > 0) or None


RARITY = [(100, 'common'), (10, 'uncommon'), (1, 'rare'), (0, 'chase')]


def rarity(units_per_day):
    """How often an item changes hands across the whole league: a stand-in for how often it drops."""
    for floor, name in RARITY:
        if units_per_day >= floor:
            return name
    return 'chase'


def _how_often(u):
    if u >= 1:
        return f'~{u:,.0f} traded a day'
    return f'~1 traded every {max(1, round(1 / u)) if u else "?"} days' if u else 'barely trades'


def board(con, league=None):
    """Mechanics ranked by what you'd realistically drop: each item weighted by how many change hands per day
    (poe.ninja volume is div traded per day; / price = units per day). Chase items (under 1 a day across the
    whole league) are listed apart and don't drive the ranking."""
    league = league or ninja.current_league(con)
    rt = money.rates(con, league)
    rows = _latest(con, league)
    tablets = [r for r in rows if r['category'] in ('UniqueTablets', 'PrecursorTablets')]
    now = time.time()
    out = []
    for mech, cfg in MECHANICS.items():
        items = []
        for r in rows:
            if r['category'] in cfg['categories'] and r['value']:
                u = (r['volume'] or 0) / r['value']
                items.append({'name': r['name'], 'value_div': round(r['value'], 4), 'price': money.fmt(r['value'], rt),
                              'icon': r['icon'], 'traded_div_day': round(r['volume'] or 0, 1),
                              'units_day': round(u, 2), 'rarity': rarity(u), 'how_often': _how_often(u)})
        if not items:
            continue
        farmable = [x for x in items if x['units_day'] >= 1]
        chase = sorted((x for x in items if x['units_day'] < 1), key=lambda x: -x['value_div'])
        steady = [x for x in farmable if x['rarity'] in ('common', 'uncommon')]  # 10+ a day league-wide
        units = sum(x['units_day'] for x in steady)
        flow = sum(x['traded_div_day'] for x in farmable)
        avg = sum(x['traded_div_day'] for x in steady) / units if units else 0  # average steady drop
        idx_now = _index_at(con, league, cfg['categories'], now)
        idx_day = _index_at(con, league, cfg['categories'], now - 24 * 3600)
        idx_week = _index_at(con, league, cfg['categories'], now - 7 * 24 * 3600)
        idx_1h = _index_at(con, league, cfg['categories'], now - 3600)
        idx_6h = _index_at(con, league, cfg['categories'], now - 6 * 3600)
        trend = lambda old: round((idx_now / old - 1) * 100, 1) if idx_now and old else None
        best_real = max((x for x in farmable if x['rarity'] in ('common', 'uncommon')), key=lambda x: x['value_div'],
                        default=None)
        tabs = [t for t in tablets if any(w in (t['name'] + ' ' + (t['base'] or '')).lower() for w in cfg['words'])]
        out.append({
            'mechanic': mech, 'items': len(items),
            'avg_drop_div': round(avg, 4), 'avg_drop': money.fmt(avg, rt),
            'best_real': best_real,
            'farmable_units_day': round(units), 'liquidity_div_per_day': round(flow, 1),
            'chase': chase[:5],
            'trend_1h_pct': trend(idx_1h), 'trend_6h_pct': trend(idx_6h),
            'trend_24h_pct': trend(idx_day), 'trend_7d_pct': trend(idx_week),
            'top_items': sorted(farmable, key=lambda x: -x['traded_div_day'])[:6],
            'tablets': [{'name': t['name'], 'base': t['base'], 'value_div': round(t['value'], 4),
                         'price': money.fmt(t['value'], rt), 'icon': t['icon']} for t in
                        sorted(tabs, key=lambda t: -(t['value'] or 0))[:4]],
        })
    from . import dropinfo
    est = dropinfo.setups(con, league)
    for m in out:
        m['estimates'] = est.get(m['mechanic'], [])[:5]
        m['est_map'] = dropinfo.best(m['estimates'])
        al = ALSO.get(m['mechanic'])
        if al:
            px = {r['name']: r['value'] for r in rows if r['name'] in al['examples'] and r['value']}
            m['also'] = {'text': al['text'], 'examples': [{'name': n, 'price': money.fmt(v, rt), 'value_div': round(v, 2)}
                                                         for n, v in px.items()]}
    # score: worth of the average realistic drop x how much of it there is (sqrt so floods of junk don't win)
    for m in out:
        m['score'] = round(m['avg_drop_div'] * (m['farmable_units_day'] ** 0.5), 2)
    out.sort(key=lambda m: -m['score'])
    first = con.execute('SELECT MIN(ts) FROM price WHERE league=?', (league,)).fetchone()[0]
    return {'league': league, 'mechanics': out,
            'history_hours': round((now - first) / 3600, 1) if first else 0,
            'notes': ['Ranked by what you would realistically drop: every item is weighted by how many change hands '
                      'per day across the league, so a 299-div key that trades once every 5 days does not count as '
                      'a typical drop. Those are listed as chase drops.',
                      'Rarity: common = 100+ traded a day, uncommon 10–100, rare 1–10, chase under 1. Average drop and the '
                      'ranking use common + uncommon items only.',
                      'Per-map estimates come from tracked farming runs people published (sample size and patch '
                      'shown): anecdotal, since only GGG knows real drop rates. Priced at today\'s prices.',
                      'Trends: 1 h and 6 h work from the first hours of a league (prices update about hourly); 24 h after a day, 7 d after a week.']}
