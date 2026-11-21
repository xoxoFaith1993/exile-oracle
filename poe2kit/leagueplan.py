"""League start planner: any class, any chain of ascendancies (they can be changed at any time), aimed at a
target build. Everything comes from data:
- quest rewards / permanent buffs per act: Path of Building's QuestRewards table (dumped to JSON);
- classes, ascendancies and their nodes: PoB's passive tree;
- skill gems by unlock tier, attribute and tags: the game data export;
- cheap leveling uniques: live poe.ninja prices (level requirement from the same data).
Acts 5-6 arrive with 1.0 (re-dump QuestRewards after PoB updates)."""

import json
import os
import re

from . import character, config, db, gamedata, money, ninja

QUESTS = config.data_file('quest_rewards.json')
# main attributes per class (gem requirement weights)
CLASS_ATTR = {'Witch': {'intelligence'}, 'Sorceress': {'intelligence'}, 'Ranger': {'dexterity'},
              'Huntress': {'dexterity'}, 'Warrior': {'strength'}, 'Mercenary': {'strength', 'dexterity'},
              'Monk': {'dexterity', 'intelligence'}, 'Druid': {'strength', 'intelligence'},
              'Shadow': {'dexterity', 'intelligence'}, 'Duelist': {'strength', 'dexterity'}}
ATTR_SLOTS = {'intelligence': ('Wand', 'Staff', 'Focus', 'Sceptre'), 'dexterity': ('Bow', 'Quarterstaff', 'Spear'),
              'strength': ('Mace', 'Two Hand Mace', 'Shield')}


def quests():
    with open(QUESTS, encoding='utf-8') as f:
        return json.load(f)


def classes():
    t = character.tree('0_5')
    return [{'name': c['name'], 'ascendancies': [a['name'] for a in c['ascendancies']]} for c in t['classes']]


def asc_nodes(ascendancy, con=None):
    """Notables + small nodes of an ascendancy, with how often your saved builds took each one."""
    t = character.tree('0_5')
    nodes = [n for n in t['nodes'] if n.get('a') == ascendancy and n['k'] in ('notable', 'small', 'keystone')]
    taken = {}
    if con is not None:
        for r in con.execute('SELECT id FROM build WHERE ascendancy=?', (ascendancy,)).fetchall():
            try:
                c = character.character(con, r['id'])
            except Exception:
                continue
            for a in c['ascendancy_nodes']:
                taken[a['name']] = taken.get(a['name'], 0) + 1
    out, seen = [], {}
    for n in nodes:
        if not n.get('n'):
            continue
        if n['n'] in seen:  # small nodes repeat (e.g. six "Life" nodes): show once with a count
            seen[n['n']]['copies'] += 1
            continue
        seen[n['n']] = {'name': n['n'], 'notable': n['k'] != 'small', 'stats': n['s'], 'art': n['i'],
                        'your_builds_took': taken.get(n['n'], 0), 'copies': 1}
        out.append(seen[n['n']])
    out.sort(key=lambda x: (-x['your_builds_took'], not x['notable'], x['name']))
    return out


def skills(class_name, target_tags=None, mine=None):
    """Active/spirit gems for this class's attributes, sorted by unlock tier, best matches to the target first."""
    attrs = CLASS_ATTR.get(class_name, {'intelligence'})
    target_tags = set(target_tags or [])
    mine = set(n.lower() for n in (mine or []))
    out = []
    for v in gamedata.load('skill_gems').values():
        bi = v.get('base_item') or {}
        name = bi.get('display_name')
        if not name or bi.get('release_state') != 'released' or v.get('gem_type') not in ('active', 'spirit'):
            continue
        if 'Ascendancy' in (bi.get('id') or '') or 'grants_active_skill' not in v.get('tags', []):
            continue
        w = v.get('requirement_weights') or {}
        main = max(w, key=w.get) if w else None
        if main not in attrs:
            continue
        tags = set(v.get('tags', []))
        match = len(tags & target_tags)
        out.append({'name': name, 'type': v['gem_type'], 'tier': v.get('crafting_level', 0), 'tags': sorted(tags - {'grants_active_skill', 'intelligence', 'dexterity', 'strength'})[:6],
                    'match': match, 'yours': name.lower() in mine})
    uniq = {}
    for g in out:
        uniq.setdefault(g['name'], g)
    out = list(uniq.values())
    out.sort(key=lambda g: (-g['yours'], g['tier'] if g['yours'] else 0, -g['match'], g['tier'], g['name']))
    return out


def _tidy(t):
    """poe.ninja mod text uses [Tag|Shown text] links: keep the shown text."""
    return re.sub(r'\[([^\]|]*\|)?([^\]]*)\]', r'\2', t or '').replace('\n', ' · ')


