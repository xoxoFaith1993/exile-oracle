"""Crafting engine for the Craft tab: item state, every crafting action, random outcomes, the next-step planner
and a Monte-Carlo simulator.

Item state (JSON, what the dashboard holds):
  {"base": "...", "ilvl": 82, "rarity": "normal|magic|rare", "corrupted": false,
   "mods": [{"fid": 12, "tier": 2, "side": "prefix", "text": "...", "kind": "normal|essence|desecrated",
             "fractured": false}]}
Targets: [{"fid": 12, "max_tier": 2}]  (fid = family index in the base's pool, tier 1 = best)

Every outcome assumes equal weights (the real ones aren't in the game files), so odds are optimistic."""

import random

from . import crafting

LIMIT = {'magic': 1, 'rare': 3}
EXALT = {'normal': 'Exalted Orb', 'greater': 'Greater Exalted Orb', 'perfect': 'Perfect Exalted Orb'}
CHAOS = {'normal': 'Chaos Orb', 'greater': 'Greater Chaos Orb', 'perfect': 'Perfect Chaos Orb'}
REGAL = {'normal': 'Regal Orb', 'greater': 'Greater Regal Orb', 'perfect': 'Perfect Regal Orb'}
TRANS = {'normal': 'Orb of Transmutation', 'greater': 'Greater Orb of Transmutation', 'perfect': 'Perfect Orb of Transmutation'}
AUG = {'normal': 'Orb of Augmentation', 'greater': 'Greater Orb of Augmentation', 'perfect': 'Perfect Orb of Augmentation'}
OMEN = {'exalt': {'prefix': 'Omen of Sinistral Exaltation', 'suffix': 'Omen of Dextral Exaltation'},
        'annul': {'prefix': 'Omen of Sinistral Annulment', 'suffix': 'Omen of Dextral Annulment'},
        'chaos': {'prefix': 'Omen of Sinistral Erasure', 'suffix': 'Omen of Dextral Erasure'},
        'regal': {'prefix': 'Omen of Sinistral Coronation', 'suffix': 'Omen of Dextral Coronation'}}
_pools = {}


# ---------------- pool ----------------

def get_pool(base, ilvl):
    key = (base, int(ilvl))
    if key not in _pools:
        p = crafting.pool(base, int(ilvl))
        fams = []
        for i, f in enumerate(p['families']):
            fams.append({'fid': i, 'side': f['side'], 'groups': f['groups'], 'template': f['template'],
                         'tiers': [{'tier': t['tier'], 'level': t['level'], 'text': t['text'], 'name': t['name']}
                                   for t in f['tiers']],
                         'available': [t['tier'] for t in f['available']]})
        _pools[key] = {'base': base, 'ilvl': int(ilvl), 'class': p['class'], 'families': fams}
    return _pools[key]


def pool_for_ui(base, ilvl):
    p = get_pool(base, ilvl)
    return {'base': base, 'ilvl': p['ilvl'], 'class': p['class'],
            'families': [{'fid': f['fid'], 'side': f['side'], 'template': f['template'],
                          'tiers': [t for t in f['tiers'] if t['tier'] in f['available']]} for f in p['families']]}


def _fam(pool, fid):
    return pool['families'][fid]


def _blocked_groups(state, pool):
    g = set()
    for m in state['mods']:
        if m.get('fid') is not None and m['fid'] < len(pool['families']):
            g.update(_fam(pool, m['fid'])['groups'])
    return g


def _open(state, side):
    cap = LIMIT.get(state['rarity'], 0)
    return cap - sum(1 for m in state['mods'] if m['side'] == side)


def eligible(state, pool, side, min_level=0):
    """[(family, [allowed tiers])] that could roll now on this side."""
    have = {m.get('fid') for m in state['mods']}
    blocked = _blocked_groups(state, pool)
    out = []
    for f in pool['families']:
        if f['side'] != side or f['fid'] in have or (set(f['groups']) & blocked):
            continue
        tiers = [t for t in f['tiers'] if t['tier'] in f['available']]
        ok = [t for t in tiers if t['level'] >= min_level] or tiers[:1]  # floor isn't absolute
        if ok:
            out.append((f, ok))
    return out


# ---------------- actions ----------------

