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


def my_pace(con, min_maps=10):
    """The player's own maps per hour from the game log (Sessions): all maps over all session time, so trading and
    hideout time count too. None until there are at least `min_maps` map runs."""
    try:
        from . import clientlog
        ss = clientlog.sessions(con, 60)['sessions']
    except Exception:
        return None
    maps = sum(s.get('maps_run') or 0 for s in ss if (s.get('maps_run') or 0) >= 3)
    hours = sum((s.get('minutes') or 0) / 60 for s in ss if (s.get('maps_run') or 0) >= 3)
    if maps < min_maps or hours <= 0:
        return None
    avg = [s['avg_map_min'] for s in ss if s.get('avg_map_min')]
    return {'maps_per_hour': round(maps / hours, 1), 'maps': maps, 'hours': round(hours, 1),
            'avg_map_min': round(sum(avg) / len(avg), 1) if avg else None}


def roi(con, strategy=None, maps_per_hour=None, extra_div=0.0, day=None, **_old):
    """What a strategy earns per hour at this point of the league, honestly:
    - the farming research's numbers are NET: the usual waystones, tablets and other inputs are already taken off;
    - they come from one recorded creator session per strategy (drop counts = community claim), valued at GGG's
      exchange prices over past leagues, then scaled for normal players: low = 45% of the worst league, mid = 70% of
      the median league, high = 100% of the best league (research/farming);
    - per hour is rescaled to YOUR maps per hour (game log) when known, else the creator's pace;
    - extra_div = what you spend per map beyond the usual setup (it comes off)."""
    s = strategies(con, day)
    st = next((x for x in s['strategies'] if strategy and _key(strategy) in _key(x['name'])), None) or s['strategies'][0]
    if not st['now']:
        return {'strategy': st['name'], 'error': 'No earnings data for this strategy at this point of the league.'}
    farm = _load('farming.json')
    run = next((f for f in farm['strategies'] if f['name'] == st['now']['name']), {})
    creator = float(((run.get('pace') or {}).get('maps_per_hour')) or 10)
    mine = my_pace(con)
    if maps_per_hour:
        mph, pace_src = float(maps_per_hour), 'the pace you typed'
    elif mine:
        mph, pace_src = mine['maps_per_hour'], f"your pace from the game log ({mine['maps']} maps over {mine['hours']} h)"
    else:
        mph, pace_src = creator, "the creator's pace (run about 10 maps and it uses yours)"
    k = mph / creator
    extra = float(extra_div or 0) * mph
    per = {q: (st['now'][q] or 0) * k - extra for q in ('low', 'mid', 'high')}
    src = run.get('source_session') or {}
    return {
        'strategy': st['name'], 'run': run.get('name'), 'phase': s['phase'],
        'per_hour': {q: round(v, 1) for q, v in per.items()},
        'per_map': {q: round((st['now'][q] or 0) / creator - float(extra_div or 0), 3) for q in ('low', 'mid', 'high')},
        'maps_per_hour': round(mph, 1), 'pace_source': pace_src, 'creator_pace': creator, 'my_pace': mine,
        'extra_div': float(extra_div or 0),
        'basis': {'what': run.get('number_label'), 'sample': src.get('sample'), 'patch': src.get('patch'),
                  'leagues': run.get('leagues_used'), 'confidence': run.get('confidence'),
                  'scaling': 'low = 45% of the worst past league, mid = 70% of the typical one, high = 100% of the best'},
        'net_note': 'Already net: the usual waystones, tablets and other inputs for this strategy are taken off.',
        'honesty': 'From one recorded session per strategy, valued at real exchange prices from past leagues. A rough '
                   'guide, not a promise; 1.0 prices and patches will move it. Your real profit comes with the '
                   'currency tab reader.'}
