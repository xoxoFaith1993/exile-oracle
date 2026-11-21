"""B2: a living in-game Build Planner plan.

Each vault build can have a saved plan (database key planner:<build_id>):
  follow  the character it follows (its level-ups in Client.txt rewrite the .build file, which the game reloads)
  notes   Claude's hover notes (see buildplanner.make)
  edits   changes made by conversation, applied to the PoB build before export:
            {'add_passives': [node name or game id], 'remove_passives': [...], 'swap_gems': {old name: new name}}
  level   the last level written

check() runs the edited build through Path of Building first and reports what changes (DPS, life, resistances...)
plus warnings (a node that isn't connected to the rest of the tree, a gem name PoB doesn't know)."""

import json
import re
import time
import xml.etree.ElementTree as ET

from . import buildplanner, config, db, vault

KEY = 'planner:'


# ---------------- saved plan ----------------

def get(con, build_id):
    try:
        return json.loads(db.kv_get(con, KEY + str(int(build_id)), '{}') or '{}')
    except ValueError:
        return {}


def save(con, build_id, **changes):
    st = get(con, build_id)
    for k, v in changes.items():
        if v is None:
            continue
        if k in ('notes', 'edits') and isinstance(v, dict):   # merge, so a new note doesn't wipe the old ones
            cur = st.setdefault(k, {})
            for kk, vv in v.items():
                if isinstance(vv, dict) and isinstance(cur.get(kk), dict):
                    cur[kk].update(vv)
                elif isinstance(vv, list) and isinstance(cur.get(kk), list):
                    cur[kk] = list(dict.fromkeys(cur[kk] + vv))
                else:
                    cur[kk] = vv
        else:
            st[k] = v
    st['updated'] = time.time()
    db.kv_set(con, KEY + str(int(build_id)), json.dumps(st))
    con.commit()
    return st


def followed(con):
    """{character name (lower case): build_id} for every plan that follows a character."""
    out = {}
    for r in con.execute("SELECT k, v FROM kv WHERE k LIKE ?", (KEY + '%',)):
        try:
            st = json.loads(r['v'])
        except ValueError:
            continue
        if st.get('follow'):
            out[st['follow'].lower()] = int(r['k'][len(KEY):])
    return out


# ---------------- edits ----------------

_gems = {}


def _gem_index():
    """Gem name (lower case) -> {gameId, grantedEffectId, variantId, support} from PoB's own gem data."""
    if _gems:
        return _gems
    import os
    try:
        text = open(os.path.join(config.POB_DIR, 'src', 'Data', 'Gems.lua'), encoding='utf-8').read()
    except OSError:
        return _gems
    for block in text.split('\n\t["')[1:]:
        f = {k: v for k, v in re.findall(r'\n\t\t(name|gameId|grantedEffectId|variantId) = "([^"]*)"', block)}
        if f.get('name') and f.get('gameId'):
            f['support'] = 'SupportGem' in f['gameId']
            _gems.setdefault(f['name'].lower(), f)
    return _gems


def _tree(version):
    from . import character
    t = character.tree(version)
    adj = {}
    for e in t['edges']:   # [a, b] straight, or [a, b, radius, side] for arcs
        a, b = e[0], e[1]
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    return {n['id']: n for n in t['nodes']}, adj


def _node_num(ref, nodes, ids_rev):
    """A node given by game id ('strength89'), number, or name (notables/keystones are unique)."""
    s = str(ref).strip()
    if s.isdigit():
        return int(s)
    if s in ids_rev:
        return ids_rev[s]
    hits = [n['id'] for n in nodes.values() if (n.get('n') or '').lower() == s.lower()]
    if len(hits) == 1:
        return hits[0]
    return hits[0] if hits and nodes[hits[0]].get('k') in ('notable', 'keystone') else None


def apply_edits(xml_text, edits):
    """Returns (new xml, warnings)."""
    edits = edits or {}
    warnings = []
    root = ET.fromstring(xml_text)
    tree = root.find('Tree')
    specs = tree.findall('Spec')
    spec = specs[max(0, int(tree.get('activeSpec') or 1) - 1)]
    nodes, adj = _tree(spec.get('treeVersion') or '0_5')
    ids_rev = {v: int(k) for k, v in buildplanner._ids()['passives'].items()}
    have = [int(x) for x in (spec.get('nodes') or '').split(',') if x]
    for ref in edits.get('remove_passives') or []:
        n = _node_num(ref, nodes, ids_rev)
        if n in have:
            have.remove(n)
        else:
            warnings.append(f'remove: {ref} is not in the tree')
    added = []
    for ref in edits.get('add_passives') or []:
        n = _node_num(ref, nodes, ids_rev)
        if n is None:
            warnings.append(f'add: no passive called {ref}')
        elif n not in have:
            have.append(n)
            added.append(n)
    hs = set(have)
    for n in added:   # a planned node must touch the rest of the path, or the game can't reach it
        if not (adj.get(n, set()) & hs):
            warnings.append(f"add: {nodes.get(n, {}).get('n', n)} isn't connected to the planned tree; add the nodes "
                            'leading to it too')
    spec.set('nodes', ','.join(str(x) for x in have))
    gi = _gem_index()
    for old, new in (edits.get('swap_gems') or {}).items():
        g = gi.get(str(new).lower())
        if not g:
            warnings.append(f'swap: Path of Building has no gem called {new}')
            continue
        hit = False
        for gem in root.iter('Gem'):
            if (gem.get('nameSpec') or '').lower() == str(old).lower():
                gem.set('nameSpec', g['name'])
                gem.set('gemId', g['gameId'])
                gem.set('skillId', g.get('grantedEffectId') or '')
                if g.get('variantId'):
                    gem.set('variantId', g['variantId'])
                hit = True
        if not hit:
            warnings.append(f'swap: {old} is not in the build')
    return ET.tostring(root, encoding='unicode'), warnings


