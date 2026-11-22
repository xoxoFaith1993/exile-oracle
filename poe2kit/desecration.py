"""Desecration in the Craft lab (research/desecration; the author 2026-11-21: "does the crafting lab include desecration
mods and the whole desecration system?").

A bone adds one UNREVEALED desecrated prefix or suffix to a rare (a random mod goes if the item is full; one
desecrated mod per item). At the Well of Souls the player picks 1 of 3 options for that side; Omen of Abyssal
Echoes swaps the 3 for a new 3 once. Each option comes from the Abyss-exclusive pool (Ulaman / Amanamu / Kurgal
lineage mods for the item class) with the bone's exclusive_option_chance (0.08 for Preserved / Ancient, 0 Gnawed),
otherwise from the item's normal pool (Ancient: mod level 40+). Lineage omens (Sovereign / Liege / Blackblooded,
weapons and jewellery, Preserved or Ancient) guarantee one option of that lineage.

How sure: the rules are high confidence (game files + patch notes); the 8% per option is our reading of an unnamed
game-data column (low); real weights aren't in the game files, so every mod counts the same (as in the rest of the
simulator). The UI and the planner say so."""

import json
import random

from . import config

_cache = {}
LINEAGE_OMEN = {'Omen of the Sovereign': 'Ulaman', 'Omen of the Liege': 'Amanamu', 'Omen of the Blackblooded': 'Kurgal'}
SIDE_OMEN = {'prefix': 'Omen of Sinistral Necromancy', 'suffix': 'Omen of Dextral Necromancy'}
ECHOES = 'Omen of Abyssal Echoes'
UNCERTAIN = ('Desecration odds: each of the 3 options is Abyss-exclusive with about an 8% chance (our reading of a '
             'game-data value, low confidence); every mod counts the same because real weights are not in the game '
             'files.')


def data():
    if 'd' not in _cache:
        p = config.data_file('desecration.json')
        if not p:
            raise FileNotFoundError('desecration.json is missing from the data pack')
        _cache['d'] = json.load(open(p, encoding='utf-8'))
    return _cache['d']


def bone(name):
    return next((b for b in data()['bones'] if b['name'] == name), None)


def bones_for(item_class, ilvl):
    """Bones that work on this item class and item level, with why the others don't."""
    out = []
    for b in data()['bones']:
        if item_class not in (b.get('item_classes') or []):
            continue
        why = None
        if b.get('max_item_level') and ilvl > b['max_item_level']:
            why = f"item level {ilvl} is above {b['max_item_level']}"
        elif b.get('min_item_level') and ilvl < b['min_item_level']:
            why = f"item level {ilvl} is below {b['min_item_level']}"
        elif b.get('dropped_since'):
            why = f"no longer drops (since {b['dropped_since']})"
        out.append({'name': b['name'], 'tier': b['tier'], 'ok': why is None, 'why': why,
                    'exclusive_option_chance': b.get('exclusive_option_chance') or 0,
                    'lineage_omens': bool(b.get('lineage_omens_allowed')), 'unstable': bool(b.get('unstable')),
                    'min_modifier_level': b.get('min_modifier_level') or 0, 'description': b.get('description')})
    return out


def exclusive(item_class, side, b=None, lineage=None):
    """The Abyss-exclusive mods this bone can offer on this item class and side."""
    pool = 'altered_collarbone' if b and b['name'].startswith('Altered') else \
        'cranium_jewel' if item_class == 'Jewel' else 'vertebrae_waystone' if item_class == 'Map' else 'bone_equipment'
    return [m for m in data()['mod_pool'] if m.get('spawnable') and m['side'] == side and m['pool'] == pool
            and item_class in m['item_classes'] and (lineage is None or m.get('lineage') == lineage)]


def _ex_mod(m):
    return {'fid': None, 'tier': None, 'side': m['side'], 'text': m['text'].replace('\n', ' / '), 'kind': 'desecrated',
            'fractured': False, 'lineage': m.get('lineage'), 'group': m.get('mod_type'), 'xid': m['id']}


