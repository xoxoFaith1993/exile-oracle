"""Build the PoE 2 atlas passive tree (nodes + links + positions) from the game files.

    python atlas_tree.py <atlasskillgraph.psg> <tables_dir> <out.json> [<statdescriptions_dir>]

Inputs:
  - metadata/atlasskillgraphs/atlasskillgraph.psg  (extract with: poe2x extract <_.index.bin> <dir> metadata/atlasskillgraphs)
  - tables_dir: the converted .datc64 tables (passiveskills.json, stats.json, atlaspassiveskillsubtrees.json)
Output: {orbits, roots, groups, nodes{graph_id: {...}}, links[[a,b,curv]], subtrees}

PSG layout (version 3, as read 2026-11-21, build 26744644), little-endian:
  u8 version, u8 unk, u8 orbit_count, u8[orbit_count] skills_per_orbit
  u32 root_count, root_count * (u32 graph_id, u32 unk)
  u32 group_count, per group:
     f32 x, f32 y, u32 flags, u32 unk, u8 unk, u32 node_count,
     per node: u32 graph_id, u32 orbit (radius index), u32 orbit_index,
               u32 conn_count, conn_count * (u32 graph_id, i32 curvature)
graph_id = PassiveSkills.PassiveSkillGraphId (not the row index).
"""
import json
import math
import os
import struct
import sys

# PoE 2 orbit radii (same numbers the character tree export uses; atlas uses the same graph engine).
ORBIT_RADII = [0, 82, 162, 335, 493, 662, 846, 251, 1080, 1322]


def read_psg(path):
    b = open(path, 'rb').read()
    o = 0

    def u8():
        nonlocal o
        v = b[o]; o += 1; return v

    def u32():
        nonlocal o
        v = struct.unpack_from('<I', b, o)[0]; o += 4; return v

    def i32():
        nonlocal o
        v = struct.unpack_from('<i', b, o)[0]; o += 4; return v

    def f32():
        nonlocal o
        v = struct.unpack_from('<f', b, o)[0]; o += 4; return v

    version = u8(); unk0 = u8(); n_orb = u8()
    orbits = [u8() for _ in range(n_orb)]
    roots = []
    for _ in range(u32()):
        roots.append(u32()); u32()
    groups = []
    for gi in range(u32()):
        x, y = f32(), f32()
        flags, unk1, unk2 = u32(), u32(), u8()
        nodes = []
        for _ in range(u32()):
            gid, orbit, idx = u32(), u32(), u32()
            conns = [(u32(), i32()) for _ in range(u32())]
            nodes.append({'id': gid, 'orbit': orbit, 'orbit_index': idx, 'out': conns})
        groups.append({'x': x, 'y': y, 'flags': flags, 'nodes': nodes})
    assert o == len(b), f'parsed {o} of {len(b)} bytes'
    return {'version': version, 'orbits': orbits, 'roots': roots, 'groups': groups}


def node_xy(group, node, orbits):
    """Same maths as the character tree: angle = 2*pi*index/skills_per_orbit (special-cased 16/40 in PoE 1;
    PoE 2 uses even spacing per orbit as far as we know)."""
    r = ORBIT_RADII[node['orbit']] if node['orbit'] < len(ORBIT_RADII) else 0
    n = orbits[node['orbit']] if node['orbit'] < len(orbits) else 1
    a = 2 * math.pi * node['orbit_index'] / max(n, 1)
    return group['x'] + r * math.sin(a), group['y'] - r * math.cos(a)


