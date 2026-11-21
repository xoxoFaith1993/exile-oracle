"""Build cost: price every piece of a Path of Building (PoE 2) build from stored poe.ninja data.

Priced automatically: uniques (matched on name AND base type), runes / soul cores / idols socketed in
gear, lineage support gems, and skill gems (by uncut gem level). Rares and magic items have no market price
on poe.ninja; they come back with their mods and an official trade-site link so they can be checked
(Exiled Exchange, the trade site, or Claude reading that one search when asked)."""

import json
import re
import urllib.parse
import xml.etree.ElementTree as ET

from . import art, db, gamedata, money, ninja, vault

UNIQUE_CATS = set(ninja.ITEM_TYPES)
STAGE_LIMITS = [(1, 'start: cheap, buy first'), (20, 'mid: main upgrades'), (float('inf'), 'endgame: big purchases')]


def _latest_index(con, league):
    rows = con.execute(
        """SELECT p.* FROM price p JOIN (SELECT item_key, category, MAX(ts) mts FROM price WHERE league=?
           GROUP BY item_key, category) m ON p.item_key=m.item_key AND p.category=m.category AND p.ts=m.mts
           WHERE p.league=?""", (league, league)).fetchall()
    by_name = {}
    for r in rows:
        name = r['name']
        if r['category'] in UNIQUE_CATS:  # strip ' (variant)' / ' [corrupted]' we appended for uniques
            name = re.sub(r' \(.*?\)$', '', re.sub(r' \[corrupted\]$', '', name))
        by_name.setdefault(name.lower(), []).append(dict(r))
    return by_name


def parse_item(text):
    lines = [l.strip() for l in (text or '').splitlines() if l.strip()]
    it = {'rarity': '', 'name': '', 'base': '', 'runes': [], 'mods': [], 'corrupted': False}
    if not lines or not lines[0].startswith('Rarity:'):
        return it
    it['rarity'] = lines[0].split(':', 1)[1].strip().upper()
    i = 1
    it['name'] = lines[i] if i < len(lines) else ''
    if it['rarity'] in ('RARE', 'UNIQUE') and i + 1 < len(lines):
        it['base'] = lines[i + 1]
        i += 2
    else:
        it['base'] = it['name']
        i += 1
    n_impl, past_impl = 0, False
    for l in lines[i:]:
        if l.startswith('Rune:'):
            it['runes'].append(l.split(':', 1)[1].strip())
        elif l == 'Corrupted':
            it['corrupted'] = True
        elif l.startswith('Implicits:'):
            n_impl, past_impl = int(l.split(':')[1] or 0), True
        elif past_impl:
            mod = re.sub(r'\{[^}]*\}', '', l).strip()
            if n_impl > 0:
                n_impl -= 1
                continue  # skip implicits/enchants; explicits are what you pay for
            if mod:
                it['mods'].append(mod)
    return it


def parse_build(xml_text):
    root = ET.fromstring(xml_text)
    items = {it.get('id'): parse_item(it.text) for it in root.iter('Item')}
    equipped = []
    for slot in root.iter('Slot'):
        iid = slot.get('itemId')
        if iid and iid != '0' and iid in items:
            equipped.append(dict(items[iid], slot=slot.get('name'), swap='Swap' in (slot.get('name') or '')))
    spec = None
    tree = root.find('Tree')
    if tree is not None:
        specs = tree.findall('Spec')
        try:
            spec = specs[int(tree.get('activeSpec', '1')) - 1]
        except (IndexError, ValueError):
            spec = specs[0] if specs else None
    if spec is not None:
        for s in spec.iter('Socket'):
            iid = s.get('itemId')
            if iid and iid != '0' and iid in items:
                equipped.append(dict(items[iid], slot=f'Jewel socket {s.get("nodeId")}', swap=False))
    gems = []
    for g in root.iter('Gem'):
        if g.get('enabled') == 'false':
            continue
        gid = g.get('gemId') or ''
        gems.append({'name': g.get('nameSpec') or '', 'level': int(float(g.get('level') or 1)),
                     'support': 'SupportGem' in gid,
                     'ascendancy': 'Ascendancy' in gid or (g.get('variantId') or '').startswith('Ascendancy')})
    return equipped, gems


