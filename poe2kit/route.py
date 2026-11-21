"""Automatic levelling route for any build (no Claude needed): the order to take an endgame tree's passives in, the
level each one comes at, when each gem can be cut, and quest reminders. buildplanner uses it for builds that don't
already have levelling trees ("Level 30", "Level 60", ...); Claude can then refine the result.

  order(nodes, version)   -> class passives in a sensible order + ascendancy passives grouped by trial
  levels(n_passives)      -> the level each passive in that order becomes affordable
  gem_level(gem_id)       -> the character level at which the gem can be cut and used (from PoB's gem data)
  quest_reminders()       -> the weapon-set passive point quests by act

Rules of thumb (stated so they can be checked):
  - passive points: 1 per level after the first, plus 2 per point-giving quest (12 quests, 24 points; PoE 2 calls
    them weapon-set points) once the character reaches that quest's area level;
  - goals are valued keystone 6, notable 4, jewel socket 2, small 1, attribute 0.6; each step takes the goal with the
    best value per point spent on the way, so the build's big nodes come as early as the path allows;
  - ascendancy points come 2 per trial; trial levels are typical campaign levels (about 22, 38, 55, 70)."""

import os
import re
from collections import deque

from . import config

VALUE = {'keystone': 6, 'notable': 4, 'jewel': 2, 'small': 1, 'attribute': 0.6}
LOOKAHEAD = 10   # in game, a planned passive appears this many levels before it's due
TRIAL_LEVELS = [22, 38, 55, 70]          # 1st..4th ascendancy trial, typical campaign / early-map levels
SUPPORT_TIER_LEVEL = {1: 1, 2: 14, 3: 28, 4: 44, 5: 60}   # uncut support gem tiers: rough first-drop levels
_cache = {}


# ---------------- tree ----------------

def _tree(version):
    if version in _cache:
        return _cache[version]
    from . import character
    t = character.tree(version)
    nodes = {n['id']: n for n in t['nodes']}
    adj = {}
    for e in t['edges']:
        adj.setdefault(e[0], set()).add(e[1])
        adj.setdefault(e[1], set()).add(e[0])
    starts = {}
    try:   # class start nodes are only marked in PoB's tree.lua (classesStart = {"Witch", "Sorceress"})
        text = open(os.path.join(config.POB_DIR, 'src', 'TreeData', version, 'tree.lua'), encoding='utf-8').read()
        for m in re.finditer(r'\n\t\t\[(\d+)\]=\{(?:(?!\n\t\t\[).){0,1500}?classesStart=\{([^}]*)\}', text, re.S):
            for cls in re.findall(r'"([^"]+)"', m.group(2)):
                starts[cls] = int(m.group(1))
    except OSError:
        pass
    _cache[version] = (nodes, adj, starts)
    return _cache[version]


def _start(have, nodes, adj, starts, class_name=None):
    if class_name and class_name in starts:
        return starts[class_name]
    best = max(starts.values(), key=lambda s: len(adj.get(s, set()) & have), default=None)
    return best


def order(have, version='0_5', class_name=None):
    """have: the endgame tree's node numbers. Returns (class_order, ascendancy_order, start_node)."""
    nodes, adj, starts = _tree(version)
    have = set(have)
    asc = {n for n in have if (nodes.get(n) or {}).get('a')}
    main = have - asc
    start = _start(main, nodes, adj, starts, class_name)
    taken, out = {start} if start else set(), []
    left = set(main) - taken
    if not taken:   # no start found: fall back to the PoB order
        return sorted(main), _asc_order(asc, nodes, adj), None
    while left:
        # shortest paths from what's taken, only through planned nodes
        prev, dist = {}, {}
        q = deque()
        for t in taken:
            for nb in adj.get(t, ()):
                if nb in left and nb not in dist:
                    dist[nb], prev[nb] = 1, None
                    q.append(nb)
        while q:
            cur = q.popleft()
            for nb in adj.get(cur, ()):
                if nb in left and nb not in dist:
                    dist[nb], prev[nb] = dist[cur] + 1, cur
                    q.append(nb)
        if not dist:   # the rest isn't connected to what's taken (odd tree): append as is
            out += sorted(left)
            break
        best, best_score = None, -1
        for goal, d in dist.items():
            path, cur = [], goal
            while cur is not None:
                path.append(cur)
                cur = prev[cur]
            score = sum(VALUE.get((nodes.get(p) or {}).get('k'), 1) for p in path) / len(path)
            score += VALUE.get((nodes.get(goal) or {}).get('k'), 1) / len(path)   # the goal itself counts double
            if score > best_score:
                best, best_score = path[::-1], score
        for p in best:
            out.append(p)
            taken.add(p)
            left.discard(p)
    return out, _asc_order(asc, nodes, adj), start


def _asc_order(asc, nodes, adj):
    """Ascendancy nodes from the ascendancy's start outwards, notables as early as their path allows."""
    if not asc:
        return []
    start = next((n for n in asc if (nodes.get(n) or {}).get('k') == 'start'), None)
    if start is None:
        return sorted(asc)
    taken, out, left = {start}, [], set(asc) - {start}
    while left:
        frontier = [n for n in left if adj.get(n, set()) & taken]
        if not frontier:
            out += sorted(left)
            break
        pick = max(frontier, key=lambda n: VALUE.get((nodes.get(n) or {}).get('k'), 1))
        out.append(pick)
        taken.add(pick)
        left.discard(pick)
    return out


