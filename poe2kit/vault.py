"""Build Vault: decode Path of Building (PoE 2) codes and keep every build forever."""

import base64
import hashlib
import time
import json
import os
import re
import xml.etree.ElementTree as ET
import zlib

from . import config, db


def decode(code):
    code = code.strip()
    raw = base64.urlsafe_b64decode(code + '=' * (-len(code) % 4))
    return zlib.decompress(raw).decode('utf-8')


def summarize(xml_text):
    root = ET.fromstring(xml_text)
    b = root.find('Build')
    stats = {s.get('stat'): _num(s.get('value')) for s in b.findall('PlayerStat')} if b is not None else {}
    main_skill = None
    skills = root.find('Skills')
    if skills is not None and b is not None:
        groups = [g for ss in skills.findall('SkillSet') for g in ss.findall('Skill')] or skills.findall('Skill')
        try:
            g = groups[int(b.get('mainSocketGroup', '1')) - 1]
            gem = g.find('Gem')
            main_skill = g.get('label') or (gem.get('nameSpec') if gem is not None else None)
        except (IndexError, ValueError):
            pass
    items = []
    it = root.find('Items')
    if it is not None:
        for item in it.findall('Item'):
            lines = [l.strip() for l in (item.text or '').splitlines() if l.strip()]
            if lines and lines[0].startswith('Rarity:'):
                items.append({'rarity': lines[0].split(':', 1)[1].strip(),
                              'name': lines[1] if len(lines) > 1 else '',
                              'base': lines[2] if len(lines) > 2 and not lines[2].startswith(('Unique ID', 'Item Level')) else ''})
    return {
        'class': b.get('className') if b is not None else None,
        'ascendancy': b.get('ascendClassName') if b is not None else None,
        'level': int(b.get('level', 0)) if b is not None else None,
        'main_skill': main_skill,
        'stats': stats,
        'items': items,
    }


def _num(v):
    try:
        f = float(v)
        return int(f) if f.is_integer() else round(f, 3)
    except (TypeError, ValueError):
        return v


def add(con, code, label, owner='me', league=None, source_url=None, notes=None):
    s = summarize(decode(code))
    cur = con.execute(
        'INSERT INTO build(added, label, owner, league, class, ascendancy, level, main_skill, stats_json, pob_code, '
        'source_url, notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
        (db.now(), label, owner, league, s['class'], s['ascendancy'], s['level'], s['main_skill'],
         json.dumps(s['stats']), code.strip(), source_url, notes))
    con.commit()
    return cur.lastrowid, s


def import_folder(con):
    """Import any vault/<league>/<name>.pob.txt files not yet in the database."""
    added = []
    for league_dir in sorted(os.listdir(config.VAULT_DIR)) if os.path.isdir(config.VAULT_DIR) else []:
        p = os.path.join(config.VAULT_DIR, league_dir)
        if not os.path.isdir(p):
            continue
        for fn in sorted(os.listdir(p)):
            if not fn.endswith('.pob.txt'):
                continue
            code = open(os.path.join(p, fn), encoding='utf-8').read().strip()
            if con.execute('SELECT 1 FROM build WHERE pob_code=?', (code,)).fetchone():
                continue
            league = re.sub(r' (Of|The|And) ', lambda m: m.group(0).lower(), league_dir.replace('-', ' ').title())
            bid, _ = add(con, code, fn[:-8], league=league, notes=f'imported from vault/{league_dir}/{fn}')
            added.append((bid, fn))
    return added


from . import osutil  # noqa: E402
POB_BUILDS = os.path.join(osutil.find_documents('Path of Building (PoE2)'), 'Builds')


def encode(xml_text):
    """Build XML -> Path of Building share code (zlib + url-safe base64), same format PoB uses."""
    return base64.urlsafe_b64encode(zlib.compress(xml_text.encode('utf-8'), 9)).decode('ascii')


def sync_pob_builds(con, folder=POB_BUILDS):
    """Snapshot every build the author saves in Path of Building (PoE 2) into the vault.
    A new snapshot is stored only when a file's content changes, so re-importing a character in PoB
    (with PoB's own GGG login) and saving gives a dated history of it. Read-only on PoB's folder."""
    added = []
    if not os.path.isdir(folder):
        return added
    for root, _, files in os.walk(folder):
        for fn in sorted(files):
            if not fn.lower().endswith('.xml'):
                continue
            p = os.path.join(root, fn)
            try:
                with open(p, encoding='utf-8') as f:
                    xml_text = f.read()
                ET.fromstring(xml_text)  # skip half-written files
            except (OSError, ET.ParseError, UnicodeDecodeError):
                continue
            digest = hashlib.sha1(xml_text.encode('utf-8')).hexdigest()
            key = f'pobfile:{digest}'
            if db.kv_get(con, key):
                continue
            rel = os.path.relpath(p, folder)
            label = os.path.splitext(rel)[0].replace(os.sep, ' / ')
            when = time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(p)))
            bid, s = add(con, encode(xml_text), label, owner='me', source_url=p,
                         notes=f'from Path of Building (PoE2) builds folder, saved {when}')
            db.kv_set(con, key, bid)
            added.append({'id': bid, 'file': rel, 'ascendancy': s['ascendancy'], 'level': s['level']})
    return added