def _pick_unique(cands, base, corrupted):
    u = [c for c in cands if c['category'] in UNIQUE_CATS]
    if not u:
        return None, []
    same_base = [c for c in u if (c.get('base') or '').lower() == base.lower()] or u
    pool = [c for c in same_base if c['name'].endswith('[corrupted]') == corrupted] or same_base
    best = max(pool, key=lambda c: c.get('listings') or 0)
    others = [c for c in u if c is not best]
    return best, others


def _stage(v):
    for lim, label in STAGE_LIMITS:
        if v < lim:
            return label
    return STAGE_LIMITS[-1][1]


def _trade_link(league, base, rarity='rare'):
    q = {'query': {'status': {'option': 'online'}, 'type': base,
                   'filters': {'type_filters': {'filters': {'rarity': {'option': rarity}}}}},
         'sort': {'price': 'asc'}}
    return (f'https://www.pathofexile.com/trade2/search/poe2/{urllib.parse.quote(league)}?q='
            + urllib.parse.quote(json.dumps(q, separators=(',', ':'))))


def trade_link_unique(league, name, base):
    q = {'query': {'status': {'option': 'online'}, 'name': name, 'type': base}, 'sort': {'price': 'asc'}}
    return (f'https://www.pathofexile.com/trade2/search/poe2/{urllib.parse.quote(league)}?q='
            + urllib.parse.quote(json.dumps(q, separators=(',', ':'))))


def slot_values(con, build_id, league=None):
    """Per-slot value for the character page: unique price (name+base), socketed runes/cores, trade links."""
    league = league or ninja.current_league(con)
    r = build_cost(con, build_id=build_id, league=league, include_swap=True)
    slots = {}
    for e in r.get('all_priced', []) + r['most_expensive']:
        if e['slot'] == 'gem':
            continue
        d = slots.setdefault(e['slot'], {'value_div': 0.0, 'parts': []})
        if e['item'] in [x['item'] for x in d['parts']]:
            continue
        d['value_div'] += e['value_div']
        d['parts'].append({'item': e['item'], 'kind': e['kind'], 'value_div': e['value_div']})
    for u in r['needs_a_price_check']:
        d = slots.setdefault(u['slot'], {'value_div': 0.0, 'parts': []})
        d['trade_link'] = u.get('trade_link')
        d['unpriced'] = u['kind']
        d['quality'] = u.get('quality')
    gems = sum(e['value_div'] for e in r.get('all_priced', []) if e['slot'] == 'gem')
    return {'league': league, 'slots': slots, 'gems_div': round(gems, 3), 'total_div': r['priced_total_div'],
            'rares_unpriced': sum(1 for u in r['needs_a_price_check'] if u['kind'] == 'rare'),
            'caveat': 'Uniques at a typical roll, runes and gems at poe.ninja prices. Rares need a trade check.'}


