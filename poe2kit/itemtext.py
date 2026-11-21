"""Read the item text Path of Exile 2 puts on the clipboard: Ctrl+C (plain) and Ctrl+Alt+C (advanced, with
"{ Prefix Modifier ... }" lines and roll ranges like 56(50-70)%). English client only.

parse(text) -> dict:
  cls, rarity (NORMAL/MAGIC/RARE/UNIQUE/GEM/CURRENCY/...), name, base, ilvl, quality, stack, rune_sockets,
  corrupted, unidentified, mirrored, fractured_item, waystone_tier, gem_level,
  mods: [{text, kind (implicit/explicit/rune/enchant/...), values, ranges, affix, tier, fractured, desecrated}]
  explicits: the explicit mods only (what you pay for on a rare), has_rolls (any mod shows a roll range)."""

import re

SEP = '--------'
NUM = re.compile(r'[+-]?\d+(?:\.\d+)?')
# 56(50-70)  or  7.59(7-7.9)  or  -10(-15--5): value with its roll range (advanced copy)
RANGED = re.compile(r'([+-]?\d+(?:\.\d+)?)\((-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)\)')
SUFFIX = re.compile(r'\s+\((implicit|enchant|rune|added rune|fractured|crafted|desecrated|scourge)\)$')
ADV_HEAD = re.compile(r'^\{\s*(.*?)\s*\}$')
MARKERS = {'Corrupted': 'corrupted', 'Twice Corrupted': 'corrupted', 'Mirrored': 'mirrored',
           'Sanctified': 'sanctified', 'Unmodifiable': 'unmodifiable', 'Fractured Item': 'fractured_item',
           'Split': 'split'}
PROP_PREFIXES = ('Item Class:', 'Rarity:', 'Requires', 'Item Level:', 'Quality:', 'Sockets:', 'Stack Size:',
                 'Level:', 'Grants Skill:', 'Physical Damage:', 'Elemental Damage:', 'Chaos Damage:',
                 'Fire Damage:', 'Cold Damage:', 'Lightning Damage:', 'Critical Hit Chance:', 'Attacks per Second:',
                 'Reload Time:', 'Armour:', 'Evasion Rating:', 'Energy Shield:', 'Block chance:', 'Spirit:',
                 'Charm Slots:', 'Limited to:', 'Radius:', 'Revives Available:', 'Waystone Tier:', 'Area Level:',
                 'Monster Pack Size:', 'Pack Size:', 'Rare Monsters:', 'Magic Monsters:', 'Item Rarity:',
                 'Waystone Drop Chance:', 'Lasts ', 'Consumes ', 'Currently has ', 'Recovers ', 'Reservation:',
                 'Cost:', 'Cast Time:', 'Cooldown Time:', 'Use Time:', 'Experience:', 'Uses ', 'Socketed ')
FLAVOUR_HINTS = ('Right Click', 'Place into', 'Can be used in', 'Shift click', 'Travel to', 'Place one or more',
                 'Creates a ', 'Can be ', 'Use this ')


def _values(line):
    """Mod line -> (clean text with values only, [values], [(lo, hi) or None])."""
    vals, ranges = [], []

    def ranged(m):
        vals.append(float(m.group(1)))
        ranges.append((float(m.group(2)), float(m.group(3))))
        return m.group(1)
    t = RANGED.sub(ranged, line)
    t = t.replace(' — Unscalable Value', '').strip()
    if not vals:
        vals = [float(x) for x in NUM.findall(t)]
        ranges = [None] * len(vals)
    return t, vals, ranges


def _num(s):
    m = NUM.search(s or '')
    return float(m.group()) if m else None


PROP_LINE = re.compile(r"^[A-Z][\w' ]{0,40}: ")   # "Monster Rarity: +32% (augmented)"


def _is_prop_section(lines):
    return all(any(l.startswith(p) for p in PROP_PREFIXES) or PROP_LINE.match(l) for l in lines)


