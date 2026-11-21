"""Everything the dashboard's poe.ninja-style character page needs, from one Build Vault entry:
gear by slot (full item text, rarity, art), jewels, skill groups with gem icons, PoB stats, allocated tree
(keystones, notables, ascendancy) and the tree geometry to draw it."""

import json
import math
import os
import re
import subprocess
import xml.etree.ElementTree as ET

from . import ninja, art, config, gamedata, pob, vault

TREE_DIR = os.path.join(config.DATA_DIR, 'tree')
SLOT_ORDER = ['Weapon 1', 'Weapon 2', 'Helmet', 'Body Armour', 'Gloves', 'Boots', 'Amulet', 'Ring 1', 'Ring 2',
              'Ring 3', 'Belt', 'Charm 1', 'Charm 2', 'Charm 3', 'Flask 1', 'Flask 2', 'Weapon 1 Swap',
              'Weapon 2 Swap']


# ---------------- tree geometry ----------------

def _dump_tree(version):
    raw = os.path.join(TREE_DIR, f'raw_{version}.json')
    if not os.path.exists(raw):
        os.makedirs(TREE_DIR, exist_ok=True)
        p = pob.run(os.path.join(config.ROOT, 'pobhost', 'treedump.lua'), {'TREE_VERSION': version, 'POB_OUT': raw})
        if p.returncode != 0 or not os.path.exists(raw):
            raise RuntimeError('tree dump failed: ' + (p.stderr or p.stdout)[-400:])
    with open(raw, encoding='utf-8') as f:
        return json.load(f)


def tree(version):
    """Compact render data: nodes with x/y and type, edges (straight or arc), per tree version (cached)."""
    out = os.path.join(TREE_DIR, f'tree_{version}.json')
    if os.path.exists(out):
        with open(out, encoding='utf-8') as f:
            return json.load(f)
    d = _dump_tree(version)
    radii = d['constants']['orbitRadii']
    angles = d['constants']['orbitAnglesByOrbit']
    groups = d['groups']
    pos, nodes = {}, []
    for sid, n in d['nodes'].items():
        g = groups.get(str(n.get('g')))
        if g is None or n.get('o') is None:
            continue
        o, oi = n['o'], n.get('oi', 0)
        a = angles[o][oi] if o < len(angles) and oi < len(angles[o]) else 0
        r = radii[o] if o < len(radii) else 0
        x, y = g['x'] + math.sin(a) * r, g['y'] - math.cos(a) * r
        pos[sid] = (x, y, n.get('g'), o)
        kind = ('keystone' if n.get('ks') else 'notable' if n.get('nt') else 'jewel' if n.get('js') else
                'mastery' if n.get('ms') else 'start' if n.get('cls') is not None or n.get('ascStart') else
                'attribute' if n.get('attr') else 'small')
        icon = n.get('icon')
        nodes.append({'id': int(sid), 'x': round(x, 1), 'y': round(y, 1), 'k': kind, 'n': n.get('name'),
                      's': n.get('stats') or [], 'a': n.get('asc'),
                      'i': (icon or '').replace('\\', '/').lower()[:-4] + '.png' if icon else None})
    edges, seen = [], set()
    for sid, n in d['nodes'].items():
        if sid not in pos:
            continue
        for cid, orbit in n.get('c', []):
            cid = str(cid)
            if cid not in pos:
                continue
            key = tuple(sorted((int(sid), int(cid))))
            if key in seen:
                continue
            seen.add(key)
            if bool(d['nodes'][sid].get('asc')) != bool(d['nodes'][cid].get('asc')):
                continue  # don't draw the line from the class start into the ascendancy area
            e = [int(sid), int(cid)]
            if orbit and abs(orbit) < len(radii):
                e += [radii[abs(orbit)], 1 if orbit > 0 else 0]  # arc radius + sweep direction
            edges.append(e)
    res = {'version': version, 'nodes': nodes, 'edges': edges,
           'classes': d.get('classes', [])}
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(res, f, separators=(',', ':'))
    return res


# ---------------- items ----------------

TAG = re.compile(r'\{([a-z]+)(?::[^}]*)?\}')