def unrevealed(state):
    return next((m for m in state['mods'] if m.get('unrevealed')), None)


def has_desecrated(state):
    return any(m.get('kind') == 'desecrated' for m in state['mods'])


def options(state, pool, rng, b=None, lineage=None):
    """3 reveal options (mod dicts) for the item's unrevealed mod: different groups, none already on the item."""
    from . import craftsim
    u = unrevealed(state)
    if not u:
        return []
    b = b or bone(u.get('bone') or '') or {}
    side = u['side']
    chance = b.get('exclusive_option_chance') or 0
    base_state = dict(state, mods=[m for m in state['mods'] if m is not u])
    normal = craftsim.eligible(base_state, pool, side, b.get('min_modifier_level') or 0)
    ex = exclusive(pool['class'], side, b)
    have_groups = {m.get('group') for m in state['mods'] if m.get('group')}
    ex = [m for m in ex if m.get('mod_type') not in have_groups]
    picked, seen = [], set()

    def add(m):
        k = m.get('group') or ('fid', m.get('fid'))
        if k in seen:
            return False
        seen.add(k)
        picked.append(m)
        return True
    if lineage:   # a lineage omen: one option is guaranteed from that lineage (if the class has any on this side)
        lx = [m for m in ex if m.get('lineage') == lineage]
        if lx:
            add(_ex_mod(rng.choice(lx)))
    tries = 0
    while len(picked) < 3 and tries < 60:
        tries += 1
        if ex and rng.random() < chance:
            add(_ex_mod(rng.choice(ex)))
        elif normal:
            f, ok = rng.choice(normal)
            t = rng.choice(ok)
            add({'fid': f['fid'], 'tier': t['tier'], 'side': side, 'text': t['text'], 'kind': 'desecrated',
                 'fractured': False, 'group': ('fid', f['fid'])})
        elif ex:
            add(_ex_mod(rng.choice(ex)))
        else:
            break
    return picked


def p_offer(state, pool, target, b, echoes=False, lineage=None):
    """Chance the wanted mod is among the options (target: {'fid'} for a normal family or {'xid'} for an exclusive
    one), with one reroll if echoes. Uniform weights, like the rest of the simulator."""
    from . import craftsim
    side = target.get('side')
    chance = b.get('exclusive_option_chance') or 0
    if target.get('xid'):
        ex = exclusive(pool['class'], side, b)
        n = len(ex) or 1
        m = next((x for x in ex if x['id'] == target['xid']), None)
        if not m:
            return 0.0
        p_one = chance / n
        if lineage and m.get('lineage') == lineage:
            lx = [x for x in ex if x.get('lineage') == lineage]
            p_set = 1 - (1 - 1 / len(lx)) * (1 - p_one) ** 2
        else:
            p_set = 1 - (1 - p_one) ** 3
    else:
        normal = craftsim.eligible(state, pool, side, b.get('min_modifier_level') or 0)
        n = len(normal) or 1
        if not any(f['fid'] == target.get('fid') for f, _ in normal):
            return 0.0
        p_one = (1 - chance) / n
        p_set = 1 - (1 - p_one) ** (2 if lineage else 3)
    return 1 - (1 - p_set) ** (2 if echoes else 1)


def reference():
    """For the UI and the AI: bones, omens and the rules, with how sure each is."""
    d = data()
    return {'bones': [{k: b.get(k) for k in ('name', 'tier', 'item_class_names', 'max_item_level', 'min_item_level',
                                             'min_modifier_level', 'exclusive_option_chance', 'lineage_omens_allowed',
                                             'unstable', 'dropped_since', 'description')} for b in d['bones']],
            'omens': [{k: o.get(k) for k in ('name', 'description', 'effect_type', 'confidence')} for o in d['omens']],
            'rules': [{k: r.get(k) for k in ('id', 'rule', 'confidence')} for r in d['rules']],
            'unrevealed_item': d.get('unrevealed_item'), 'note': UNCERTAIN}


def simulate_reveal_rng(seed=None):
    return random.Random(seed)