def check(con, build_id, edits):
    """What the edits change, measured by Path of Building (before -> after), without saving anything."""
    from . import pob
    r = con.execute('SELECT pob_code FROM build WHERE id=?', (int(build_id),)).fetchone()
    if not r:
        raise ValueError('no such build in the vault')
    base = vault.decode(r['pob_code'])
    cur = get(con, build_id).get('edits') or {}
    before_xml, _ = apply_edits(base, cur)
    merged = json.loads(json.dumps(cur))
    for k, v in (edits or {}).items():
        if isinstance(v, list):
            merged[k] = list(dict.fromkeys((merged.get(k) or []) + v))
        elif isinstance(v, dict):
            merged.setdefault(k, {}).update(v)
    after_xml, warnings = apply_edits(base, merged)
    a, b = pob.calc(before_xml), pob.calc(after_xml, main_group=None)
    sa, sb = pob.key_stats(a), pob.key_stats(b)
    diff = {k: {'before': sa[k], 'after': sb.get(k), 'change_pct': round((sb.get(k, 0) / sa[k] - 1) * 100, 1)
                if sa[k] else None} for k in sa if sb.get(k) != sa[k]}
    return {'changes': diff, 'warnings': warnings, 'main_skill': b.get('main_skill'), 'edits_if_saved': merged}


# ---------------- writing, with level-aware notes ----------------

def _level_notes(doc, level):
    """Mark what's due at this level: passives whose level range starts soon get a 'next' note."""
    if not level:
        return
    nxt = [p for p in doc['passives'] if isinstance(p, dict) and isinstance(p.get('level_interval'), list)
           and level < p['level_interval'][0] <= level + 10]
    for p in nxt:
        tag = f"<green>{{Next: from level {p['level_interval'][0]}}}"
        p['additional_text'] = tag + ('\n' + p['additional_text'] if p.get('additional_text') else '')
    extra = f"Level {level} now" + (f"; {len(nxt)} planned passives come in the next 10 levels" if nxt else '')
    doc['description'] = (doc.get('description') or '') + f"\n{extra} (updated {time.strftime('%H:%M')})"


def export(con, build_id, write=True, confirm=False, level=None, name=None):
    """Make the .build from the build + its saved plan (edits, notes, level) and write it."""
    st = get(con, build_id)
    r = con.execute('SELECT label, pob_code FROM build WHERE id=?', (int(build_id),)).fetchone()
    if not r:
        raise ValueError('no such build in the vault')
    xml, warnings = apply_edits(vault.decode(r['pob_code']), st.get('edits'))
    doc, rep = buildplanner.make(con, None, vault.encode(xml), st.get('notes'), name or st.get('name') or r['label'])
    if rep.get('slots') == 0:   # gear prices need the vault build id
        doc2, rep2 = buildplanner.make(con, build_id, None, st.get('notes'), name or st.get('name') or r['label'])
        if st.get('edits'):
            doc2['passives'], doc2['skills'] = doc['passives'], doc['skills']
        doc, rep = doc2, dict(rep2, passives=rep['passives'], skills=rep['skills'])
    level = level or st.get('level')
    _level_notes(doc, level)
    rep['edit_warnings'] = warnings
    out = {'report': rep, 'doc': doc}
    if write:
        out['write'] = buildplanner.write(doc, confirm)
        if out['write'].get('ok'):
            save(con, build_id, level=level, file=out['write']['path'])
    return out


def on_levelups(con, since_ts):
    """Monitor hook: rewrite the plan of every followed character that levelled up since since_ts.
    Only after the player allowed Build Planner files (the first write is always theirs)."""
    if not config.settings().get('build_planner_ok'):
        return []
    follow = followed(con)
    if not follow:
        return []
    done = []
    rows = con.execute("SELECT ts, a, c FROM log_event WHERE kind='levelup' AND ts>? ORDER BY ts", (since_ts,)).fetchall()
    latest = {}
    for r in rows:
        if (r['a'] or '').lower() in follow:
            latest[r['a'].lower()] = int(r['c'])
    for char, level in latest.items():
        bid = follow[char]
        if get(con, bid).get('level') == level:
            continue
        try:
            res = export(con, bid, write=True, level=level)
            if res['write'].get('ok'):
                done.append(f'{char} {level}')
        except Exception as e:
            done.append(f'{char}: failed ({e})')
    return done