def listing(con, owner=None, ascendancy=None):
    q, args = 'SELECT id, added, label, owner, league, class, ascendancy, level, main_skill FROM build WHERE 1=1', []
    if owner:
        q += ' AND owner=?'; args.append(owner)
    if ascendancy:
        q += ' AND ascendancy LIKE ?'; args.append(f'%{ascendancy}%')
    return con.execute(q + ' ORDER BY added DESC', args).fetchall()


def get(con, build_id):
    r = con.execute('SELECT * FROM build WHERE id=?', (build_id,)).fetchone()
    if not r:
        return None
    s = summarize(decode(r['pob_code']))
    return dict(r) | {'summary': s}


# ---------------- paste a build / delete one (the author, 2026-11-21) ----------------

PASTE_SITES = {   # build-sharing sites with a plain-text Path of Building code page
    'pobb.in': lambda path: f'https://pobb.in/{path}/raw',
    'pastebin.com': lambda path: f'https://pastebin.com/raw/{path.split("/")[-1]}',
}


def _fetch_code(url):
    import urllib.parse
    import urllib.request
    u = urllib.parse.urlparse(url.strip())
    host = (u.hostname or '').lower().removeprefix('www.')
    path = u.path.strip('/')
    if u.scheme not in ('http', 'https') or host not in PASTE_SITES or not re.fullmatch(r'(raw/)?[A-Za-z0-9_-]{3,40}', path):
        return None
    path = path.removeprefix('raw/')
    req = urllib.request.Request(PASTE_SITES[host](path), headers={'User-Agent': config.user_agent()})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read(2_000_000).decode('utf-8', errors='replace').strip()


def from_paste(con, text, label=None, mine=False):
    """Pasted text -> a vault build. Accepts a Path of Building code, or a link to it on pobb.in / pastebin.
    A poe.ninja character link opens that character's page in Exile Oracle's own window (with its "Save this build"
    button: the one page the player asked for, no poe.ninja builds API). Returns {'ok', 'id' | 'open_ninja' | 'why'}."""
    text = (text or '').strip()
    if not text:
        return {'ok': False, 'why': 'Paste a Path of Building code or a build link first.'}
    m = re.match(r'https?://(?:www\.)?poe\.ninja/poe2/builds/([a-z0-9]+)/character/([^/?#\s]+)/([^/?#\s]+)', text)
    if m:
        return {'ok': True, 'open_ninja': {'slug': m.group(1), 'path': f'{m.group(2)}/{m.group(3)}'}}
    source = None
    if text.lower().startswith(('http://', 'https://')):
        try:
            code = _fetch_code(text)
        except Exception as e:
            return {'ok': False, 'why': f'Could not read that link ({e}).'}
        if code is None:
            return {'ok': False, 'why': 'That site isn\'t supported. Paste the Path of Building code itself (in Path of '
                                       'Building: Import/Export → Generate → Copy), or a pobb.in / pastebin / poe.ninja link.'}
        source, text = text, code
    code = re.sub(r'\s+', '', text)
    try:
        s = summarize(decode(code))
    except Exception:
        return {'ok': False, 'why': 'That isn\'t a Path of Building code (it should be one long line of letters and numbers).'}
    old = con.execute('SELECT id FROM build WHERE pob_code=?', (code,)).fetchone()
    if old:
        return {'ok': True, 'id': old['id'], 'already': True}
    name = (label or '').strip()[:80] or f"{s.get('ascendancy') or s.get('class') or 'Build'} · {s.get('main_skill') or '?'} (pasted)"
    bid, s = add(con, code, name, owner='me' if mine else 'pasted', source_url=source,
                 notes='pasted on the Builds page' + (f' from {source}' if source else ''))
    return {'ok': True, 'id': bid, 'label': name, 'ascendancy': s.get('ascendancy'), 'level': s.get('level'),
            'main_skill': s.get('main_skill')}