def parse(text):
    text = (text or '').replace('\r\n', '\n').strip()
    secs, cur = [], []
    for l in text.split('\n'):
        l = l.strip()
        if l == SEP:
            if cur:
                secs.append(cur)
            cur = []
        elif l:
            cur.append(l)
    if cur:
        secs.append(cur)
    it = {'cls': None, 'rarity': None, 'name': None, 'base': None, 'ilvl': None, 'quality': None, 'stack': None,
          'rune_sockets': 0, 'corrupted': False, 'unidentified': False, 'unid_tier': None, 'mirrored': False,
          'fractured_item': False, 'waystone_tier': None, 'gem_level': None, 'mods': [], 'has_rolls': False,
          'advanced': False}
    if not secs:
        return it
    head = secs[0]
    rest = []
    for l in head:
        if l.startswith('Item Class:'):
            it['cls'] = l.split(':', 1)[1].strip()
        elif l.startswith('Rarity:'):
            it['rarity'] = l.split(':', 1)[1].strip().upper()
        else:
            rest.append(l)
    if not it['rarity']:
        return it
    if len(rest) >= 2:
        it['name'], it['base'] = rest[0], rest[1]
    elif rest:
        it['name'] = it['base'] = rest[0]
    if it['rarity'] == 'MAGIC':   # "Crackling Temple Maul of the Brute": base is inside; trade matches by name
        it['base'] = None
    if it['rarity'] == 'NORMAL' and (it['base'] or '').startswith('Superior '):
        it['base'] = it['base'][len('Superior '):]
    m = re.match(r'^(.*?)\s*\(Tier (\d+)\)$', it['base'] or '')
    if m and 'Waystone' in m.group(1):
        it['waystone_tier'] = int(m.group(2))
    body_secs = secs[1:]
    explicit_done = False
    for sec in body_secs:
        # one-line markers and the properties that matter
        if len(sec) == 1 and sec[0] in MARKERS:
            it[MARKERS[sec[0]]] = True
            continue
        u = re.match(r'^Unidentified(?:\s*\(Tier\s*(\d+)\))?$', sec[0])
        if u and len(sec) == 1:
            it['unidentified'] = True
            it['unid_tier'] = int(u.group(1)) if u.group(1) else None
            continue
        props = False
        for l in sec:
            if l.startswith('Item Level:'):
                it['ilvl'] = int(_num(l) or 0) or None
                props = True
            elif l.startswith('Quality:'):
                it['quality'] = int(_num(l) or 0)
                props = True
            elif l.startswith('Stack Size:'):
                it['stack'] = int(_num(l.replace(',', '')) or 1)
                props = True
            elif l.startswith('Sockets:'):
                it['rune_sockets'] = l.split(':', 1)[1].split().count('S')
                props = True
            elif l.startswith('Level:') and it['rarity'] == 'GEM':
                it['gem_level'] = int(_num(l) or 0)
                props = True
        if props or _is_prop_section(sec):
            continue
        if any(sec[0].startswith(h) for h in FLAVOUR_HINTS):
            continue
        if any(l.startswith('{') for l in sec):   # advanced copy: each block is "{ header }" + its lines
            it['advanced'] = True
            hdr = None
            for l in sec:
                h = ADV_HEAD.match(l)
                if h:
                    hdr = h.group(1).split('—')[0].strip()
                    continue
                if l.startswith('(') and l.endswith(')'):   # reminder text
                    continue
                low = (hdr or '').lower()
                kind = ('implicit' if low.startswith('implicit') else 'unique' if low.startswith('unique')
                        else 'corruption' if low.startswith('corruption') else 'explicit')
                tier = re.search(r'\(Tier: (\d+)\)', hdr or '')
                m = SUFFIX.search(l)
                if m:   # an enchant/rune line inside an advanced block section
                    tag = m.group(1).replace('added ', '')
                    if tag in ('fractured', 'desecrated', 'crafted'):
                        low += ' ' + tag
                    else:
                        kind = tag
                    l = l[:m.start()]
                t, vals, rngs = _values(l)
                if any(rngs):
                    it['has_rolls'] = True
                it['mods'].append({'text': t, 'kind': 'explicit' if kind == 'unique' else kind, 'values': vals,
                                   'ranges': rngs, 'tier': int(tier.group(1)) if tier else None,
                                   'affix': 'prefix' if 'prefix' in low else 'suffix' if 'suffix' in low else None,
                                   'fractured': 'fractured' in low, 'desecrated': 'desecrated' in low,
                                   'crafted': 'crafted' in low})
            explicit_done = True
            continue
        # plain copy: tagged lines, else the first untagged mod section is the explicit mods (later ones: flavour)
        tagged = [SUFFIX.search(l) for l in sec]
        if any(tagged):
            for l, m in zip(sec, tagged):
                kind = m.group(1).replace('added ', '') if m else 'explicit'
                if m:
                    l = l[:m.start()]
                t, vals, rngs = _values(l)
                it['mods'].append({'text': t, 'kind': 'explicit' if kind in ('fractured', 'desecrated', 'crafted') else kind,
                                   'values': vals, 'ranges': rngs, 'tier': None, 'affix': None,
                                   'fractured': kind == 'fractured', 'desecrated': kind == 'desecrated',
                                   'crafted': kind == 'crafted'})
            if all(m and m.group(1) in ('fractured', 'desecrated', 'crafted') or not m for m in tagged):
                explicit_done = True
            continue
        if explicit_done or it['rarity'] in ('CURRENCY', 'GEM', 'NORMAL', 'DIVINATION CARD', 'QUEST'):
            continue
        if sec[0].startswith('Grants Skill:'):
            continue
        for l in sec:
            t, vals, rngs = _values(l)
            it['mods'].append({'text': t, 'kind': 'explicit', 'values': vals, 'ranges': rngs, 'tier': None,
                               'affix': None, 'fractured': False, 'desecrated': False, 'crafted': False})
        explicit_done = True
    it['explicits'] = [m for m in it['mods'] if m['kind'] == 'explicit']
    it['ninja_name'] = it['name']
    return it


def summary(it):
    """What the overlay shows in its header."""
    flags = []
    if it.get('corrupted'):
        flags.append('Corrupted')
    if it.get('unidentified'):
        flags.append('Unidentified' + (f" (tier {it['unid_tier']})" if it.get('unid_tier') else ''))
    if it.get('mirrored'):
        flags.append('Mirrored')
    if it.get('fractured_item'):
        flags.append('Fractured')
    if it.get('quality'):
        flags.append(f"{it['quality']}% quality")
    if it.get('rune_sockets'):
        flags.append(f"{it['rune_sockets']} rune socket{'s' if it['rune_sockets'] > 1 else ''}")
    if it.get('stack') and it['stack'] > 1:
        flags.append(f"stack of {it['stack']}")
    if it.get('gem_level'):
        flags.append(f"level {it['gem_level']}")
    return {'name': it.get('name'), 'base': it.get('base'), 'rarity': it.get('rarity'), 'cls': it.get('cls'),
            'ilvl': it.get('ilvl'), 'flags': flags, 'mods': len(it.get('explicits') or [])}