def _roll(state, pool, sides, min_level, rng):
    sides = [s for s in sides if _open(state, s) > 0]
    cands = [(f, ok) for s in sides for f, ok in eligible(state, pool, s, min_level)]
    if not cands:
        return None
    f, ok = rng.choice(cands)
    t = rng.choice(ok)
    m = {'fid': f['fid'], 'tier': t['tier'], 'side': f['side'], 'text': t['text'], 'kind': 'normal', 'fractured': False}
    state['mods'].append(m)
    return m


def _remove(state, side, rng, lowest=False, pool=None):
    cands = [m for m in state['mods'] if not m.get('fractured') and (side is None or m['side'] == side)]
    if not cands:
        return None
    if lowest and pool:
        lv = lambda m: next((t['level'] for t in _fam(pool, m['fid'])['tiers'] if t['tier'] == m['tier']), 0) \
            if m.get('fid') is not None else 0
        low = min(lv(m) for m in cands)
        cands = [m for m in cands if lv(m) == low]
    m = rng.choice(cands)
    state['mods'].remove(m)
    return m


def apply(state, action, rng=None):
    """Apply one crafting action to a copy of state. Returns (new_state, what_happened, items_used)."""
    import copy
    rng = rng or random.Random()
    s = copy.deepcopy(state)
    pool = get_pool(s['base'], s['ilvl'])
    a = action['type']
    grade = action.get('grade', 'normal')
    side = action.get('side')  # omen side (prefix/suffix) or None
    used, msg = [], ''
    sides = [side] if side else ['prefix', 'suffix']
    if s.get('corrupted'):
        return s, 'The item is corrupted: it can\'t be changed any more.', used
    if a == 'transmute':
        if s['rarity'] != 'normal':
            return s, 'Transmutation needs a normal item.', used
        s['rarity'] = 'magic'
        m = _roll(s, pool, ['prefix', 'suffix'], crafting.MIN_LEVEL[TRANS[grade]], rng)
        used, msg = [TRANS[grade]], f'Magic with {m["text"] if m else "nothing"}'
    elif a == 'augment':
        if s['rarity'] != 'magic' or len(s['mods']) >= 2:
            return s, 'Augmentation needs a magic item with an open slot.', used
        m = _roll(s, pool, ['prefix', 'suffix'], crafting.MIN_LEVEL[AUG[grade]], rng)
        used, msg = [AUG[grade]], f'Added {m["text"] if m else "nothing"}'
    elif a == 'regal':
        if s['rarity'] != 'magic':
            return s, 'Regal needs a magic item.', used
        s['rarity'] = 'rare'
        m = _roll(s, pool, sides, crafting.MIN_LEVEL[REGAL[grade]], rng)
        used = [REGAL[grade]] + ([OMEN['regal'][side]] if side else [])
        msg = f'Rare, added {m["text"] if m else "nothing"}'
    elif a == 'alchemy':
        if s['rarity'] == 'rare':
            return s, 'Alchemy needs a normal or magic item.', used
        s['rarity'], s['mods'] = 'rare', []
        order = (['prefix'] * 3 + ['suffix']) if side == 'prefix' else (['suffix'] * 3 + ['prefix']) if side == 'suffix' \
            else [rng.choice(['prefix', 'suffix']) for _ in range(4)]
        for sd in order:
            _roll(s, pool, [sd] if _open(s, sd) > 0 else ['prefix', 'suffix'], 0, rng)
        used = ['Orb of Alchemy'] + ([f"Omen of {'Sinistral' if side == 'prefix' else 'Dextral'} Alchemy"] if side else [])
        msg = 'Rare with 4 mods'
    elif a == 'exalt':
        if s['rarity'] != 'rare' or len(s['mods']) >= 6:
            return s, 'Exalt needs a rare with an open slot.', used
        n = 2 if action.get('greater_exaltation') else 1
        added = [_roll(s, pool, sides, crafting.MIN_LEVEL[EXALT[grade]], rng) for _ in range(n)]
        used = [EXALT[grade]] + ([OMEN['exalt'][side]] if side else []) + (['Omen of Greater Exaltation'] if n == 2 else [])
        msg = 'Added ' + ', '.join(m['text'] for m in added if m) if any(added) else 'No room on that side'
    elif a == 'annul':
        n = 2 if action.get('greater_annulment') else 1
        gone = [_remove(s, side, rng) for _ in range(n)]
        used = ['Orb of Annulment'] + ([OMEN['annul'][side]] if side else []) + (['Omen of Greater Annulment'] if n == 2 else [])
        msg = 'Removed ' + ', '.join(m['text'] for m in gone if m) if any(gone) else 'Nothing removable'
    elif a == 'chaos':
        if s['rarity'] != 'rare':
            return s, 'Chaos needs a rare.', used
        gone = _remove(s, side, rng, lowest=action.get('whittling'), pool=pool)
        m = _roll(s, pool, ['prefix', 'suffix'], crafting.MIN_LEVEL[CHAOS[grade]], rng)
        used = [CHAOS[grade]] + ([OMEN['chaos'][side]] if side else []) + (['Omen of Whittling'] if action.get('whittling') else [])
        msg = f'Removed {gone["text"] if gone else "nothing"}, added {m["text"] if m else "nothing"}'
    elif a == 'essence':
        mod = action['mod']  # {"text", "side"} of the essence mod
        perfect = action.get('perfect')
        if not perfect and s['rarity'] != 'magic':
            return s, 'A normal essence needs a magic item.', used
        if perfect:
            if s['rarity'] != 'rare':
                return s, 'A Perfect essence needs a rare.', used
            _remove(s, side, rng)
        else:
            s['rarity'] = 'rare'
        s['mods'].append({'fid': None, 'tier': None, 'side': mod['side'], 'text': mod['text'], 'kind': 'essence',
                          'fractured': False})
        used = [action.get('name', 'Essence')] + ([f"Omen of {'Sinistral' if side == 'prefix' else 'Dextral'} "
                                                    'Crystallisation'] if perfect and side else [])
        msg = f'Added {mod["text"]}'
    elif a == 'fracture':
        cands = [m for m in s['mods'] if not m.get('fractured')]
        if len(s['mods']) < 4 or not cands:
            return s, 'Fracturing needs a rare with at least 4 mods.', used
        m = rng.choice(cands)
        m['fractured'] = True
        used, msg = ['Fracturing Orb'], f'Fractured {m["text"]}'
    elif a == 'divine':
        used, msg = ['Divine Orb'], 'Rerolled the values'
    elif a == 'set':  # record a real in-game result exactly (from the UI)
        return action['state'], 'Recorded your real result', []
    else:
        return s, f'Unknown action {a}', used
    return s, msg, used