def delete(con, build_id):
    """Remove a build from the vault and what was kept for it (Build Lab cards / curves, its in-game plan). The
    in-game Build Planner file the game reads is left alone (that's in the game's own folder)."""
    bid = int(build_id)
    row = con.execute('SELECT label FROM build WHERE id=?', (bid,)).fetchone()
    if not row:
        return {'ok': False, 'why': 'No such build.'}
    con.execute('DELETE FROM build WHERE id=?', (bid,))
    for k in (f'lab:cards:{bid}', f'planner:{bid}', f'tune:{bid}', f'tune:orig:{bid}'):
        con.execute('DELETE FROM kv WHERE k=?', (k,))
    con.execute('DELETE FROM kv WHERE k LIKE ?', (f'lab:curves:{bid}:%',))
    con.commit()
    s = config.settings()
    if str(s.get('active_build') or '') == str(bid):
        config.save_settings({'active_build': None})
    return {'ok': True, 'deleted': bid, 'label': row['label']}


# ---------------- build check: how a build is measured, and fixing it (the author, 2026-11-21) ----------------

def check(con, build_id):
    """What Path of Building is told about this build: weapon sets, which one is used, the main skill, and whether it
    was tuned. (The measured numbers and warnings come from the Character page itself.)"""
    r = con.execute('SELECT pob_code FROM build WHERE id=?', (int(build_id),)).fetchone()
    if not r:
        return {'ok': False, 'why': 'No such build.'}
    xml = decode(r['pob_code'])

    def item(slot):
        m = re.search(r'<Slot [^>]*itemId="(\d+)"[^>]*name="%s"' % re.escape(slot), xml)
        return bool(m and m.group(1) != '0')
    root = ET.fromstring(xml)
    b = root.find('Build')
    items = root.find('Items')
    use2 = (items.get('useSecondWeaponSet') if items is not None else None) == 'true'
    orig = db.kv_get(con, f'tune:orig:{int(build_id)}')
    return {'ok': True, 'set1': item('Weapon 1') or item('Weapon 2'), 'set2': item('Weapon 1 Swap') or item('Weapon 2 Swap'),
            'uses_set': 2 if use2 else 1, 'main_group': int(b.get('mainSocketGroup') or 1) if b is not None else 1,
            'tuned': bool(orig), 'tune': json.loads(db.kv_get(con, f'tune:{int(build_id)}') or '{}')}


def tune(con, build_id, weapon_set=None, main_group=None):
    """Change how a build is measured: weapon set 1 / 2 (None = leave it to the auto-fixes) and the main skill group.
    The build as it was imported is kept, so reset() brings it back."""
    bid = int(build_id)
    r = con.execute('SELECT pob_code FROM build WHERE id=?', (bid,)).fetchone()
    if not r:
        return {'ok': False, 'why': 'No such build.'}
    if not db.kv_get(con, f'tune:orig:{bid}'):
        db.kv_set(con, f'tune:orig:{bid}', r['pob_code'])
    xml = decode(db.kv_get(con, f'tune:orig:{bid}'))
    cur = json.loads(db.kv_get(con, f'tune:{bid}') or '{}')
    if weapon_set is not None:
        cur['weapon_set'] = int(weapon_set) if int(weapon_set) in (1, 2) else None
    if main_group is not None:
        cur['main_group'] = int(main_group) if int(main_group) > 0 else None
    ws, mg = cur.get('weapon_set'), cur.get('main_group')
    if ws:
        val = 'true' if ws == 2 else 'nil'
        xml = re.sub(r'(<(?:Items|ItemSet) [^>]*?)useSecondWeaponSet="[^"]*"', r'\1useSecondWeaponSet="%s"' % val, xml)
        if 'useSecondWeaponSet=' not in xml:
            xml = xml.replace('<Items ', f'<Items useSecondWeaponSet="{val}" ', 1)
    if mg:
        xml = re.sub(r'(<Build [^>]*?)mainSocketGroup="\d+"', r'\g<1>mainSocketGroup="%d"' % mg, xml, count=1)
    code = encode(xml)
    s = summarize(xml)
    con.execute('UPDATE build SET pob_code=?, main_skill=? WHERE id=?', (code, s.get('main_skill'), bid))
    db.kv_set(con, f'tune:{bid}', json.dumps(cur))
    con.commit()
    return dict(check(con, bid), main_skill=s.get('main_skill'))


def reset(con, build_id):
    """Back to the build exactly as it was imported."""
    bid = int(build_id)
    orig = db.kv_get(con, f'tune:orig:{bid}')
    if not orig:
        return check(con, bid)
    s = summarize(decode(orig))
    con.execute('UPDATE build SET pob_code=?, main_skill=? WHERE id=?', (orig, s.get('main_skill'), bid))
    con.execute('DELETE FROM kv WHERE k IN (?, ?)', (f'tune:orig:{bid}', f'tune:{bid}'))
    con.commit()
    return check(con, bid)
