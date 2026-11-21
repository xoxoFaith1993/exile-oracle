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
_names = {}


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
            _names[f['gameId']] = f['name'].lower()   # every version of a gem (e.g. a unique's Lightning Bolt)
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

def deaths(con, name, hours=3):
    """This character's deaths in the last few hours, from Client.txt, with the zone each happened in."""
    from . import clientlog
    since = time.time() - hours * 3600
    rows = con.execute("SELECT ts FROM log_event WHERE kind='slain' AND lower(a)=lower(?) AND ts>? ORDER BY ts",
                       (name, since)).fetchall()
    out = []
    names = clientlog.areas()
    for r in rows:
        z = con.execute("SELECT a FROM log_event WHERE kind='zone' AND ts<=? ORDER BY ts DESC LIMIT 1",
                        (r['ts'],)).fetchone()
        aid = z['a'] if z else None
        out.append((names.get(aid) or {}).get('Name') or aid or 'unknown zone')
    return out


def _mark_next(entry, level):
    iv = entry.get('level_interval') if isinstance(entry, dict) else None
    if not isinstance(iv, list):
        return False
    m = re.search(r'Take at level (\d+)', entry.get('additional_text') or '')
    due = int(m.group(1)) if m else iv[0]   # route passives carry their due level in the note
    if level < due <= level + 10:
        tag = f"<green>{{Next: at level {due}}}"
        entry['additional_text'] = tag + ('\n' + entry['additional_text'] if entry.get('additional_text') else '')
        return True
    return False


def _level_notes(doc, level, died=None):
    """Mark what's due at this level: passives and gems whose level range starts in the next 10 levels get a
    'Next' note; recent deaths go into the description."""
    if not level:
        return
    n_pass = sum(_mark_next(p, level) for p in doc['passives'])
    n_gems = 0
    for sk in doc.get('skills') or []:
        n_gems += _mark_next(sk, level)
        for sup in sk.get('support_skills') or []:
            n_gems += _mark_next(sup, level) if isinstance(sup, dict) else 0
    parts = [f"Level {level} now"]
    if n_pass:
        parts.append(f"{n_pass} planned passives in the next 10 levels")
    if n_gems:
        parts.append(f"{n_gems} gems to cut soon")
    if died:
        from collections import Counter
        top = Counter(died).most_common(1)[0]
        parts.append(f"{len(died)} deaths in the last 3 hours (most in {top[0]}): check resistances and life")
    doc['description'] = (doc.get('description') or '') + '\n' + '; '.join(parts) + f" (updated {time.strftime('%H:%M')})"


def _gem_id(name):
    g = _gem_index().get(str(name).lower())
    return g['gameId'] if g else None


def _apply_skill_plan(doc, edits, rep):
    """edits['levelling_skills']: skills used only while levelling, shown first with their level range:
         [{"gem": "Spark", "from": 1, "to": 65, "supports": ["Lightning Attunement", {"gem": "Lightning
           Penetration", "from": 14}], "note": "..."}]
       edits['skill_levels']: level ranges for the build's own skills, e.g. {"Lightning Bolt": [65, 100]}."""
    from . import route
    unknown = []
    lv_skills = []
    for s in edits.get('levelling_skills') or []:
        gid = _gem_id(s.get('gem'))
        if not gid:
            unknown.append(s.get('gem'))
            continue
        e = {'id': gid, 'level_interval': [int(s.get('from') or route.gem_level(gid) or 1), int(s.get('to') or 100)]}
        if s.get('note'):
            e['additional_text'] = buildplanner._note(s['note'])
        sups = []
        for sp in s.get('supports') or []:
            sp = sp if isinstance(sp, dict) else {'gem': sp}
            sid = _gem_id(sp.get('gem'))
            if not sid:
                unknown.append(sp.get('gem'))
                continue
            frm = int(sp.get('from') or route.gem_level(sid) or 1)
            se = {'id': sid, 'level_interval': [frm, int(sp.get('to') or e['level_interval'][1])]}
            if sp.get('note'):
                se['additional_text'] = buildplanner._note(sp['note'])
            sups.append(se)
        if sups:
            e['support_skills'] = sups
        lv_skills.append(e)
    _gem_index()
    by_name = {}
    for name, rng in (edits.get('skill_levels') or {}).items():
        if str(name).lower() in _gems:
            by_name[str(name).lower()] = rng
        else:
            unknown.append(name)
    for sk in doc.get('skills') or []:
        rng = by_name.get(_names.get(sk['id'], ''))
        if rng:
            sk['level_interval'] = [int(rng[0]), int(rng[1]) if len(rng) > 1 else 100]
    have = {x['id'] for x in lv_skills}
    doc['skills'] = lv_skills + [x for x in doc.get('skills') or [] if x['id'] not in have]
    if unknown:
        rep['unknown_gems'] = unknown


def export(con, build_id, write=True, confirm=False, level=None, name=None):
    """Make the .build from the build + its saved plan (edits, notes, level) and write it."""
    st = get(con, build_id)
    r = con.execute('SELECT label, pob_code FROM build WHERE id=?', (int(build_id),)).fetchone()
    if not r:
        raise ValueError('no such build in the vault')
    xml, warnings = apply_edits(vault.decode(r['pob_code']), st.get('edits'))
    route_on = bool(st.get('levelling_route'))   # only after Claude reviewed it (the order is a rule of thumb)
    doc, rep = buildplanner.make(con, None, vault.encode(xml), st.get('notes'), name or st.get('name') or r['label'],
                                 auto_route=route_on)
    if rep.get('slots') == 0:   # gear prices need the vault build id
        doc2, rep2 = buildplanner.make(con, build_id, None, st.get('notes'), name or st.get('name') or r['label'],
                                       auto_route=route_on)
        if st.get('edits'):
            doc2['passives'], doc2['skills'] = doc['passives'], doc['skills']
        doc, rep = doc2, dict(rep2, passives=rep['passives'], skills=rep['skills'])
    _apply_skill_plan(doc, st.get('edits') or {}, rep)
    level = level or st.get('level')
    _level_notes(doc, level, deaths(con, st['follow']) if st.get('follow') else None)
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