def build_cost(con, pob_code=None, build_id=None, league=None, include_swap=False):
    league = league or ninja.current_league(con)
    if build_id is not None:
        b = con.execute('SELECT label, pob_code FROM build WHERE id=?', (int(build_id),)).fetchone()
        if not b:
            raise ValueError('no such build in the vault')
        label, pob_code = b['label'], b['pob_code']
    else:
        label = 'pasted build'
    equipped, gems = parse_build(vault.decode(pob_code))
    idx = _latest_index(con, league)
    if not idx:
        raise ValueError(f'No stored prices for {league}. Run poe2_refresh first.')
    rates = json.loads(db.kv_get(con, f'rates:{league}', '{}') or '{}')

    priced, unpriced, cheap = [], [], []

    def add_priced(kind, what, slot, row, note=None, others=None):
        e = {'kind': kind, 'item': what, 'slot': slot, 'value_div': round(row['value'] or 0, 3),
             'listings': row.get('listings'), 'volume': row.get('volume'), 'icon': row.get('icon')}
        if note:
            e['note'] = note
        if not e.get('icon'):
            nm = what.split(' (')[0]
            e['art'] = art.find('unique', nm) or art.find('skill', nm) or art.find('base', nm)
        if others:
            e['other_versions'] = [f"{o['name']} / {o.get('base') or '?'}: {o['value']:.2f} div" for o in others[:4]]
        priced.append(e)

    for it in equipped:
        if it['swap'] and not include_swap:
            continue
        slot = it['slot']
        if it['rarity'] == 'UNIQUE':
            best, others = _pick_unique(idx.get(it['name'].lower(), []), it['base'], it['corrupted'])
            if best:
                note = 'price is for a typical copy; top rolls / extra mods cost more'
                if it['corrupted']:
                    note += ' (corrupted)'
                add_priced('unique', f"{it['name']} ({it['base']})", slot, best, note, others)
                priced[-1]['trade_link'] = trade_link_unique(league, it['name'], it['base'])
            else:
                unpriced.append({'kind': 'unique', 'item': f"{it['name']} ({it['base']})", 'slot': slot,
                                 'why': 'not on poe.ninja for this league (rare unique or new)',
                                 'trade_link': _trade_link(league, it['base'], 'unique')})
        elif it['rarity'] == 'RARE':
            try:
                rd = gamedata.read_item(it['base'], it['mods'])
                tiers = [(f"T{m['tier']} {m['roll_pct']}%" if m.get('tier') and m['tiers'] > 1 else
                          f"{m['roll_pct']}% roll" if m.get('tier') else '?') + f" | {m['text']}" for m in rd['mods']]
                quality = rd['quality']
            except (OSError, ValueError):
                tiers, quality = it['mods'], 'unread (game data missing: run gamedata.update())'
            unpriced.append({'kind': 'rare', 'item': f"{it['name']} ({it['base']})", 'slot': slot,
                             'quality': quality, 'mods': tiers, 'trade_link': _trade_link(league, it['base']),
                             'art': art.find('base', it['base'])})
        else:
            cheap.append(f"{slot}: {it['name']} ({it['rarity'].lower()}, usually cheap)")
        for rn in it['runes']:
            cands = [c for c in idx.get(rn.lower(), []) if c['category'] not in UNIQUE_CATS]
            if cands:
                add_priced('socketed', rn, slot, cands[0])
            else:
                cheap.append(f'{slot}: {rn} (socketed, no price found)')

    seen = set()
    for g in gems:
        if g['ascendancy']:
            continue
        key = (g['name'], g['level'], g['support'])
        if key in seen:
            continue
        seen.add(key)
        lineage = [c for c in idx.get(g['name'].lower(), []) if c['category'] == 'LineageSupportGems']
        if lineage:
            add_priced('lineage support', g['name'], 'gem', lineage[0])
        elif g['support'] and (gamedata.gem_info(g['name']) or {}).get('lineage'):
            unpriced.append({'kind': 'lineage support', 'item': g['name'], 'slot': 'gem',
                             'why': 'lineage gem not listed on poe.ninja this league'})
        elif not g['support'] and g['level'] <= 1:
            cheap.append(f"skill: {g['name']} (level 1, usually granted by an item or free)")
        elif not g['support']:
            lvl = min(g['level'], 20)
            info = gamedata.gem_info(g['name']) or {}
            kind_name = 'spirit' if info.get('type') == 'spirit' else 'skill'
            row = (idx.get(f'uncut {kind_name} gem (level {lvl})') or [None])[0]
            note = ('level 21+ needs corruption or +level gear: price is the level-20 uncut gem'
                    if g['level'] > 20 else None)
            if row:
                add_priced(f'{kind_name} gem', f"{g['name']} (level {g['level']})", 'gem', row, note)
        else:
            cheap.append(f"support: {g['name']} (regular support, cheap)")

    rt = money.rates(con, league)
    priced.sort(key=lambda e: -e['value_div'])
    money.annotate(priced, rt)
    total = sum(e['value_div'] for e in priced)
    steps = {}
    for e in sorted(priced, key=lambda e: e['value_div']):
        steps.setdefault(_stage(e['value_div']), []).append(f"{e['item']} — {e['price']}")
    ex_per_div = rates.get('exalted')
    return {
        'build': label, 'league': league,
        'priced_total': money.fmt(total, rt),
        'priced_total_div': round(total, 2),
        'priced_total_exalted': round(total * ex_per_div) if ex_per_div else None,
        'rate': f"1 div = {ex_per_div:g} ex = {rates.get('chaos', 0):g} chaos" if ex_per_div else None,
        'most_expensive': priced[:5],
        'buy_order': steps,
        'all_priced': priced,
        'needs_a_price_check': unpriced,
        'cheap_or_free': cheap,
        'caveats': ['Rares are not included in the total: check them (Exiled Exchange or the trade links).',
                    'Unique prices are for typical rolls; perfect or desecrated-mod copies cost more.',
                    'Prices are poe.ninja estimates from the last snapshot.',
                    'Gems are priced as the uncut gem of their level (skill or spirit, from game data).',
                    'Rares get a quality read (mod tiers and rolls); a price estimate for them needs checks '
                    'to learn from (price memory, next).'],
    }