def main(psg, tables, out, csd_dir=None):
    g = read_psg(psg)
    ps = json.load(open(os.path.join(tables, 'passiveskills.json'), encoding='utf-8'))
    stats = json.load(open(os.path.join(tables, 'stats.json'), encoding='utf-8'))
    subs = json.load(open(os.path.join(tables, 'atlaspassiveskillsubtrees.json'), encoding='utf-8'))
    vtypes = json.load(open(os.path.join(tables, 'passiveskillvarianttypes.json'), encoding='utf-8'))
    vrows = json.load(open(os.path.join(tables, 'passiveskillvariants.json'), encoding='utf-8'))
    st = None
    if csd_dir:  # data/statdescriptions extracted with poe2x
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from csd import StatText
        st = StatText([os.path.join(csd_dir, f) for f in (
            'atlas_variant_stat_descriptions.csd', 'atlas_stat_descriptions.csd',
            'endgame_map_stat_descriptions.csd', 'map_stat_descriptions.csd') if os.path.exists(os.path.join(csd_dir, f))])

    def text_of(p):
        if not st or not p.get('Stats'):
            return []
        vals = [p.get(f'Stat{i}Value', 0) for i in range(1, 8)]
        return st.text([stats[s]['Id'] for s in p['Stats']], vals[:len(p['Stats'])])

    # multi-choice ("Select a bonus") keystones: VariantType -> PassiveSkillVariants rows (Type, Variant=row)
    options = {}
    for r in vrows:
        options.setdefault(r['Type'], []).append(r['Variant'])
    by_gid = {}
    for row, p in enumerate(ps):
        if p.get('SkillType') == 1:   # 1 = atlas passive (1734 rows in 0.5.x incl. unused/legacy)
            by_gid[p['PassiveSkillGraphId']] = (row, p)
    nodes, links = {}, []
    for gi, grp in enumerate(g['groups']):
        for n in grp['nodes']:
            row, p = by_gid.get(n['id'], (None, {}))
            x, y = node_xy(grp, n, g['orbits'])
            vals = [p.get(f'Stat{i}Value', 0) for i in range(1, 8)]
            nodes[n['id']] = {
                'row': row, 'id': p.get('Id'), 'name': p.get('Name'), 'group': gi,
                'x': round(x, 1), 'y': round(y, 1), 'orbit': n['orbit'], 'orbit_index': n['orbit_index'],
                'notable': p.get('IsNotable', False), 'keystone': p.get('IsKeystone', False),
                'root': p.get('IsRootOfAtlasTree', False), 'icon': p.get('Icon_DDSFile'),
                'subtree': None if p.get('AtlasSubTree') is None else subs[p['AtlasSubTree']]['Id'],
                'points_granted': p.get('SkillPointsGranted', 0),
                'stats': [{'id': stats[s]['Id'], 'value': vals[i] if i < len(vals) else None}
                          for i, s in enumerate(p.get('Stats', []))],
                'text': text_of(p),
                # gates: a Fortress map node (row in PassiveSkills, EndgameMapLayoutGraph) and an area level
                'requires_fortress_node': (ps[p['Requirement']]['Id'] if p.get('Requirement') is not None else None),
                'requires_area_level': p.get('_unk67') or None,
                'is_mastery_art': (p.get('Id') or '').startswith('AtlasGenericMastery'),
            }
            vt = p.get('VariantType') or 0
            if vt and vtypes[vt]['Id'] == p.get('Id'):
                nodes[n['id']]['choices'] = [{'id': ps[v]['Id'], 'name': ps[v]['Name'], 'text': text_of(ps[v])}
                                             for v in options.get(vt, [])]
            for to, curv in n['out']:
                links.append([n['id'], to, curv])
    res = {'source': os.path.basename(psg), 'psg_version': g['version'], 'skills_per_orbit': g['orbits'],
           'orbit_radii_assumed': ORBIT_RADII, 'roots': g['roots'], 'group_count': len(g['groups']),
           'groups': [{'x': round(gr['x'], 1), 'y': round(gr['y'], 1), 'nodes': [n['id'] for n in gr['nodes']]}
                      for gr in g['groups']],
           'nodes': nodes, 'links': links}
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=1)
    print(f"{len(nodes)} nodes, {len(links)} links, {len(g['groups'])} groups, roots {g['roots']}")


if __name__ == '__main__':
    main(*sys.argv[1:5])
