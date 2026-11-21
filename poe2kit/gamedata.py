"""Game data from the community RePoE export (repoe-fork.github.io/poe2), stored on F:.
Used for: gem types (skill / spirit / support / lineage), base item tags, and reading rare mods into tiers.
Swap in data extracted from the 1.0 client (poe2x) after Dec 11; the shapes stay the same."""

import json
import os
import re
import time
import urllib.request

from . import config

DATA = os.path.join(config.DATA_DIR, 'repoe')
SRC = 'https://repoe-fork.github.io/poe2'
FILES = ['mods', 'base_items', 'skill_gems', 'uniques', 'item_classes', 'tags', 'gem_tags']
_cache = {}


def update(max_age_days=3):
    """Re-download the export files if older than max_age_days. Returns what changed."""
    os.makedirs(DATA, exist_ok=True)
    out = {}
    for f in FILES:
        p = os.path.join(DATA, f'{f}.min.json')
        if os.path.exists(p) and time.time() - os.path.getmtime(p) < max_age_days * 86400:
            out[f] = 'fresh'
            continue
        req = urllib.request.Request(f'{SRC}/{f}.min.json', headers={'User-Agent': config.user_agent()})
        with urllib.request.urlopen(req, timeout=120) as r:
            body = r.read()
        json.loads(body)  # validate before replacing
        with open(p + '.part', 'wb') as fh:
            fh.write(body)
        os.replace(p + '.part', p)
        out[f] = f'{len(body) // 1024} KB'
    _cache.clear()
    return out


def load(name):
    if name not in _cache:
        with open(os.path.join(DATA, f'{name}.min.json'), encoding='utf-8') as f:
            _cache[name] = json.load(f)
    return _cache[name]


# ---------- gems ----------

def gem_info(name):
    """{'type': 'active'|'spirit'|'support', 'lineage': bool, 'tags': [...]} or None."""
    idx = _cache.get('_gems')
    if idx is None:
        idx = {}
        for v in load('skill_gems').values():
            bi = v.get('base_item') or {}
            n = (bi.get('display_name') or '').lower()
            if n and bi.get('release_state', 'released') == 'released' and n not in idx:
                idx[n] = {'type': v.get('gem_type'), 'lineage': bool(v.get('is_lineage')), 'tags': v.get('tags', [])}
        _cache['_gems'] = idx
    return idx.get(name.lower())


# ---------- bases ----------

def base_info(name):
    idx = _cache.get('_bases')
    if idx is None:
        idx = {}
        for k, v in load('base_items').items():
            n = v.get('name')
            if n and v.get('release_state', 'released') == 'released' and n not in idx:
                idx[n] = {'id': k, 'tags': set(v.get('tags', [])), 'class': v.get('item_class'),
                          'level': v.get('drop_level')}
        _cache['_bases'] = idx
    return idx.get(name)


# ---------- mods → tiers ----------

_NUM = re.compile(r'\(\s*-?\d+(?:\.\d+)?\s*-\s*-?\d+(?:\.\d+)?\s*\)|-?\d+(?:\.\d+)?')
_RANGE = re.compile(r'\(\s*(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)\s*\)|(-?\d+(?:\.\d+)?)')


def _clean(text):
    text = re.sub(r'\[([^\]|]*)\|([^\]]*)\]', r'\2', text)   # [Strength|Strength] -> Strength
    text = re.sub(r'\[([^\]]*)\]', r'\1', text)
    return text.strip()


def _template(text):
    return re.sub(r'\s+', ' ', _NUM.sub('#', _clean(text))).strip().lower()


