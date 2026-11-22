"""Crafting engine for the Craft tab: item state, every crafting action, random outcomes, the next-step planner
and a Monte-Carlo simulator.

Item state (JSON, what the dashboard holds):
  {"base": "...", "ilvl": 82, "rarity": "normal|magic|rare", "corrupted": false,
   "mods": [{"fid": 12, "tier": 2, "side": "prefix", "text": "...", "kind": "normal|essence|desecrated",
             "fractured": false}]}
Targets: [{"fid": 12, "max_tier": 2}]  (fid = family index in the base's pool, tier 1 = best), or
         [{"xid": "AbyssMod...", "side": "suffix"}] for an Abyss-exclusive desecrated mod (poe2kit/desecration.py)
Desecration: an unrevealed mod is {"kind": "desecrated", "unrevealed": true, "side", "bone"}; revealed exclusive
mods carry "xid" and "lineage".

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
        lv = lambda m: 1 if m.get('unrevealed') else 65 if m.get('xid') else \
            next((t['level'] for t in _fam(pool, m['fid'])['tiers'] if t['tier'] == m['tier']), 0) \
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
    elif a == 'annul' and action.get('light'):   # Omen of Light: removes only the desecrated mod
        from . import desecration as _d
        dm = next((m for m in s['mods'] if m.get('kind') == 'desecrated' and not m.get('fractured')), None)
        if not dm:
            return s, 'There is no desecrated mod to remove.', used
        s['mods'].remove(dm)
        used, msg = ['Orb of Annulment', 'Omen of Light'], f"Removed the desecrated {dm['text']}"
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
    elif a == 'desecrate':
        from . import desecration as _d
        b = _d.bone(action.get('bone') or '')
        if not b:
            return s, 'Pick a bone.', used
        if s['rarity'] != 'rare':
            return s, 'Bones only work on rare items.', used
        if pool['class'] not in (b.get('item_classes') or []):
            return s, f"{b['name']} doesn't work on {pool['class']} items.", used
        if b.get('max_item_level') and s['ilvl'] > b['max_item_level']:
            return s, f"{b['name']} only works up to item level {b['max_item_level']}.", used
        if b.get('min_item_level') and s['ilvl'] < b['min_item_level']:
            return s, f"{b['name']} needs item level {b['min_item_level']} or more.", used
        if _d.has_desecrated(s):
            return s, 'The item already has a desecrated mod (remove it first: Annulment + Omen of Light).', used
        lin = _d.LINEAGE_OMEN.get(action.get('lineage_omen') or '')
        if lin and not b.get('lineage_omens_allowed'):
            return s, f"{action['lineage_omen']} only works with Preserved or Ancient bones on weapons and jewellery.", used
        removed = None
        if len(s['mods']) >= 6 or (side and _open(s, side) <= 0):   # a full item (or side): a random mod goes
            removed = _remove(s, side if side and _open(s, side) <= 0 else None, rng)
        room = [sd for sd in ('prefix', 'suffix') if _open(s, sd) > 0]
        sd = side if side in room else (rng.choice(room) if room else None)
        if not sd:
            return s, 'No room for the desecrated mod.', used
        s['mods'].append({'fid': None, 'tier': None, 'side': sd, 'text': f'Unrevealed desecrated {sd}',
                          'kind': 'desecrated', 'unrevealed': True, 'fractured': False, 'bone': b['name'],
                          'lineage_omen': lin})
        used = [b['name']] + ([_d.SIDE_OMEN[side]] if side else []) + ([action['lineage_omen']] if lin else [])
        msg = f'Added an unrevealed desecrated {sd}' + (f" (removed {removed['text']})" if removed else '') + \
            '. Reveal it at the Well of Souls.'
    elif a == 'reveal':
        from . import desecration as _d
        u = _d.unrevealed(s)
        if not u:
            return s, 'There is no unrevealed desecrated mod.', used
        pick = action.get('mod')
        if not pick:   # the simulator: take a target if offered, else the first option; Echoes rerolls once
            targets = action.get('targets') or []
            b = _d.bone(u.get('bone') or '')
            opts = _d.options(s, pool, rng, b, u.get('lineage_omen'))
            pick = next((o for o in opts if _is_target(o, targets)), None)
            if not pick and action.get('echoes'):
                opts = _d.options(s, pool, rng, b, u.get('lineage_omen'))
                pick = next((o for o in opts if _is_target(o, targets)), None)
            pick = pick or (opts[0] if opts else None)
        if not pick:
            return s, 'No options could be offered for this item.', used
        s['mods'].remove(u)
        s['mods'].append(dict(pick, kind='desecrated', unrevealed=False))
        used = [_d.ECHOES] if action.get('echoes') else []
        msg = f"Revealed {pick['text']}" + (f" ({pick['lineage']})" if pick.get('lineage') else '')
    elif a == 'putrefaction':
        from . import desecration as _d
        b = _d.bone(action.get('bone') or '')
        if not b or s['rarity'] != 'rare':
            return s, 'Putrefaction needs a rare item and a bone.', used
        keep = [m for m in s['mods'] if m.get('fractured')]
        s['mods'] = keep + [{'fid': None, 'tier': None, 'side': sd, 'text': f'Unrevealed desecrated {sd}', 'kind': 'desecrated',
                             'unrevealed': True, 'fractured': False, 'bone': b['name']}
                            for sd in ['prefix'] * (3 - sum(m['side'] == 'prefix' for m in keep)) +
                            ['suffix'] * (3 - sum(m['side'] == 'suffix' for m in keep))]
        s['corrupted'] = True
        used, msg = [b['name'], 'Omen of Putrefaction'], 'Every mod replaced by unrevealed desecrated mods; the item is corrupted'
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
        if t.get('xid') and m.get('xid') == t['xid']:
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
    missing = [t for t in targets if t not in hit and (t.get('fid') is not None or t.get('xid'))]
    side_of = lambda t: t['side'] if t.get('xid') else _fam(pool, t['fid'])['side']
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
        opts += _desecration_options(state, pool, targets, missing, prices, cost)
        good_unfrac = [m for m in state['mods'] if _is_target(m, targets) and not m.get('fractured')]
        if len(state['mods']) >= 4 and good_unfrac and not any(m.get('fractured') for m in state['mods']):
            p = len(good_unfrac) / len(state['mods'])
            opts.append({'label': 'Fracturing Orb (lock a mod)', 'action': {'type': 'fracture'}, 'p_progress': round(p, 4),
                         'cost': cost(['Fracturing Orb']), 'note': 'fractures a random mod: good if it picks a target'})
    opts = [o for o in opts if o.get('p_progress') != 0]   # can't reach any missing target this way
    for o in opts:
        if o.get('p_progress') and o.get('cost') and 'expected_cost' not in o:
            o['expected_cost'] = round(o['cost'] / o['p_progress'], 2)
    opts.sort(key=lambda o: (o.get('expected_cost') is None, o.get('expected_cost') or 1e9))
    if opts:
        opts[0]['recommended'] = True
    return {'done': False, 'hit': len(hit), 'of': len(targets), 'missing': len(missing), 'junk': len(junk),
            'options': opts}


def _desecration_options(state, pool, targets, missing, prices, cost):
    """Bones on a rare: reveal a waiting mod, clear a junk desecrated mod, or desecrate for a missing target (the only
    way to the Abyss-exclusive mods). Odds from poe2kit/desecration.p_offer (uniform weights, 8% per option)."""
    try:
        from . import desecration as _d
        bones = [b for b in _d.bones_for(pool['class'], state['ilvl']) if b['ok']]
    except Exception:
        return []
    out = []
    u = _d.unrevealed(state)
    note = 'odds: about 8% per option from the Abyss pool (our reading of the game data); every mod counts the same'
    if u:
        b = _d.bone(u.get('bone') or '') or {}
        for echoes in (False, True):
            p = max((_d.p_offer(state, pool, t, b, echoes, u.get('lineage_omen')) for t in missing
                     if (t['side'] if t.get('xid') else _fam(pool, t['fid'])['side']) == u['side']), default=0)
            items = [_d.ECHOES] if echoes else []
            out.append({'label': 'Reveal it at the Well of Souls' + (f' + {_d.ECHOES} (reroll once)' if echoes else ''),
                        'action': {'type': 'reveal', 'echoes': echoes, 'targets': targets}, 'p_progress': round(p, 4),
                        'cost': cost(items), 'note': 'pick 1 of 3 options; ' + note})
        return out
    dm = next((m for m in state['mods'] if m.get('kind') == 'desecrated'), None)
    if dm:
        if not _is_target(dm, targets) and not dm.get('fractured'):
            out.append({'label': 'Orb of Annulment + Omen of Light (remove the desecrated mod)',
                        'action': {'type': 'annul', 'light': True}, 'p_progress': None,
                        'cost': cost(['Orb of Annulment', 'Omen of Light']),
                        'note': 'frees the item for another bone; removes only the desecrated mod'})
        return out
    for t in missing:
        side = t['side'] if t.get('xid') else _fam(pool, t['fid'])['side']
        if not t.get('xid') and _open(state, side) <= 0:
            continue   # a normal target on a full side: the bone would remove a random mod first
        lin = None
        if t.get('xid'):
            m = next((x for x in _d.data()['mod_pool'] if x['id'] == t['xid']), {})
            lin = m.get('lineage')
        best = None
        for b in bones:
            bd = _d.bone(b['name'])
            lo = next((k for k, v in _d.LINEAGE_OMEN.items() if v == lin), None) if lin and b['lineage_omens'] else None
            for echoes in (False, True):
                p = _d.p_offer(state, pool, dict(t, side=side), bd, echoes, _d.LINEAGE_OMEN.get(lo) if lo else None)
                if not p:
                    continue
                items = [b['name'], _d.SIDE_OMEN[side]] + ([lo] if lo else []) + ([_d.ECHOES] if echoes else [])
                c = cost(items)
                e = c / p if c else None
                if best is None or (e is not None and (best['expected_cost'] is None or e < best['expected_cost'])):
                    best = {'label': ' + '.join(items) + ', then reveal', 'p_progress': round(p, 4), 'cost': c,
                            'expected_cost': round(e, 2) if e else None, 'note': note,
                            'action': {'type': 'desecrate', 'bone': b['name'], 'side': side,
                                       'lineage_omen': lo, 'then_echoes': echoes}}
        if best:
            out.append(best)
    return out


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
            if act['type'] == 'desecrate' and any(m.get('unrevealed') for m in s['mods']):
                s, _msg, used = apply(s, {'type': 'reveal', 'echoes': act.get('then_echoes'), 'targets': targets}, rng)
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
