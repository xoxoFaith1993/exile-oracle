"""Atlas war room, the rest of R15: strategy guides, the planner (a strategy's setup drawn on the atlas tree),
waystone rolling with live costs, tablets, the map-juicing ROI simulator and strategy switches by league phase.

Data: datapack/atlas-strategies.json (our research, research/atlas: 11 strategies with their key nodes, tablets,
waystone setups, rolling methods, deadly mod combos) + datapack/farming.json (div / hour by phase) + the live atlas
tree (poe2kit.atlas) + live currency prices. All original; no other tool's data.
"""

import collections
import json
import re

from . import config

_cache = {}
# what each rolling method spends, per waystone (names as on the Currency Exchange)
ROLL_COST = {
    'White (normal) waystone': {},
    'Magic (Transmute + Augment)': {'Orb of Transmutation': 1, 'Orb of Augmentation': 1},
    'Rare: Alchemy (4 mods) + Exalted to 6': {'Orb of Alchemy': 1, 'Exalted Orb': 2},
    'Chaos Orb (swap one random mod)': {'Chaos Orb': 1},
    'Vaal Orb (corrupt)': {'Vaal Orb': 1},
}
# average reward per method at T16 (research/atlas, computed from the game's mod data with equal weights)
ROLL_REWARD = {
    'White (normal) waystone': {'waystones': 0, 'pack': 0, 'rarity': 0},
    'Magic (Transmute + Augment)': {'waystones': 30, 'pack': 5, 'rarity': 9},
    'Rare: Alchemy (4 mods) + Exalted to 6': {'waystones': 89, 'pack': 15, 'rarity': 28},
}


def _load(name):
    if name not in _cache:
        p = config.data_file(name)
        if not p:
            raise FileNotFoundError(f'{name} is missing from the data pack')
        _cache[name] = json.load(open(p, encoding='utf-8'))
    return _cache[name]


def data():
    return _load('atlas-strategies.json')


def _tree():
    if 'tree' not in _cache:
        from . import atlas
        _cache['tree'] = atlas.tree_for_viewer()
    return _cache['tree']


def _key(s):
    return re.sub(r'[^a-z]', '', (s or '').lower())


def _graph():
    if 'graph' not in _cache:
        t = _tree()
        adj = collections.defaultdict(set)
        for e in t['edges']:
            adj[e[0]].add(e[1])
            adj[e[1]].add(e[0])
        byname = collections.defaultdict(list)
        for n in t['nodes']:
            byname[_key(n.get('n'))].append(n['id'])
        _cache['graph'] = (adj, byname, {n['id']: n for n in t['nodes']})
    return _cache['graph']


def _bfs_path(adj, sources, target):
    """Shortest path from any node in `sources` to target (list of node ids, sources excluded)."""
    prev = {s: None for s in sources}
    q = collections.deque(sources)
    while q:
        v = q.popleft()
        if v == target:
            path = []
            while prev[v] is not None:
                path.append(v)
                v = prev[v]
            return path[::-1]
        for w in adj[v]:
            if w not in prev:
                prev[w] = v
                q.append(w)
    return None


def setup(name):
    """A strategy's atlas setup: its key nodes, plus the shortest connecting paths from the tree's start points
    (a greedy Steiner tree: always add the key node that is cheapest to reach next). Points = nodes taken."""
    st = next((s for s in data()['strategies'] if _key(s['name']) == _key(name) or _key(name) in _key(s['name'])), None)
    if not st:
        return {'error': f'no strategy called {name}'}
    adj, byname, nodes = _graph()
    roots = set(_tree().get('roots') or [])
    keys, missing = [], []
    for k in st.get('key_nodes') or []:
        ids = byname.get(_key(k['name'])) or []
        (keys.append(ids[0]) if ids else missing.append(k['name']))
    have = set(roots)
    left = [k for k in keys if k not in have]
    while left:
        best = None
        for k in left:
            p = _bfs_path(adj, have, k)
            if p is not None and (best is None or len(p) < len(best[1])):
                best = (k, p)
        if not best:
            missing += [nodes[k].get('n') for k in left]
            break
        have.update(best[1])
        left.remove(best[0])
    taken = sorted(have - roots)
    return {'strategy': st['name'], 'allocated': sorted(have), 'key': keys, 'points': len(taken),
            'key_nodes': [dict(k, id=(byname.get(_key(k['name'])) or [None])[0]) for k in st.get('key_nodes') or []],
            'missing': missing}


def _phase_key(day):
    from . import prophecy
    return prophecy.farm_phase(day)