def _mod_index():
    idx = _cache.get('_mods')
    if idx is None:
        idx = {}
        for mid, m in load('mods').items():
            if m.get('domain') not in ('item', 'misc', 'desecrated') or m.get('generation_type') not in ('prefix', 'suffix'):
                continue
            if not m.get('text') or m.get('is_essence_only'):
                continue
            for li, line in enumerate(m['text'].split('\n')):
                ranges = [(float(a), float(b)) if a != '' else (float(c), float(c))
                          for a, b, c in _RANGE.findall(_clean(line))]
                idx.setdefault(_template(line), []).append({
                    'id': mid, 'name': m.get('name'), 'gen': m['generation_type'], 'level': m.get('required_level', 1),
                    'groups': tuple(m.get('groups', [])), 'weights': m.get('spawn_weights', []),
                    'line': li, 'lines': m['text'].count('\n') + 1, 'ranges': ranges})
        _cache['_mods'] = idx
    return idx


def _spawns_on(mod, tags):
    for w in mod['weights']:
        if w['tag'] in tags or w['tag'] == 'default':
            return w['weight'] > 0
    return False


def read_mod(line, base_tags):
    """Match one explicit mod line on an item to its tier. Returns dict or None."""
    cands = _mod_index().get(_template(line))
    if not cands:
        return None
    vals = [float(x) for x in re.findall(r'-?\d+(?:\.\d+)?', _clean(line))]
    cands = [c for c in cands if _spawns_on(c, base_tags)] or cands
    # Tiers are counted within the same mod group + same line shape, highest level = T1.
    best = None
    for c in cands:
        if len(c['ranges']) != len(vals):
            continue
        fits = all(lo - 1e-9 <= v <= hi + 1e-9 for v, (lo, hi) in zip(vals, c['ranges']))
        if fits and (best is None or c['level'] > best['level']):
            best = c
    if best is None:
        top = max((c['ranges'][0][1] for c in cands if c['ranges']), default=None)
        why = ('above any single mod: probably two mods adding up (e.g. a hybrid) or a special mod'
               if vals and top is not None and vals[0] > top else 'value outside known tiers (special or changed mod)')
        return {'mod': None, 'text': line, 'note': why}
    family = sorted({(c['level'], c['ranges'][0] if c['ranges'] else (0, 0)) for c in cands
                     if c['groups'] == best['groups'] and c['lines'] == best['lines'] and c['line'] == best['line']},
                    key=lambda x: -x[0])
    levels = [lv for lv, _ in family]
    tier = levels.index(best['level']) + 1 if best['level'] in levels else None
    lo, hi = best['ranges'][0] if best['ranges'] else (0, 0)
    roll = round((vals[0] - lo) / (hi - lo) * 100) if vals and hi != lo else 100
    return {'mod': best['name'], 'gen': best['gen'], 'tier': tier, 'tiers': len(levels), 'ilvl_needed': best['level'],
            'roll_pct': roll, 'text': line, 'hybrid': best['lines'] > 1}


def read_item(base, mods):
    """Read every explicit mod of a rare. Returns per-mod tiers and a quality summary."""
    b = base_info(base)
    tags = (b or {}).get('tags', set())
    rows = [read_mod(m, tags) for m in mods]
    known = [r for r in rows if r and r.get('tier')]
    if known and all(r['tiers'] == 1 for r in known):  # jewels: one tier per mod, the roll is what counts
        avg = round(sum(r['roll_pct'] for r in known) / len(known))
        summary = f'jewel: {len(known)}/{len(mods)} mods read, average roll {avg}%'
        return {'base_found': b is not None, 'mods': [r or {'text': m, 'note': 'not matched'} for r, m in zip(rows, mods)],
                'top_tier_count': None, 'avg_roll_pct': avg, 'quality': summary}
    top = sum(1 for r in known if r['tier'] <= 2)
    summary = ('high-end: several top-tier mods' if top >= 3 else
               'strong: some top-tier mods' if top == 2 else
               'decent: one top-tier mod' if top == 1 else
               'budget: no top-tier mods' if known else 'unknown')
    return {'base_found': b is not None, 'mods': [r or {'text': m, 'note': 'not matched'} for r, m in zip(rows, mods)],
            'top_tier_count': top, 'quality': summary}
