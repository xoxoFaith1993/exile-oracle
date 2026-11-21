"""Waystone and tablet modifiers, our own in-game search strings, and danger ratings for the player's build.

All original: the mods come from the game data (RePoE fork export of the game files, mods.min.json; domains 'area'
for waystones and 'tablet' for tablets); the search-string builder and the rules are written here. Nothing is taken
from other tools.

In-game search (stash / vendor, Ctrl+F) facts used: it matches item text without case; inside double quotes a
regular expression is allowed, "|" means OR, a leading "!" negates, and the box has a length limit (SEARCH_LIMIT;
PoE 2 raised it to 250 characters in 0.5.0; research/atlas).
"""

import json
import re

from . import gamedata

SEARCH_LIMIT = 250   # raised from 50 in PoE 2 patch 0.5.0 (research/atlas)
# text every waystone / tablet shows besides its mods: a search token must not match these, or "!token" would hide all
ITEM_LINES = ['waystone', 'waystone tier', 'area level', 'item quantity', 'item rarity', 'monster pack size',
              'waystone drop chance', 'revives available', 'corrupted', 'unidentified', 'rarity: normal', 'rarity: magic',
              'rarity: rare', 'rarity: unique', 'item class: waystones', 'item class: tablet', 'precursor tablet',
              'item level', 'uses remaining', 'requires level', 'modifiers', 'tablet', 'breach', 'delirium', 'ritual',
              'expedition', 'irradiated', 'overseer', 'note:', 'place into', 'map device']
TAG = re.compile(r'\[([^\]|]+)\|([^\]]+)\]')   # "[Rarity|Rare]" -> "Rare"
_cache = {}


def _clean(text):
    return TAG.sub(r'\2', re.sub(r'\[([^\]|]+)\]', r'\1', text or ''))


def _norm(line):
    return re.sub(r'\(?-?[\d.]+(?:-[\d.]+)?\)?', '#', line).strip()


def mods(kind='waystone'):
    """Groups of mods (one entry per group, tiers inside) for 'waystone' or 'tablet'."""
    if kind in _cache:
        return _cache[kind]
    allm = gamedata.load('mods')
    dom = 'area' if kind == 'waystone' else 'tablet'
    groups = {}
    for mid, m in allm.items():
        if m.get('domain') != dom or m.get('generation_type') not in ('prefix', 'suffix'):
            continue
        text = _clean(m.get('text') or '').strip()
        if not text:
            continue
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        g = (m.get('groups') or [mid])[0]
        e = groups.setdefault(g, {'group': g, 'kind': m['generation_type'], 'line': _norm(lines[0]),
                                  'extra': [_norm(l) for l in lines[1:]], 'tiers': [], 'stats': []})
        e['tiers'].append({'id': mid, 'text': lines[0], 'level': m.get('required_level'),
                           'extra': lines[1:]})
        for s in m.get('stats') or []:
            if s.get('id') and s['id'] not in e['stats']:
                e['stats'].append(s['id'])
    out = sorted(groups.values(), key=lambda e: (e['kind'], e['line']))
    for e in out:
        e['tiers'].sort(key=lambda t: t['level'] or 0)
    _cache[kind] = out
    return out


# ---------------- search strings ----------------

def _tokens(kind):
    """For each group: the shortest lower-case piece of its main line that appears in no other mod line at all."""
    key = 'tok:' + kind
    if key in _cache:
        return _cache[key]
    groups = mods(kind)
    every = {}
    for e in groups:
        for t in e['tiers']:
            for l in [t['text']] + t['extra']:
                every.setdefault(l.lower(), set()).add(e['group'])
    for l in ITEM_LINES:
        every.setdefault(l, set()).add('__item__')
    toks = {}
    for e in groups:
        mine = [t['text'].lower() for t in e['tiers']]
        base = re.sub(r'[^a-z ]', ' ', e['line'].lower())
        base = re.sub(r' +', ' ', base).strip()
        best = None
        for spaces in (False, True):   # prefer one-word tokens: sturdier against other text on the item
          for n in range(3, len(base) + 1):
            if best:
                break
            for i in range(0, len(base) - n + 1):
                cand = base[i:i + n]
                if cand.startswith(' ') or cand.endswith(' ') or (' ' in cand) != spaces:
                    continue
                if not all(cand in m for m in mine):
                    continue
                if any(cand in line for line, gs in every.items() if e['group'] not in gs):
                    continue
                best = cand
                break
          if best:
            break
        toks[e['group']] = best or base[:20]
    _cache[key] = toks
    return toks