# ---------------- planner ----------------

def _is_target(m, targets):
    for t in targets:
        if m.get('fid') is not None and m['fid'] == t.get('fid') and (m.get('tier') or 99) <= t.get('max_tier', 99):
            return True
        if t.get('text') and m.get('text') and t['text'].lower() == m['text'].lower():
            return True
    return False


def progress(state, targets):
    hit = [t for t in targets if any(_is_target(m, [t]) for m in state['mods'])]
    junk = [m for m in state['mods'] if not _is_target(m, targets)]
    return hit, junk


def _p_hit(state, pool, side, min_level, missing):
    el = eligible(state, pool, side, min_level)
    if not el:
        return 0.0
    p = 0.0
    for f, ok in el:
        for t in missing:
            if t.get('fid') == f['fid']:
                p += (1 / len(el)) * (sum(1 for x in ok if x['tier'] <= t.get('max_tier', 99)) / len(ok))
    return p


def plan(state, targets, prices):
    """Ranked options for the next step, with odds of progress and cost per try."""
    pool = get_pool(state['base'], state['ilvl'])
    hit, junk = progress(state, targets)
    missing = [t for t in targets if t not in hit and t.get('fid') is not None]
    side_of = lambda t: _fam(pool, t['fid'])['side']
    miss_side = {s: [t for t in missing if side_of(t) == s] for s in ('prefix', 'suffix')}
    cost = lambda items: round(sum(prices.get(i) or 0 for i in items), 4)
    opts = []
    if not missing and not any(t.get('kind') == 'essence' and t not in hit for t in targets):
        return {'done': True, 'hit': len(hit), 'of': len(targets),
                'options': [{'label': 'All targets hit! Divine Orbs to improve rolls, or stop here.',
                             'action': {'type': 'divine'}, 'p_progress': None, 'cost': cost(['Divine Orb'])}]}
    if state['rarity'] == 'normal':
        for g in ('normal', 'greater', 'perfect'):
            ml = crafting.MIN_LEVEL[TRANS[g]]
            p = (_p_hit(state, pool, 'prefix', ml, missing) * 0.5 + _p_hit(state, pool, 'suffix', ml, missing) * 0.5)
            opts.append({'label': f'{TRANS[g]}', 'action': {'type': 'transmute', 'grade': g}, 'p_progress': round(p, 4),
                         'cost': cost([TRANS[g]])})
    elif state['rarity'] == 'magic':
        if len(state['mods']) < 2:
            for g in ('normal', 'greater', 'perfect'):
                ml = crafting.MIN_LEVEL[AUG[g]]
                sides = [s for s in ('prefix', 'suffix') if _open(state, s) > 0]
                p = sum(_p_hit(state, pool, s, ml, missing) for s in sides) / max(1, len(sides))
                opts.append({'label': AUG[g], 'action': {'type': 'augment', 'grade': g}, 'p_progress': round(p, 4),
                             'cost': cost([AUG[g]])})
        best_side = max(('prefix', 'suffix'), key=lambda s: len(miss_side[s]))
        for g in ('normal', 'greater', 'perfect'):
            ml = crafting.MIN_LEVEL[REGAL[g]]
            p = _p_hit({**state, 'rarity': 'rare'}, pool, best_side, ml, missing)
            opts.append({'label': f"{REGAL[g]} + {OMEN['regal'][best_side]}", 'action': {'type': 'regal', 'grade': g,
                         'side': best_side}, 'p_progress': round(p, 4), 'cost': cost([REGAL[g], OMEN['regal'][best_side]])})
    else:  # rare
        for s in ('prefix', 'suffix'):
            if not miss_side[s]:
                continue
            if _open(state, s) > 0:
                for g in ('normal', 'greater', 'perfect'):
                    ml = crafting.MIN_LEVEL[EXALT[g]]
                    p = _p_hit(state, pool, s, ml, missing)
                    items = [EXALT[g], OMEN['exalt'][s]]
                    opts.append({'label': f'{EXALT[g]} + {OMEN["exalt"][s]}', 'action': {'type': 'exalt', 'grade': g,
                                 'side': s}, 'p_progress': round(p, 4), 'cost': cost(items),
                                 'expected_cost': round(cost(items) / p, 2) if p else None})
            else:
                bad = [m for m in junk if m['side'] == s and not m.get('fractured')]
                good = [m for m in state['mods'] if m['side'] == s and _is_target(m, targets) and not m.get('fractured')]
                if bad:
                    p_ok = len(bad) / (len(bad) + len(good))
                    items = ['Orb of Annulment', OMEN['annul'][s]]
                    opts.append({'label': f'Orb of Annulment + {OMEN["annul"][s]} (clear a {s} slot)',
                                 'action': {'type': 'annul', 'side': s}, 'p_progress': round(p_ok, 4),
                                 'cost': cost(items),
                                 'note': f'removes a random unfractured {s}: {len(good)} good one(s) at risk'})
                    # cheaper: a plain Annulment can hit any unfractured mod
                    allfree = [m for m in state['mods'] if not m.get('fractured')]
                    p_plain = len(bad) / len(allfree) if allfree else 0
                    if p_plain:
                        opts.append({'label': f'Orb of Annulment (no omen: removes any random mod)',
                                     'action': {'type': 'annul'}, 'p_progress': round(p_plain, 4),
                                     'cost': cost(['Orb of Annulment']),
                                     'note': f'{len(bad)} junk {s}(s) out of {len(allfree)} removable mods; '
                                             'may remove a good one'})
                    # or Chaos + Erasure omen: swap a random mod on this side for a new random mod
                    p_ch = (len(bad) / (len(bad) + len(good))) * max(_p_hit(dict(state, mods=[m for m in state['mods']
                            if m is not bad[0]]), pool, s, 0, missing), 0.0)
                    items = ['Chaos Orb', OMEN['chaos'][s]]
                    if p_ch:
                        opts.append({'label': f'Chaos Orb + {OMEN["chaos"][s]} (swap a {s})',
                                     'action': {'type': 'chaos', 'side': s}, 'p_progress': round(p_ch, 4),
                                     'cost': cost(items), 'note': 'progress = removes junk AND rolls a target'})
        good_unfrac = [m for m in state['mods'] if _is_target(m, targets) and not m.get('fractured')]
        if len(state['mods']) >= 4 and good_unfrac and not any(m.get('fractured') for m in state['mods']):
            p = len(good_unfrac) / len(state['mods'])
            opts.append({'label': 'Fracturing Orb (lock a mod)', 'action': {'type': 'fracture'}, 'p_progress': round(p, 4),
                         'cost': cost(['Fracturing Orb']), 'note': 'fractures a random mod: good if it picks a target'})
    for o in opts:
        if o.get('p_progress') and o.get('cost') and 'expected_cost' not in o:
            o['expected_cost'] = round(o['cost'] / o['p_progress'], 2)
    opts.sort(key=lambda o: (o.get('expected_cost') is None, o.get('expected_cost') or 1e9))
    if opts:
        opts[0]['recommended'] = True
    return {'done': False, 'hit': len(hit), 'of': len(targets), 'missing': len(missing), 'junk': len(junk),
            'options': opts}


