"""The atlas passive tree, read from the game's own files (original code; no third-party data).

- Layout: Metadata/AtlasSkillGraphs/AtlasSkillGraph.psg (extracted with the game-file extractor into
  HOME/gamefiles/<build>/raw/). Format (v3, little-endian), worked out from the file:
    u8 version, u8 type, u8 orbit_count, orbit_count x u8 nodes-per-orbit,
    u32 root_count, root_count x (u32 node, u32 flag),
    u32 group_count, per group: f32 x, f32 y, u32 flags, u32 unknown, u8 unknown, u32 node_count,
      per node: u32 node_id (PassiveSkillGraphId), u32 orbit, u32 orbit_index, u32 link_count,
        per link: u32 node_id, i32 curvature.
- Names, icons and flags: tables/passiveskills.json (rows whose PassiveSkillGraphId match the nodes).
"""

import glob
import json
import math
import os
import struct

from . import config

ORBIT_RADII = [0, 82, 162, 335, 493, 662, 846, 251, 1080, 1322]   # PoE 2's passive-tree orbit radii (same family)
_cache = {}


def _gamefiles():
    builds = sorted(glob.glob(os.path.join(config.GAMEFILES_DIR, '*', 'tables', 'passiveskills.json')),
                    key=os.path.getmtime)
    return os.path.dirname(os.path.dirname(builds[-1])) if builds else None


def parse_psg(path):
    b = open(path, 'rb').read()
    o = 0

    def u8():
        nonlocal o
        v = b[o]
        o += 1
        return v

    def u32():
        nonlocal o
        v = struct.unpack_from('<I', b, o)[0]
        o += 4
        return v

    def i32():
        nonlocal o
        v = struct.unpack_from('<i', b, o)[0]
        o += 4
        return v

    def f32():
        nonlocal o
        v = struct.unpack_from('<f', b, o)[0]
        o += 4
        return v

    version, gtype, n_orbits = u8(), u8(), u8()
    per_orbit = [u8() for _ in range(n_orbits)]
    roots = [(u32(), u32()) for _ in range(u32())]
    groups = []
    for _ in range(u32()):
        g = {'x': f32(), 'y': f32(), 'flags': u32(), 'unk': u32(), 'unk2': u8(), 'nodes': []}
        for _ in range(u32()):
            n = {'id': u32(), 'orbit': u32(), 'index': u32(), 'links': []}
            for _ in range(u32()):
                n['links'].append((u32(), i32()))
            g['nodes'].append(n)
        groups.append(g)
    return {'version': version, 'type': gtype, 'per_orbit': per_orbit, 'roots': roots, 'groups': groups,
            'bytes_left': len(b) - o}


def tree():
    """{'nodes': [{id, x, y, name, icon, kind, group}], 'links': [[a, b]], 'roots': [...]} for drawing."""
    if 'tree' in _cache:
        return _cache['tree']
    gf = _gamefiles()
    psg = os.path.join(gf, 'raw', 'metadata', 'atlasskillgraphs', 'atlasskillgraph.psg') if gf else None
    if not psg or not os.path.exists(psg):   # no game files here (friends' installs): the shipped copy
        p = config.data_file('atlas_tree.json')
        if not p:
            raise FileNotFoundError('the atlas tree is not available: no game files and no data-pack copy')
        _cache['tree'] = json.load(open(p, encoding='utf-8'))
        return _cache['tree']
    g = parse_psg(psg)
    rows = json.load(open(os.path.join(gf, 'tables', 'passiveskills.json'), encoding='utf-8'))
    stat_ids = [r.get('Id') for r in json.load(open(os.path.join(gf, 'tables', 'stats.json'), encoding='utf-8'))]
    sd = os.path.join(gf, 'raw', 'data', 'statdescriptions')
    csd = [os.path.join(sd, f) for f in ('atlas_stat_descriptions.csd', 'endgame_map_stat_descriptions.csd',
                                          'passive_skill_stat_descriptions.csd', 'stat_descriptions.csd')]
    from . import statdesc
    by_graph = {}
    for r in rows:
        gid = r.get('PassiveSkillGraphId')
        if gid is not None:
            by_graph.setdefault(gid, r)
    nodes, links, seen = [], set(), {}
    for gi, grp in enumerate(g['groups']):
        for n in grp['nodes']:
            per = g['per_orbit'][n['orbit']] if n['orbit'] < len(g['per_orbit']) else 1
            rad = ORBIT_RADII[n['orbit']] if n['orbit'] < len(ORBIT_RADII) else 0
            ang = 2 * math.pi * n['index'] / max(1, per) - math.pi / 2
            r = by_graph.get(n['id']) or {}
            kind = 'keystone' if r.get('IsKeystone') else 'notable' if r.get('IsNotable') else \
                'jewel' if r.get('IsJewelSocket') else 'small'
            stats = {stat_ids[i]: r.get(f'Stat{k + 1}Value', 0) for k, i in enumerate(r.get('Stats') or [])
                     if isinstance(i, int) and i < len(stat_ids)}
            node = {'stats': statdesc.describe(stats, csd) if stats else [],
                    'id': n['id'], 'x': round(grp['x'] + rad * math.cos(ang), 1),
                    'y': round(grp['y'] + rad * math.sin(ang), 1), 'name': r.get('Name') or '',
                    'icon': (r.get('Icon_DDSFile') or '').lower(), 'kind': kind, 'group': gi,
                    'row': r.get('Id')}
            seen[n['id']] = node
            nodes.append(node)
            for other, _curve in n['links']:
                links.add(tuple(sorted((n['id'], other))))
    out = {'nodes': nodes, 'links': [list(l) for l in links if l[0] in seen and l[1] in seen],
           'roots': [r[0] for r in g['roots']], 'named': sum(1 for n in nodes if n['name']),
           'build': os.path.basename(gf)}
    _cache['tree'] = out
    return out


def tree_for_viewer():
    """The atlas in the dashboard tree viewer's format (same as character.tree): nodes {id, x, y, k, n, s, a, i}."""
    from . import art
    t = tree()
    nodes = []
    for n in t['nodes']:
        icon = n['icon'].replace('.dds', '.png') if n['icon'] else ''
        if icon and not icon.startswith('art/'):
            icon = 'art/' + icon
        nodes.append({'id': n['id'], 'x': n['x'], 'y': n['y'], 'k': n['kind'], 'n': n['name'] or '',
                      's': n.get('stats') or [], 'a': None, 'i': icon if icon and art.file_for(icon) else None})
    return {'version': 'atlas', 'nodes': nodes, 'edges': t['links'], 'classes': [], 'roots': t['roots'],
            'build': t['build']}


def export_datapack(path):
    """Write the parsed atlas tree for the data pack (make_datapack.py), so installs without game files have it."""
    t = tree()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(t, f, separators=(',', ':'))
    return len(t['nodes'])