def search_string(avoid=(), want=(), kind='waystone', limit=SEARCH_LIMIT):
    """The text to paste into the in-game search. avoid = groups that must NOT be on the item (shows the good ones);
    want = groups to highlight. Returns {'text', 'length', 'fits', 'parts', 'limit'}."""
    toks = _tokens(kind)
    parts = []
    if avoid:
        parts.append('"!' + '|'.join(toks[g] for g in avoid if g in toks) + '"')
    if want:
        parts.append('"' + '|'.join(toks[g] for g in want if g in toks) + '"')
    text = ' '.join(parts)
    return {'text': text, 'length': len(text), 'fits': len(text) <= limit, 'limit': limit,
            'parts': {g: toks.get(g) for g in list(avoid) + list(want)}}


# ---------------- danger for the player's build ----------------

ELEMENTS = ('fire', 'cold', 'lightning', 'chaos')


def rate(groups, stats):
    """stats = Path of Building key stats of the geared build (lab.defence()['stats']).
    Returns {group: {'level': deadly|risky|fine, 'why'}} for waystone groups."""
    hits = {t: stats.get(f'max hit: {t}') for t in ('physical',) + ELEMENTS}
    known = sorted(v for v in hits.values() if v)
    mid = known[len(known) // 2] if known else None
    out = {}
    for e in groups:
        line = e['line'].lower()
        level, why = 'fine', ''
        el = next((x for x in ELEMENTS if f'extra {x}' in line or f'as extra {x}' in line), None)
        if el:
            h = hits.get(el)
            if h and mid and h < 0.6 * mid:
                level, why = 'deadly', f'your {el} max hit ({h:,.0f}) is your weak spot'
            elif h and mid and h < 0.85 * mid:
                level, why = 'risky', f'your {el} max hit is below your others ({h:,.0f})'
            else:
                why = f'{el} max hit {h:,.0f}' if h else ''
        elif 'maximum' in line and 'resistance' in line and ('less' in line or 'reduced' in line or 'player' in line):
            res = [stats.get(f'{x} res') for x in ('fire', 'cold', 'lightning')]
            level = 'deadly' if any(r is not None and r < 75 for r in res) else 'risky'
            why = 'lowers your max resistances' + (' and you are already uncapped' if level == 'deadly' else '')
        elif 'cursed' in line or ('curse' in line and 'on monsters' not in line and 'player' in line):
            level, why = 'risky', 'curses you for the whole map'
        elif 'recovery' in line or 'regenerat' in line or 'leech' in line or 'recoup' in line:
            level, why = 'risky', 'cuts your life / mana sustain'
        elif 'critical' in line and line.startswith('monsters have'):   # monsters crit YOU (not 'take reduced ... from Critical Hits')
            low = min(known) if known else None
            level = 'risky' if low and low < 8000 else 'fine'
            why = f'big crits vs your lowest max hit ({low:,.0f})' if low else ''
        elif 'armour' in line and 'break' in line:
            arm, eva = stats.get('armour') or 0, stats.get('evasion') or 0
            level = 'risky' if arm > eva else 'fine'
            why = 'you rely on armour' if arm > eva else 'you rely on evasion / energy shield'
        elif any(w in line for w in ('poison', 'bleed', 'ignite', 'freeze', 'shock', 'chill', 'electrocute')):
            level, why = 'risky', 'ailments: check your immunities'
        out[e['group']] = {'level': level, 'why': why}
    return out


def overview(con=None, build_id=None, kind='waystone'):
    """Everything the Atlas page shows: the mod groups (with tiers), each one's search token, and (with a build)
    the danger rating for that build."""
    groups = mods(kind)
    toks = _tokens(kind)
    ratings = {}
    if build_id and kind == 'waystone':
        from . import lab
        ratings = rate(groups, lab.defence(con, build_id)['stats'])
    return {'kind': kind, 'limit': SEARCH_LIMIT,
            'groups': [dict(e, token=toks.get(e['group']), rating=ratings.get(e['group'])) for e in groups]}