# ---------------- simulator ----------------

def simulate(state, targets, prices, runs=300, max_steps=120, base_cost=0.0, seed=1):
    """Follow the planner's top choice until every target is hit (or the step cap). Equal weights."""
    rng = random.Random(seed)
    results = []
    for _ in range(runs):
        s = dict(state, mods=[dict(m) for m in state['mods']])
        spent, steps = base_cost, 0
        while steps < max_steps:
            pl = plan(s, targets, prices)
            if pl['done']:
                break
            if not pl['options']:
                # stuck (e.g. side full of fractured junk): start over on a fresh base
                s = {'base': state['base'], 'ilvl': state['ilvl'], 'rarity': 'normal', 'mods': [], 'corrupted': False}
                spent += base_cost
                steps += 1
                continue
            act = pl['options'][0]['action']
            s, _msg, used = apply(s, act, rng)
            spent += sum(prices.get(i) or 0 for i in used)
            steps += 1
        results.append({'ok': plan(s, targets, prices)['done'], 'cost': spent, 'steps': steps})
    ok = [r for r in results if r['ok']]
    costs = sorted(r['cost'] for r in ok)
    pick = lambda q: round(costs[min(len(costs) - 1, int(q * len(costs)))], 2) if costs else None
    return {'runs': runs, 'success_rate': round(len(ok) / runs, 3), 'median_cost_div': pick(0.5),
            'p90_cost_div': pick(0.9), 'avg_steps': round(sum(r['steps'] for r in ok) / len(ok), 1) if ok else None,
            'note': f'Equal-weights model, following the planner, up to {max_steps} steps per run.'}