def _item(text):
    lines = [l.strip() for l in (text or '').splitlines() if l.strip()]
    it = {'rarity': 'NORMAL', 'name': '', 'base': '', 'props': [], 'implicits': [], 'explicits': [], 'runes': [],
          'enchants': [], 'corrupted': False, 'item_level': None, 'quality': None, 'req_level': None, 'sockets': None}
    if not lines:
        return it
    i = 0
    if lines[0].startswith('Rarity:'):
        it['rarity'] = lines[0].split(':', 1)[1].strip().upper()
        i = 1
    it['name'] = lines[i] if i < len(lines) else ''
    if it['rarity'] in ('RARE', 'UNIQUE') and i + 1 < len(lines):
        it['base'] = lines[i + 1]
        i += 2
    else:
        it['base'] = it['name']
        i += 1
    n_impl = None
    for l in lines[i:]:
        if l.startswith(('Unique ID:', 'Selected Variant', 'Variant:', 'Has Alt Variant', 'Catalyst',
                         'LevelReq: 0', 'Prefix:', 'Suffix:')):
            continue
        if l.startswith('Item Level:'):
            it['item_level'] = l.split(':', 1)[1].strip()
            continue
        if l.startswith('Quality:'):
            it['quality'] = l.split(':', 1)[1].strip()
            continue
        if l.startswith('LevelReq:'):
            it['req_level'] = l.split(':', 1)[1].strip()
            continue
        if l.startswith('Sockets:'):
            it['sockets'] = l.split(':', 1)[1].strip()
            continue
        if l.startswith('Rune:'):
            it['runes'].append(l.split(':', 1)[1].strip())
            continue
        if l == 'Corrupted':
            it['corrupted'] = True
            continue
        if l.startswith('Implicits:'):
            n_impl = int(l.split(':', 1)[1] or 0)
            continue
        if n_impl is None:
            if ':' in l and not l.startswith('{'):
                it['props'].append(l)  # Energy Shield: 589, Charm Slots: 2 ...
            continue
        tags = TAG.findall(l)
        text = TAG.sub('', l).strip()
        entry = {'t': text, 'tags': tags}
        if n_impl > 0:
            n_impl -= 1
            (it['enchants'] if ('enchant' in tags or 'rune' in tags) else it['implicits']).append(entry)
        else:
            it['explicits'].append(entry)
    return it


def _base_for_magic(name):
    """'Sunny Stone Charm of the Copious' -> 'Stone Charm' (longest known base name inside the name)."""
    best = None
    words = name.split()
    for a in range(len(words)):
        for b in range(len(words), a, -1):
            cand = ' '.join(words[a:b])
            if (best is None or len(cand) > len(best)) and gamedata.base_info(cand):
                best = cand
    return best or name


# ---------------- character ----------------