def leveling_uniques(con, class_name, max_level=45, budget_div=0.05, league=None):
    """Cheap uniques usable while leveling (poe.ninja level requirement), by price."""
    league = league or ninja.current_league(con)
    rows = con.execute("SELECT url, body FROM http_cache WHERE url LIKE '%stash/current/item/overview%' AND url LIKE ?",
                       (f"%league={league.replace(' ', '+')}%",)).fetchall()
    if not rows:
        rows = con.execute("SELECT url, body FROM http_cache WHERE url LIKE '%stash/current/item/overview%'").fetchall()
    rt = money.rates(con, league)
    attrs = CLASS_ATTR.get(class_name, {'intelligence'})
    reqs = {}
    for b in gamedata.load('base_items').values():
        if b.get('name') and b['name'] not in reqs:
            reqs[b['name']] = (b.get('requirements') or {}, b.get('item_class'))
    out = []
    for r in rows:
        try:
            d = json.loads(r['body'])
        except Exception:
            continue
        for ln in d.get('lines', []):
            req, iclass = reqs.get(ln.get('baseType'), ({}, None))
            if (iclass or '') in ('Tablet', 'Relic', 'SanctumRelic', 'PrecursorTablet') or \
                    any(w in (ln.get('baseType') or '') for w in ('Tablet', 'Relic')):
                continue  # endgame tablets / sanctum relics aren't leveling gear
            need = {a for a in ('strength', 'dexterity', 'intelligence') if (req.get(a) or 0) > 0}
            if need and not (need <= attrs or (need & attrs and len(need) == 2)):
                continue  # e.g. a bow (dex) for a Witch (int)
            if iclass in ('Bow', 'Crossbow', 'Quiver', 'Warstaff', 'Spear', 'Flail', 'One Hand Mace', 'Two Hand Mace',
                          'Claw', 'Dagger', 'One Hand Sword', 'Two Hand Sword', 'One Hand Axe', 'Two Hand Axe') \
                    and 'strength' not in attrs and 'dexterity' not in attrs:
                continue  # martial weapons only for str/dex classes
            lvl, v = (ln.get('levelRequired') or req.get('level') or 0), ln.get('primaryValue') or 0
            if ln.get('corrupted') or not v or v > budget_div or lvl > max_level or (ln.get('listingCount') or 0) < 5:
                continue
            out.append({'name': ln['name'], 'base': ln.get('baseType'), 'category': ln.get('category'), 'level': lvl,
                        'value_div': round(v, 4), 'price': money.fmt(v, rt), 'icon': ln.get('icon'),
                        'mods': [_tidy(m.get('text')) for m in (ln.get('explicitModifiers') or [])][:4]})
    out.sort(key=lambda x: (x['level'], x['value_div']))
    seen, res = set(), []
    for x in out:
        if x['name'] not in seen:
            seen.add(x['name'])
            res.append(x)
    return res


def plan(con, class_name='Witch', ascendancies=('Blood Mage',), target_build=None, budget_div=0.05):
    target_tags, mine, target = set(), [], None
    if target_build:
        c = character.character(con, int(target_build))
        target = {'id': c['id'], 'label': c['label'], 'ascendancy': c['ascendancy'], 'main_skill': c['main_skill'],
                  'keystones': [k['name'] for k in c['keystones']]}
        for g in c['skills']:
            for gem in g['gems']:
                mine.append(gem['name'])
        info = gamedata.gem_info(c['main_skill'] or '') or {}
        target_tags = set(info.get('tags', [])) - {'grants_active_skill', 'intelligence', 'dexterity', 'strength'}
    qs = quests()
    acts = {}
    for q in qs:
        acts.setdefault(q.get('Description', f"Act {q.get('Act')}"), []).append({
            'area': q.get('Area'), 'area_level': q.get('AreaLevel'), 'what': q.get('Info'),
            'reward': q.get('Stat'), 'choices': [o.replace('\n\t', ' + ') for o in (q.get('Options') or [])],
            'passive_points': q.get('questPoints')})
    return {
        'class': class_name, 'ascendancy_path': list(ascendancies), 'target': target,
        'acts': acts,
        'ascendancy_points': ('Your first ascendancy points come from the campaign trials (Trial of the Sekhemas or '
                              'the Trial of Chaos). You can change ascendancy later, so a path like '
                              f"{' → '.join(ascendancies)} works: take what levels fastest first."),
        'ascendancies': {a: asc_nodes(a, con)[:14] for a in ascendancies},
        'skills': skills(class_name, target_tags, mine)[:24],
        'leveling_uniques': leveling_uniques(con, class_name, budget_div=budget_div)[:30],
        'notes': ['Quest rewards from Path of Building; Acts 5–6 are added when 1.0 releases.',
                  'Skill "tier" = the uncut gem level needed to cut it (higher tiers drop later in the campaign).',
                  'Leveling uniques: cheapest with at least 5 listings and level requirement ≤ 45.'],
    }