# ---------------- bridges for the Craft tab ----------------

def import_item(base, ilvl, mod_lines):
    """Turn real mod lines into engine mods (family + tier where possible)."""
    from . import gamedata
    pool = get_pool(base, ilvl)
    tags = (gamedata.base_info(base) or {}).get('tags', set())
    out = []
    for line in mod_lines:
        r = gamedata.read_mod(line, tags) or {}
        fid = None
        if r.get('mod'):
            for f in pool['families']:
                if f['side'] == r.get('gen') and any(t['name'] == r['mod'] and t['tier'] == r.get('tier')
                                                     for t in f['tiers']):
                    fid = f['fid']
                    break
        out.append({'fid': fid, 'tier': r.get('tier'), 'side': r.get('gen') or 'prefix', 'text': line,
                    'kind': 'normal' if fid is not None else 'other', 'fractured': False})
    return out


def bases():
    """Craftable equipment bases for the base picker."""
    from . import gamedata
    keep = ('Ring', 'Amulet', 'Belt', 'Helmet', 'Body Armour', 'Gloves', 'Boots', 'Shield', 'Focus', 'Quiver',
            'Wand', 'Staff', 'Sceptre', 'Bow', 'Crossbow', 'Quarterstaff', 'One Hand Mace', 'Two Hand Mace',
            'Spear', 'Flail', 'Dagger', 'Claw', 'One Hand Sword', 'Two Hand Sword', 'One Hand Axe', 'Two Hand Axe',
            'Jewel', 'Charm', 'Talisman', 'Trap', 'Buckler')
    out = []
    for k, v in gamedata.load('base_items').items():
        if v.get('release_state') == 'released' and v.get('item_class') in keep and v.get('name') \
                and 'Unique' not in k:
            out.append({'name': v['name'], 'class': v['item_class'], 'level': v.get('drop_level')})
    seen, res = set(), []
    for b in sorted(out, key=lambda b: (b['class'], -(b['level'] or 0))):
        if b['name'] not in seen:
            seen.add(b['name'])
            res.append(b)
    return res