# ---------------- levels ----------------

def points_at(level):
    """Passive points by this level: 1 per level after the first, plus the quest points (2 each, 12 quests = 24; PoE 2
    labels them weapon-set points) for quests whose area level is at or below this level."""
    return (level - 1) + sum(int(q.get('points') or 0) for q in quest_reminders() if (q.get('level') or 999) <= level)


def levels(n):
    """Level at which the i-th passive (1-based) in the order becomes affordable."""
    out, lvl = [], 1
    for i in range(1, n + 1):
        while lvl < 100 and points_at(lvl) < i:
            lvl += 1
        out.append(lvl)
    return out


def asc_levels(n):
    """2 ascendancy points per trial."""
    return [TRIAL_LEVELS[min(len(TRIAL_LEVELS) - 1, i // 2)] for i in range(n)]


# ---------------- gems ----------------

_gems = {}


def _gem_data():
    if _gems:
        return _gems
    src = os.path.join(config.POB_DIR, 'src', 'Data')
    try:
        text = open(os.path.join(src, 'Gems.lua'), encoding='utf-8').read()
    except OSError:
        return _gems
    req = {}
    for f in ('act_int.lua', 'act_str.lua', 'act_dex.lua', 'sup_int.lua', 'sup_str.lua', 'sup_dex.lua', 'other.lua',
              'minion.lua', 'spectre.lua'):
        try:
            sk = open(os.path.join(src, 'Skills', f), encoding='utf-8').read()
        except OSError:
            continue
        for m in re.finditer(r'\nskills\["([^"]+)"\] = \{(.*?)\n\}', sk, re.S):
            lv = re.findall(r'levelRequirement = (\d+)', m.group(2))
            if lv:
                req[m.group(1)] = [int(x) for x in lv]
    for block in text.split('\n\t["')[1:]:
        gid = re.search(r'gameId = "([^"]+)"', block)   # builds store the game's id; PoB files gems under its own
        if not gid:
            continue
        tier = re.search(r'\n\t\tTier = (\d+)', block)
        eff = re.search(r'grantedEffectId = "([^"]+)"', block)
        _gems.setdefault(gid.group(1), {'tier': int(tier.group(1)) if tier else 0,
                                        'req': req.get(eff.group(1) if eff else '', [])})
    return _gems


def gem_level(gem_id):
    """Character level at which this gem can first be cut and used, or None (granted / unique / unknown).
    Skill gems: tier T needs an uncut gem of level T, and gem level T has its own level requirement.
    Support gems: tiers 1-5 by when uncut support gems of that tier start dropping (approximate)."""
    g = _gem_data().get(gem_id)
    if not g or not g['tier']:
        return None
    if 'SupportGem' in gem_id:
        return SUPPORT_TIER_LEVEL.get(g['tier'])
    req = g['req']
    if len(req) >= g['tier']:
        return max(1, req[g['tier'] - 1])
    return None


# ---------------- quests ----------------

def quest_reminders():
    import json
    p = config.data_file('quest_rewards.json')
    if not p:
        return []
    out = []
    for q in json.load(open(p, encoding='utf-8')):
        st = q.get('Stat') or ''
        if q.get('questPoints') or 'Passive Skill Point' in st:
            out.append({'act': q.get('Act'), 'area': q.get('Area'), 'level': q.get('AreaLevel'), 'who': q.get('Info'),
                        'reward': st, 'points': q.get('questPoints') or 0})
    return out


# ---------------- weapon-set points ----------------

OFFENCE = ('damage', 'critical', 'cast speed', 'attack speed', 'penetrat', 'spell', 'projectile', 'area of effect',
           'skill effect duration', 'lightning', 'fire', 'cold', 'chaos', 'minion')
DEFENCE = ('life', 'mana', 'energy shield', 'resist', 'armour', 'evasion', 'block', 'attribute', 'strength',
           'dexterity', 'intelligence', 'stun', 'recovery', 'regenerat', 'movement speed', 'spirit')


def _offensive(node):
    text = ' '.join((node or {}).get('s') or []).lower()
    if not text or any(w in text for w in DEFENCE):
        return False
    return any(w in text for w in OFFENCE)


def weapon_set_nodes(order_list, level_list, version='0_5'):
    """Which planned passives to buy with the quest points (PoE 2 gives them as Weapon Set points: a passive bought
    with one only works while that weapon set is in use). Damage nodes go on Weapon Set I, so the always-on defence
    (life, resistances, attributes) stays on normal points. Each quest's 2 points go to the first damage nodes due
    at or after that quest's level. Returns {node: quest label}."""
    nodes, _, _ = _tree(version)
    out, used = {}, set()
    for q in sorted(quest_reminders(), key=lambda q: q.get('level') or 0):
        for _ in range(int(q.get('points') or 0)):
            pick = next((n for n, lv in zip(order_list, level_list)
                         if n not in used and lv >= (q.get('level') or 0) and _offensive(nodes.get(n))), None)
            if pick is None:
                break
            used.add(pick)
            out[pick] = f"Act {q['act']} {q['area']}"
    return out