def character(con, build_id):
    r = con.execute('SELECT * FROM build WHERE id=?', (int(build_id),)).fetchone()
    if not r:
        raise ValueError('no such build in the vault')
    xml = vault.decode(r['pob_code'])
    root = ET.fromstring(xml)
    b = root.find('Build')
    items = {it.get('id'): it for it in root.iter('Item')}

    def item_out(iid, slot):
        el = items.get(iid)
        if el is None:
            return None
        it = _item(el.text)
        base = it['base'] if it['rarity'] in ('RARE', 'UNIQUE') else _base_for_magic(it['name'])
        it['base_type'] = base
        it['slot'] = slot
        it['art'] = (art.find('unique', it['name']) if it['rarity'] == 'UNIQUE' else None) or art.find('base', base)
        if it['rarity'] == 'RARE':
            try:
                rd = gamedata.read_item(base, [m['t'] for m in it['explicits']])
                for m, t in zip(it['explicits'], rd['mods']):
                    if t.get('tier'):
                        m['tier'] = t['tier'] if t['tiers'] > 1 else None
                        m['roll'] = t['roll_pct']
            except (OSError, ValueError):
                pass
        return it

    gear = []
    for slot in root.iter('Slot'):
        iid = slot.get('itemId')
        if iid and iid != '0' and slot.get('name') in SLOT_ORDER:
            o = item_out(iid, slot.get('name'))
            if o:
                gear.append(o)
    tree_el = root.find('Tree')
    specs = tree_el.findall('Spec') if tree_el is not None else []
    try:
        spec = specs[int(tree_el.get('activeSpec', '1')) - 1]
    except (IndexError, ValueError, AttributeError):
        spec = specs[0] if specs else None
    jewels = []
    allocated, version = [], None
    if spec is not None:
        version = spec.get('treeVersion')
        allocated = [int(x) for x in (spec.get('nodes') or '').split(',') if x.strip().isdigit()]
        for s in spec.iter('Socket'):
            iid = s.get('itemId')
            if iid and iid != '0':
                o = item_out(iid, 'Jewel')
                if o:
                    o['node'] = int(s.get('nodeId'))
                    jewels.append(o)

    # skills
    groups = []
    skills = root.find('Skills')
    sets = skills.findall('SkillSet') if skills is not None else []
    active_set = (skills.get('activeSkillSet') if skills is not None else '1') or '1'
    sset = next((s for s in sets if s.get('id') == active_set), sets[0] if sets else skills)
    for gi, g in enumerate(sset.findall('Skill') if sset is not None else []):
        if g.get('source'):  # auto-added by PoB for skills granted by items/tree (the real group is listed too)
            continue
        gems = []
        for gem in g.findall('Gem'):
            name = gem.get('nameSpec') or ''
            info = gamedata.gem_info(name) or {}
            gems.append({'name': name, 'level': gem.get('level'), 'quality': gem.get('quality'),
                         'enabled': gem.get('enabled') != 'false',
                         'support': 'SupportGem' in (gem.get('gemId') or ''), 'lineage': info.get('lineage'),
                         'type': info.get('type'), 'art': art.find('skill', name)})
        if gems:
            groups.append({'index': gi + 1, 'label': g.get('label') or '', 'slot': g.get('slot'),
                           'enabled': g.get('enabled') != 'false', 'gems': gems})

    res = pob.calc(xml)
    out = res.get('output', {})
    by_group = {sg['index']: sg for sg in res.get('skill_groups', [])}
    for g in groups:
        sg = by_group.get(g['index'])
        if sg:
            g['dps'] = round(sg['dps']) if sg.get('dps', 0) > 0 else 0

    # allocated nodes -> keystones / notables / ascendancy
    tr = tree(version or '0_5')
    nodes = {n['id']: n for n in tr['nodes']}
    alloc_set = set(allocated)
    keystones = [nodes[i] for i in allocated if i in nodes and nodes[i]['k'] == 'keystone' and not nodes[i]['a']]
    notables = [nodes[i] for i in allocated if i in nodes and nodes[i]['k'] == 'notable' and not nodes[i]['a']]
    asc = [nodes[i] for i in allocated if i in nodes and nodes[i]['a'] and nodes[i]['k'] not in ('start',)]
    missing = [i for i in allocated if i not in nodes]

    def st(*keys):
        for k in keys:
            if k in out:
                return out[k]
        return None

    stats = {
        'character': {'Attributes': f"{round(st('Str') or 0)} / {round(st('Dex') or 0)} / {round(st('Int') or 0)}",
                      'Movement Speed': f"{round((st('EffectiveMovementSpeedMod') or 1) * 100)}%",
                      'Item Rarity': f"{round(st('LootRarity') or 0)}%" if st('LootRarity') is not None else None,
                      'Charges': f"{round(st('PowerChargesMax') or 0)} / {round(st('FrenzyChargesMax') or 0)} / {round(st('EnduranceChargesMax') or 0)}"},
        'defensive': {'Life': st('Life'), 'Energy shield': st('EnergyShield'), 'Mana': st('Mana'),
                      'Spirit': st('Spirit'), 'Armour': st('Armour'), 'Evasion rating': st('Evasion'),
                      'Resistances': f"{round(st('FireResist') or 0)}% / {round(st('ColdResist') or 0)}% / "
                                     f"{round(st('LightningResist') or 0)}% / {round(st('ChaosResist') or 0)}%",
                      'Effective Health Pool': st('TotalEHP'),
                      'Max Hit': ' / '.join(str(round(st(k) or 0)) for k in (
                          'PhysicalMaximumHitTaken', 'FireMaximumHitTaken', 'ColdMaximumHitTaken',
                          'LightningMaximumHitTaken', 'ChaosMaximumHitTaken'))},
        'recovery': {'Mana regen': st('ManaRegenRecovery', 'ManaRegen'), 'Life regen': st('LifeRegenRecovery'),
                     'Life leech': st('LifeLeechGainRate'),
                     'Energy shield recharge': st('EnergyShieldRecharge')},
    }
    for sec in stats.values():
        for k, v in list(sec.items()):
            if v is None:
                del sec[k]
            elif isinstance(v, float):
                sec[k] = round(v, 1) if v < 100 else round(v)

    # value per slot (uniques, runes) + trade links, at current-league prices
    value = None
    try:
        from . import cost
        value = cost.slot_values(con, r['id'])
        for it in gear + jewels:
            key = it['slot'] if it['slot'] != 'Jewel' else f"Jewel socket {it.get('node')}"
            v = value['slots'].get(key) or {}
            it['value_div'] = round(v.get('value_div') or 0, 3) or None
            it['value_parts'] = v.get('parts', [])
            it['trade_link'] = v.get('trade_link')
            it['unpriced'] = v.get('unpriced')
            if it['rarity'] == 'UNIQUE' and not it['trade_link']:
                it['trade_link'] = cost.trade_link_unique(value['league'], it['name'], it['base'])
            if it['rarity'] == 'UNIQUE':
                rd = ninja.roll_dependent(con).get(re.sub(r'\s*\[corrupted\]$', '', it['name']))
                if rd:   # poe.ninja's single price for this unique is the cheapest roll: flag it as a floor
                    it['roll_dependent'] = rd
                    it['roll_text'] = [m['t'] for m in (it.get('explicits') or [])][:3]
            if it['rarity'] == 'RARE' and it.get('explicits'):
                # nobody publishes rare prices: estimate what crafting one like it costs (a floor for special mods)
                from . import crafting
                ilvl = int(re.sub(r'\D', '', str(it.get('item_level') or '')) or 0) or None
                est = crafting.estimate_rare(con, it.get('base_type') or it['base'], [m['t'] for m in it['explicits']],
                                             ilvl, value['league'])
                if est.get('est_div'):
                    it['estimate'] = est
        value['estimated_rares_div'] = round(sum((it.get('estimate') or {}).get('est_div') or 0
                                                 for it in gear + jewels), 2)
    except Exception as e:  # prices are a bonus; never break the page
        value = {'error': f'{type(e).__name__}: {e}'}

    return {
        'value': value,
        'id': r['id'], 'label': r['label'], 'owner': r['owner'], 'league': r['league'],
        'class': b.get('className') if b is not None else None,
        'ascendancy': b.get('ascendClassName') if b is not None else None,
        'level': b.get('level') if b is not None else None,
        'main_skill': res.get('main_skill'), 'main_group': res.get('main_group'),
        'dps': round(out.get('CombinedDPS') or out.get('TotalDPS') or 0),
        'gear': gear, 'jewels': jewels, 'skills': groups, 'stats': stats,
        'keystones': [{'name': n['n'], 'stats': n['s'], 'art': n['i']} for n in keystones],
        'notables': [{'name': n['n'], 'stats': n['s'], 'art': n['i']} for n in notables],
        'ascendancy_nodes': [{'name': n['n'], 'stats': n['s'], 'art': n['i'], 'notable': n['k'] == 'notable'}
                             for n in asc],
        'tree': {'version': tr['version'], 'allocated': [i for i in allocated if i in nodes],
                 'missing_nodes': len(missing), 'jewel_nodes': [j['node'] for j in jewels]},
        'points': {'passives': sum(1 for i in allocated if i in nodes and not nodes[i]['a'] and nodes[i]['k'] != 'start'),
                   'ascendancy': len(asc)},
        'warnings': res.get('warnings', []),
    }
