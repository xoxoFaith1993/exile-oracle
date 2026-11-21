"""Market at a glance: key currency rates (mirror, divine, exalt, chaos) and the league's chase items."""

from . import money, ninja

KEY_CURRENCY = ['Mirror of Kalandra', "Hinekora's Lock", 'Divine Orb', 'Perfect Exalted Orb', 'Perfect Chaos Orb',
                'Greater Exalted Orb', 'Orb of Annulment', 'Exalted Orb', 'Chaos Orb']
PRETTY = {'LineageSupportGems': 'Lineage support gem', 'UncutGems': 'Uncut gem', 'SoulCores': 'Soul core',
          'Runes': 'Rune', 'Idols': 'Idol', 'Fragments': 'Fragment', 'Ritual': 'Omen', 'Delirium': 'Liquid emotion',
          'Breach': 'Catalyst', 'Abyss': 'Abyssal bone', 'Essences': 'Essence', 'Expedition': 'Expedition',
          'Verisium': 'Verisium', 'Currency': 'Currency'}
BAROMETERS = ['Headhunter', 'Mageblood']   # always in the chase list, whatever they cost (the author); a daily price log is kept
MIN_LISTINGS = 5          # ignore troll / one-off listings (e.g. a "41 million div" unique with 1 listing)


def _barometer_log(con, league, name, value):
    """One price per day per barometer, kept for the whole league (the price table only keeps recent snapshots).
    Returns the change against about a week ago (or the oldest day logged) and the daily history."""
    import json
    import time
    from . import db
    key = f'barometer:{league}:{name}'
    log = json.loads(db.kv_get(con, key) or '{}')
    today = time.strftime('%Y-%m-%d', time.gmtime())
    if value and log.get(today) != value:
        log[today] = value
        db.kv_set(con, key, json.dumps(dict(sorted(log.items())[-400:])))
    days = sorted(log)
    out = {'history': [[d, log[d]] for d in days[-60:]]}
    if len(days) >= 2:
        week_ago = time.strftime('%Y-%m-%d', time.gmtime(time.time() - 7 * 86400))
        base_day = max([d for d in days if d <= week_ago], default=days[0])
        if log.get(base_day):
            out['change_pct'] = round((value / log[base_day] - 1) * 100, 1)
            out['change_since'] = base_day
    return out


def overview(con, league=None, top=12):
    league = league or ninja.current_league(con)
    rows = con.execute(
        """SELECT p.* FROM price p JOIN (SELECT item_key, category, MAX(ts) m FROM price WHERE league=?
           GROUP BY item_key, category) x ON p.item_key=x.item_key AND p.category=x.category AND p.ts=x.m
           WHERE p.league=?""", (league, league)).fetchall()
    rt = money.rates(con, league)
    by_name = {}
    for r in rows:
        by_name.setdefault(r['name'], dict(r))
    mirror = (by_name.get('Mirror of Kalandra') or {}).get('value')

    def card(r):
        v = r['value'] or 0
        c = {'name': r['name'].replace(' [corrupted]', ''), 'base': r['base'], 'category': PRETTY.get(r['category'], r['category']),
             'value_div': round(v, 3), 'price': money.fmt(v, rt), 'icon': r['icon'],
             'listings': r['listings'], 'volume': r['volume'], 'corrupted': r['name'].endswith('[corrupted]')}
        if r['name'] == 'Chaos Orb' and rt.get('ex_per_div'):
            c['price'] = f"{round(v * rt['ex_per_div'])} ex"
        if mirror and v >= mirror * 0.5:
            c['mirrors'] = round(v / mirror, 2)
        return c

    currency = [card(by_name[n]) for n in KEY_CURRENCY if n in by_name]
    uniques = sorted([r for r in rows if r['category'].startswith('Unique') and (r['listings'] or 0) >= MIN_LISTINGS
                      and r['value']], key=lambda r: -r['value'])
    seen, chase_u = set(), []
    for r in uniques:  # one line per unique name (best-priced base / variant)
        key = r['name'].replace(' [corrupted]', '').split(' (')[0]
        if key in seen:
            continue
        seen.add(key)
        chase_u.append(card(r))
        if len(chase_u) >= top:
            break
    for name in BAROMETERS:   # always on the board, with their 7-day change, as a market thermometer
        r = next((x for x in sorted(rows, key=lambda x: -(x['listings'] or 0)) if x['category'].startswith('Unique')
                  and x['name'] == name), None)
        if not r:
            continue
        c = next((x for x in chase_u if x['name'] == name), None)
        if c is None:
            c = card(r)
            chase_u.append(c)
        c['barometer'] = True
        c.update(_barometer_log(con, league, name, r['value']))
    other = sorted([r for r in rows if not r['category'].startswith('Unique') and r['name'] not in KEY_CURRENCY
                    and r['value'] and (r['volume'] or 0) > 0], key=lambda r: -r['value'])[:top]
    return {
        'league': league,
        'rates': {'mirror_div': round(mirror) if mirror else None, 'div_ex': rt.get('ex_per_div'),
                  'div_chaos': rt.get('chaos_per_div'),
                  'chaos_ex': round(rt['ex_per_div'] / rt['chaos_per_div'], 1) if rt.get('ex_per_div') and rt.get('chaos_per_div') else None},
        'currency': currency, 'chase_uniques': chase_u, 'chase_other': [card(r) for r in other],
        'note': f'Uniques need at least {MIN_LISTINGS} listings to show (filters out fake prices).',
    }


def log_uniques(con, league=None, top=80):
    """Once per day: the price of the league's top uniques (by value, real listings only) plus the always-shown ones,
    into unique_daily. Kept for the whole league; cheap (one row per unique per day)."""
    import time
    league = league or ninja.current_league(con)
    day = time.strftime('%Y-%m-%d', time.gmtime())
    rows = con.execute(
        """SELECT p.name, p.base, p.value, p.listings FROM price p JOIN (SELECT item_key, MAX(ts) m FROM price
           WHERE league=? AND category LIKE 'Unique%' GROUP BY item_key) x ON p.item_key=x.item_key AND p.ts=x.m
           WHERE p.league=? AND p.value > 0""", (league, league)).fetchall()
    best = {}
    for r in rows:   # one row per unique name: the variant with the most listings
        n = r['name'].replace(' [corrupted]', '')
        if n not in best or (r['listings'] or 0) > (best[n]['listings'] or 0):
            best[n] = r
    keep = sorted([r for r in best.values() if (r['listings'] or 0) >= MIN_LISTINGS], key=lambda r: -r['value'])[:top]
    keep += [best[n] for n in BAROMETERS if n in best and best[n] not in keep]
    for r in keep:
        con.execute('INSERT OR REPLACE INTO unique_daily(day, league, name, base, value_div, listings) VALUES(?,?,?,?,?,?)',
                    (day, league, r['name'].replace(' [corrupted]', ''), r['base'], r['value'], r['listings']))
    con.commit()
    return len(keep)
