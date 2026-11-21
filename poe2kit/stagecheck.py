"""Check a levelling route in Path of Building: a character at level L with the route's passives taken by then,
one skill + supports at the gem levels available by then, and no gear (so it's the floor: gear only adds).
Used to choose levelling skills/supports and to show how the build grows stage by stage."""

import re
import xml.etree.ElementTree as ET

from . import pob, route


def _gem_info(gem_id):
    import os
    from . import config
    text = open(os.path.join(config.POB_DIR, 'src', 'Data', 'Gems.lua'), encoding='utf-8').read()
    for b in text.split('\n\t["')[1:]:
        if f'gameId = "{gem_id}"' in b:
            name = re.search(r'\n\t\tname = "([^"]+)"', b)
            eff = re.search(r'grantedEffectId = "([^"]+)"', b)
            var = re.search(r'variantId = "([^"]+)"', b)
            return {'name': name.group(1) if name else gem_id, 'skillId': eff.group(1) if eff else '',
                    'variantId': var.group(1) if var else ''}
    return None


def _gem_level_at(gem_id, char_level):
    g = route._gem_data().get(gem_id) or {}
    req = g.get('req') or [0]
    return max(1, sum(1 for r in req if r <= char_level)) if 'SupportGem' not in gem_id else 1


def stage_xml(base_xml, level, skill, supports=()):
    """base_xml: the target build (its tree + class/ascendancy). Keeps only what the route has by this level."""
    root = ET.fromstring(base_xml)
    b = root.find('Build')
    b.set('level', str(level))
    b.set('mainSocketGroup', '1')
    tree = root.find('Tree')
    spec = tree.findall('Spec')[max(0, int(tree.get('activeSpec') or 1) - 1)]
    have = [int(x) for x in (spec.get('nodes') or '').split(',') if x]
    main, asc, _ = route.order(have, spec.get('treeVersion') or '0_5', b.get('className'))
    keep = [n for n, lv in zip(main, route.levels(len(main))) if lv <= level]
    keep += [n for n, lv in zip(asc, route.asc_levels(len(asc))) if lv <= level]
    spec.set('nodes', ','.join(map(str, keep)))
    for el in list(root):
        if el.tag in ('Skills', 'Items'):
            root.remove(el)
    skills = ET.SubElement(root, 'Skills', {'activeSkillSet': '1'})
    ss = ET.SubElement(skills, 'SkillSet', {'id': '1'})
    grp = ET.SubElement(ss, 'Skill', {'enabled': 'true', 'mainActiveSkill': '1', 'includeInFullDPS': 'true'})
    for gid in (skill,) + tuple(supports):
        info = _gem_info(gid)
        if not info:
            continue
        ET.SubElement(grp, 'Gem', {'gemId': gid, 'skillId': info['skillId'], 'variantId': info['variantId'],
                                   'nameSpec': info['name'], 'level': str(_gem_level_at(gid, level)),
                                   'quality': '0', 'enabled': 'true'})
    ET.SubElement(root, 'Items')
    return ET.tostring(root, encoding='unicode'), len(keep)


def check(base_xml, level, skill, supports=()):
    xml, n = stage_xml(base_xml, level, skill, supports)
    res = pob.calc(xml, use_cache=True)
    st = pob.key_stats(res)
    return {'level': level, 'passives': n, 'skill': res.get('main_skill'),
            'dps': st.get('DPS (combined)') or st.get('DPS (main skill)'), 'life': st.get('life'),
            'mana': st.get('mana'), 'es': st.get('energy shield')}


_cat = {}


def catalogue():
    """Every gem PoB knows: name (lower) -> {name, id, support, tier, level (first cuttable), tags}."""
    if _cat:
        return _cat
    import os
    from . import config
    text = open(os.path.join(config.POB_DIR, 'src', 'Data', 'Gems.lua'), encoding='utf-8').read()
    for b in text.split('\n\t["')[1:]:
        g = re.search(r'gameId = "([^"]+)"', b)
        n = re.search(r'\n\t\tname = "([^"]+)"', b)
        if not (g and n):
            continue
        tags = re.search(r'tags = \{(.*?)\n\t\t\}', b, re.S)
        _cat.setdefault(n.group(1).lower(), {
            'name': n.group(1), 'id': g.group(1), 'support': 'SupportGem' in g.group(1),
            'tags': sorted(set(re.findall(r'(\w+) = true', tags.group(1) if tags else '')) - {'grants_active_skill'}),
            'level': route.gem_level(g.group(1))})
    return _cat


def rank(base_xml, level, skill, supports=(), candidates=None, kind='supports', limit=30):
    """kind='supports': each cuttable support (by `level`) added to skill+supports, ranked by DPS gain.
    kind='skills': each candidate skill (names) with the given supports, ranked by DPS."""
    cat = catalogue()
    sk = cat.get(str(skill).lower())
    if kind == 'supports' and not sk:
        raise ValueError(f'unknown skill {skill}')
    sup_ids = tuple(cat[x.lower()]['id'] for x in supports if x.lower() in cat)
    if kind == 'skills':
        out = []
        for name in candidates or []:
            g = cat.get(str(name).lower())
            if not g:
                out.append({'skill': name, 'error': 'unknown gem'})
                continue
            r = check(base_xml, level, g['id'], sup_ids)
            out.append({'skill': g['name'], 'dps': r['dps'], 'cuttable_from': g['level']})
        return sorted(out, key=lambda x: -(x.get('dps') or 0))
    base = check(base_xml, level, sk['id'], sup_ids)['dps'] or 0
    want = set(sk['tags']) & {'spell', 'attack', 'projectile', 'area', 'lightning', 'fire', 'cold', 'chaos',
                              'physical', 'minion', 'duration', 'melee', 'critical'}
    pool = [g for g in cat.values() if g['support'] and g['level'] and g['level'] <= level and g['id'] not in sup_ids
            and (set(g['tags']) & want or not g['tags'])]
    pool = sorted(pool, key=lambda g: -len(set(g['tags']) & want))[:limit]
    out = []
    for g in pool:
        d = check(base_xml, level, sk['id'], sup_ids + (g['id'],))['dps'] or 0
        out.append({'support': g['name'], 'gain_pct': round((d / base - 1) * 100, 1) if base else None,
                    'cuttable_from': g['level']})
    return {'skill': sk['name'], 'level': level, 'base_dps': base,
            'ranked': sorted(out, key=lambda x: -(x['gain_pct'] or 0))}