def strategies(con=None, day=None):
    """Every strategy with its guide, its setup size, and div / hour now and next phase (farming research)."""
    from . import prophecy
    if day is None and con is not None:
        _, day, _ = prophecy.league_day(con)
    farm = _load('farming.json')
    ph = _phase_key(day)
    keys = [k for k, a, b in prophecy.FARM_PHASES]
    nxt = keys[keys.index(ph) + 1] if ph in keys and keys.index(ph) + 1 < len(keys) else None
    out = []
    for s in data()['strategies']:
        word = _key(s['name'].split('(')[0].split('/')[0])
        mech = [_key(m) for m in s.get('mechanics') or []]
        runs = [f for f in farm['strategies'] if word and (word in _key(f.get('mechanic')) or word in _key(f['name']))]
        if not runs and 'juiced' in word:
            runs = [f for f in farm['strategies'] if (f.get('mechanic') or '') == 'Base mapping']

        def best(k):
            rows = [(f, (f.get('div_per_hour') or {}).get(k)) for f in runs]
            rows = [(f, r) for f, r in rows if r]
            if not rows:
                return None
            f, r = max(rows, key=lambda x: x[1].get('mid') or 0)
            return {'name': f['name'], 'low': r.get('low'), 'mid': r.get('mid'), 'high': r.get('high'),
                    'dps_min': (f.get('requirements') or {}).get('dps_min'), 'ehp_min': (f.get('requirements') or {}).get('ehp_min')}
        try:
            size = setup(s['name']).get('points')
        except Exception:
            size = None
        out.append({'name': s['name'], 'mechanics': s.get('mechanics'), 'key_nodes': s.get('key_nodes'),
                    'tablets': s.get('tablets'), 'waystones': s.get('waystone_setup'), 'confidence': s.get('confidence'),
                    'version': s.get('version'), 'points': size, 'now': best(ph), 'next': best(nxt) if nxt else None,
                    'pairing': (data().get('tablets') or {}).get('pairing', {}).get(s['name'].split(' ')[0])})
    out.sort(key=lambda s: -((s['now'] or {}).get('mid') or 0))
    if out and out[0]['now']:
        top_next = max(out, key=lambda s: (s['next'] or {}).get('mid') or 0)
        switch = None
        if nxt and top_next is not out[0] and (top_next['next'] or {}).get('mid'):
            switch = f"Now {out[0]['name']} pays most; next phase ({farm['phases'].get(nxt)}) switch to {top_next['name']}."
    else:
        switch = None
    return {'day': round(day, 1) if day is not None else None, 'phase': farm['phases'].get(ph),
            'next_phase': farm['phases'].get(nxt) if nxt else None, 'strategies': out, 'switch': switch,
            'deadly': data().get('deadly_for_most_builds'), 'facts': data().get('waystone_facts')}


def _price(con, league, name):
    from . import oracle
    try:
        p, _ = oracle._live(con, league, name)
        return p
    except Exception:
        return None


def rolling(con):
    """Each way to roll a waystone, what it costs at live prices, what it gives, and when to use it."""
    from . import ninja, money
    league = ninja.current_league(con)
    ex = (money.rates(con, league) or {}).get('ex_per_div')
    out = []
    for r in data().get('rolling') or []:
        cost = ROLL_COST.get(r['method'])
        div = None
        parts = []
        if cost is not None:
            div = 0.0
            for name, n in cost.items():
                p = _price(con, league, name)
                if p is None:
                    div = None
                    break
                div += p * n
                parts.append(f'{n} {name}')
        out.append({'method': r['method'], 'cost_div': round(div, 4) if div is not None else None,
                    'cost_ex': round(div * ex, 2) if div is not None and ex else None, 'spends': parts,
                    'cost_note': r.get('cost_note'), 'reward': r.get('expected_reward'), 'when': r.get('when'),
                    'reward_pct': ROLL_REWARD.get(r['method']), 'confidence': r.get('confidence')})
    return {'league': league, 'ex_per_div': ex, 'methods': out,
            'search': {k: v for k, v in (data().get('search_box') or {}).items() if k in ('max_len', 'syntax')}}


def tablets():
    t = data().get('tablets') or {}
    return {'types': [{'name': x['name'], 'implicit': x.get('implicit'),
                       'mods': [{'affix': m.get('affix_name'), 'text': m.get('text'), 'kind': m.get('kind')}
                                for m in (x.get('own_suffixes') or []) + (x.get('own_prefixes') or [])]}
                      for x in t.get('types') or []],
            'rules': t.get('rules'), 'pairing': t.get('pairing'), 'value_note': t.get('value_note')}


def roi(con, strategy=None, method='Rare: Alchemy (4 mods) + Exalted to 6', tablets_per_map=0, tablet_cost_div=0.0,
        extra_div=0.0, maps_per_hour=None, day=None):
    """Map-juicing ROI: what one map costs to set up vs what the strategy returns per map at this point of the league."""
    s = strategies(con, day)
    st = next((x for x in s['strategies'] if strategy and _key(strategy) in _key(x['name'])), None) or s['strategies'][0]
    r = next((m for m in rolling(con)['methods'] if m['method'] == method), None)
    roll = (r or {}).get('cost_div') or 0.0
    farm = _load('farming.json')
    run = next((f for f in farm['strategies'] if st['now'] and f['name'] == st['now']['name']), None)
    mph = maps_per_hour or ((run or {}).get('pace') or {}).get('maps_per_hour') or 10
    per_hour = (st['now'] or {}).get('mid')
    cost_map = roll + float(tablets_per_map) * float(tablet_cost_div) / 10.0 + float(extra_div)   # tablets: 10 uses
    if per_hour is None:
        return {'strategy': st['name'], 'error': 'no div / hour data for this strategy at this point of the league',
                'cost_per_map_div': round(cost_map, 4)}
    gross_map = per_hour / mph
    return {'strategy': st['name'], 'run': st['now']['name'], 'phase': s['phase'], 'maps_per_hour': mph,
            'method': method, 'roll_cost_div': round(roll, 4), 'cost_per_map_div': round(cost_map, 4),
            'return_per_map_div': round(gross_map, 3), 'profit_per_map_div': round(gross_map - cost_map, 3),
            'profit_per_hour_div': round((gross_map - cost_map) * mph, 2),
            'range_per_hour_div': [st['now']['low'], st['now']['high']],
            'break_even': round(cost_map / gross_map, 2) if gross_map else None,
            'note': 'The div / hour already assumes the usual juice for that strategy; extra costs you add here come '
                    'off it. Creators are fast: most players land in the lower half of the range.'}
