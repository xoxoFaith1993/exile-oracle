"""Market at a glance: key currency rates (mirror, divine, exalt, chaos) and the league's chase items."""

from . import money, ninja

KEY_CURRENCY = ['Mirror of Kalandra', "Hinekora's Lock", 'Divine Orb', 'Perfect Exalted Orb', 'Perfect Chaos Orb',
                'Greater Exalted Orb', 'Orb of Annulment', 'Exalted Orb', 'Chaos Orb']
PRETTY = {'LineageSupportGems': 'Lineage support gem', 'UncutGems': 'Uncut gem', 'SoulCores': 'Soul core',
          'Runes': 'Rune', 'Idols': 'Idol', 'Fragments': 'Fragment', 'Ritual': 'Omen', 'Delirium': 'Liquid emotion',
          'Breach': 'Catalyst', 'Abyss': 'Abyssal bone', 'Essences': 'Essence', 'Expedition': 'Expedition',
          'Verisium': 'Verisium', 'Currency': 'Currency'}
MIN_LISTINGS = 5          # ignore troll / one-off listings (e.g. a "41 million div" unique with 1 listing)


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
