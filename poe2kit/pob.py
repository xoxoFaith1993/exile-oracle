"""Headless Path of Building: real DPS / defence numbers for any build, cached by content hash.
Windows: PoB's own LuaJIT through HOME\\tools\\poblua.exe (see pobhost\\).
Linux: LuaJIT runs the same scripts directly, with lua-utf8 and lcurl built for Linux (the app's linux\\ folder,
built by GitHub Actions; a system `luajit` works too)."""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile

from . import config, vault

POB = config.POB_DIR
HOST = os.path.join(config.TOOLS_DIR, 'poblua.exe')
LINUX_RT = os.path.join(config.ROOT, 'linux')   # bin/luajit + lib/lua-utf8.so, lib/lcurl.so
SCRIPT = os.path.join(config.ROOT, 'pobhost', 'pobrun.lua')
CACHE = os.path.join(config.DATA_DIR, 'pob-cache')


def runner():
    """(command prefix, extra environment) that runs one of our pobhost scripts, or None if nothing can."""
    if os.name == 'nt':
        return ([os.path.abspath(HOST), os.path.join(POB, 'runtime')], {}) if os.path.exists(HOST) else None
    exe = os.path.join(LINUX_RT, 'bin', 'luajit')
    exe = exe if os.access(exe, os.X_OK) else shutil.which('luajit')
    if not exe:
        return None
    lib = os.path.join(LINUX_RT, 'lib')
    env = {}
    if os.path.isdir(lib):
        env['POB_CPATH'] = os.path.join(lib, '?.so')
        env['POB_LCURL'] = os.path.join(lib, 'lcurl.so')
    return [exe], env


def ready():
    return os.path.exists(os.path.join(POB, 'manifest.xml')) and runner() is not None


def run(script, env=None, timeout=300):
    """Run a pobhost script inside PoB's src folder. Returns the CompletedProcess."""
    r = runner()
    if not r:
        raise FileNotFoundError('no Lua runtime for Path of Building (Windows: tools\\poblua.exe; Linux: linux/bin/luajit)')
    cmd, extra = r
    e = dict(os.environ, POB_RUNTIME=os.path.join(POB, 'runtime'), **extra, **(env or {}))
    e.pop('CI', None)   # PoB skips its mod cache when CI is set (its own test mode): slow and not what we want
    from . import osutil
    return subprocess.run(cmd + [script], cwd=os.path.join(POB, 'src'), env=e, capture_output=True, text=True,
                          creationflags=osutil.NO_WINDOW,
                          encoding='utf-8', errors='replace', timeout=timeout, stdin=subprocess.DEVNULL)

# The numbers people actually compare, in a sensible order (PoB mainOutput keys).
KEY_STATS = [
    ('CombinedDPS', 'DPS (combined)'), ('TotalDPS', 'DPS (main skill)'), ('Speed', 'casts/attacks per sec'),
    ('CritChance', 'crit chance %'), ('CritMultiplier', 'crit multiplier'),
    ('Life', 'life'), ('EnergyShield', 'energy shield'), ('Mana', 'mana'), ('Spirit', 'spirit'),
    ('TotalEHP', 'effective HP'), ('PhysicalMaximumHitTaken', 'max hit: physical'),
    ('FireMaximumHitTaken', 'max hit: fire'), ('ColdMaximumHitTaken', 'max hit: cold'),
    ('LightningMaximumHitTaken', 'max hit: lightning'), ('ChaosMaximumHitTaken', 'max hit: chaos'),
    ('FireResist', 'fire res'), ('ColdResist', 'cold res'), ('LightningResist', 'lightning res'),
    ('ChaosResist', 'chaos res'), ('Armour', 'armour'), ('Evasion', 'evasion'),
    ('EffectiveMovementSpeedMod', 'movement speed x'), ('LifeRegenRecovery', 'life regen /s'),
]


def version():
    try:
        with open(os.path.join(POB, 'manifest.xml'), encoding='utf-8') as f:
            head = f.read(400)
        import re
        m = re.search(r'number="([^"]+)"', head)
        return m.group(1) if m else '?'
    except OSError:
        return 'not installed'


_asc_starts = {}


def _ascendancy_start(node_id):
    """True for the start points of other ascendancies: GGG's character data lists them for everyone, Path of
    Building doesn't draw them, so they aren't really missing (found on the author's import, 2026-11-21)."""
    if 'ids' not in _asc_starts:
        ids = set()
        try:
            p = config.newest_gamefiles(os.path.join('tables', 'passiveskills.json'))
            d = json.load(open(p, encoding='utf-8')) if p else []
            for r in (d if isinstance(d, list) else d.get('rows') or []):
                if str(r.get('Id') or '').startswith('Ascendancy') and str(r.get('Id') or '').rstrip('_').endswith('Start'):
                    ids.add(str(r.get('PassiveSkillGraphId')))
        except Exception:
            pass
        _asc_starts['ids'] = ids
    return str(node_id) in _asc_starts['ids']


def filled_weapon_set(xml_text):
    """(xml, note) with the weapon set that has the weapons switched on. A character whose weapons sit only in
    weapon set II (set I empty) was measured with NO weapon: no staff damage, no "+levels to spells" (found on
    the author's Comet build, 2026-11-21). The game uses the set the weapons are in, so this does too."""
    import re as _re
    if 'name="Weapon 1 Swap"' not in xml_text:
        return xml_text, None
    def item(slot):
        m = _re.search(r'<Slot [^>]*itemId="(\d+)"[^>]*name="%s"' % _re.escape(slot), xml_text) or \
            _re.search(r'<Slot [^>]*name="%s"[^>]*itemId="(\d+)"' % _re.escape(slot), xml_text)
        return int(m.group(1)) if m else 0
    first = item('Weapon 1') or item('Weapon 2')
    second = item('Weapon 1 Swap') or item('Weapon 2 Swap')
    using_second = _re.search(r'<Items [^>]*useSecondWeaponSet="true"', xml_text) is not None
    if not first and second and not using_second:
        fixed = _re.sub(r'(<(?:Items|ItemSet) [^>]*?)useSecondWeaponSet="[^"]*"', r'\1useSecondWeaponSet="true"', xml_text)
        if fixed == xml_text:   # the attribute wasn't there: add it
            fixed = _re.sub(r'<Items ', '<Items useSecondWeaponSet="true" ', xml_text, count=1)
        return fixed, 'Fixed automatically: weapon set I is empty, so it was measured with weapon set II, where the weapons are.'
    return xml_text, None


# Auto-fixes (the author, 2026-11-21: "we need to be able to auto fix this stuff for anyone"). Each one repairs a known
# import problem before Path of Building measures a build, for every player and every build, and says what it did
# (the note shows with the build's warnings). Add new ones here as they are found; each is
# fix(xml) -> (xml, note or None), and must leave a correct build unchanged.
AUTOFIXES = [filled_weapon_set]
AUTOFIX_VERSION = 'af2'   # bump when a fix or its note changes: cached results are measured again


def autofix(xml_text):
    notes = []
    for fix in AUTOFIXES:
        try:
            xml_text, note = fix(xml_text)
        except Exception:
            note = None
        if note:
            notes.append(note)
    return xml_text, notes


def calc(xml_text, use_cache=True, timeout=300, main_group=None):
    xml_text, fixnotes = autofix(xml_text)
    with open(SCRIPT, 'rb') as f:
        script = hashlib.sha1(f.read()).hexdigest()
    key = hashlib.sha1((version() + script + str(main_group) + AUTOFIX_VERSION + xml_text).encode('utf-8')).hexdigest()
    os.makedirs(CACHE, exist_ok=True)
    cpath = os.path.join(CACHE, key + '.json')
    if use_cache and os.path.exists(cpath):
        with open(cpath, encoding='utf-8') as f:
            return json.load(f)
    tmp = tempfile.mkdtemp(prefix='pob-', dir=CACHE)  # temp on F:, never C:
    xml_path, out_path = os.path.join(tmp, 'in.xml'), os.path.join(tmp, 'out.json')
    try:
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(xml_text)
        env = dict(POB_IN=xml_path, POB_OUT=out_path, TEMP=tmp, TMP=tmp, TMPDIR=tmp)
        if main_group is not None:
            env['POB_MAIN_GROUP'] = str(int(main_group))
        p = run(SCRIPT, env, timeout)
        if p.returncode != 0 or not os.path.exists(out_path):
            tail = (p.stderr or p.stdout or '').strip().splitlines()[-6:]
            raise RuntimeError('PoB failed: ' + ' | '.join(tail))
        with open(out_path, encoding='utf-8') as f:
            res = json.load(f)
        ids = [l.split()[-1] for l in p.stdout.splitlines() if l.startswith('missing node')]
        missing = len([i for i in ids if not _ascendancy_start(i)])   # GGG lists every ascendancy's start point
        res['warnings'] = [f'{missing} passive nodes in this build no longer exist in PoB {version()} '
                           '(tree changed since the build was made)'] if missing else []
        res['warnings'] += fixnotes
        res['pob_version'] = version()
        with open(cpath, 'w', encoding='utf-8') as f:
            json.dump(res, f)
        return res
    finally:
        for fn in (xml_path, out_path):
            try:
                os.remove(fn)
            except OSError:
                pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass


def key_stats(res):
    o = res.get('output', {})
    return {label: round(o[k], 2) for k, label in KEY_STATS if k in o}


def stats_for(con, build_id=None, pob_code=None, main_group=None):
    if build_id is not None:
        r = con.execute('SELECT label, pob_code FROM build WHERE id=?', (int(build_id),)).fetchone()
        if not r:
            raise ValueError('no such build in the vault')
        label, pob_code = r['label'], r['pob_code']
    else:
        label = 'pasted build'
    res = calc(vault.decode(pob_code), main_group=main_group)
    return {'build': label, 'class': res.get('class'), 'ascendancy': res.get('ascendancy'), 'level': res.get('level'),
            'main_skill': res.get('main_skill'), 'main_skill_reason': res.get('main_group_reason'),
            'skills': [{'group': g['index'], 'skill': g['skill'], 'dps': round(g['dps'])}
                       for g in res.get('skill_groups', []) if g.get('dps', 0) > 0],
            'stats': key_stats(res), 'warnings': res.get('warnings', []), 'pob_version': res.get('pob_version')}


def compare(con, a, b):
    """a, b: dicts with build_id or pob_code. Returns both stat sets and the differences (b vs a)."""
    sa, sb = stats_for(con, **a), stats_for(con, **b)
    diff = {}
    for label, va in sa['stats'].items():
        vb = sb['stats'].get(label)
        if vb is None:
            continue
        pct = round((vb / va - 1) * 100, 1) if va else None
        diff[label] = {'a': va, 'b': vb, 'b_vs_a_pct': pct}
    return {'a': {k: sa[k] for k in ('build', 'ascendancy', 'level', 'main_skill')},
            'b': {k: sb[k] for k in ('build', 'ascendancy', 'level', 'main_skill')},
            'diff': diff, 'warnings': sa['warnings'] + sb['warnings']}


def swap_item(xml_text, slot, item_text):
    """Put item_text (in-game Ctrl+C text or PoB item text) into slot ('Helmet', 'Ring 1', 'Weapon 1', ...).
    Returns new XML. Jewel sockets aren't supported yet."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_text)
    slots = {s.get('name', '').lower(): s for s in root.iter('Slot')}
    sl = slots.get(slot.lower())
    if sl is None:
        raise ValueError(f'no slot {slot!r}; slots: ' + ', '.join(sorted(s.get('name') for s in root.iter('Slot'))))
    items = root.find('Items')
    new_id = str(max([int(i.get('id')) for i in items.iter('Item')] + [0]) + 1)
    it = ET.SubElement(items, 'Item', {'id': new_id})
    it.text = '\n' + item_text.strip().replace('\r\n', '\n') + '\n'
    for s in root.iter('Slot'):  # item sets hold their own slot lists; point every matching slot at the new item
        if s.get('name', '').lower() == slot.lower():
            s.set('itemId', new_id)
    return ET.tostring(root, encoding='unicode')


def whatif(con, build_id=None, pob_code=None, slot=None, item_text=None, main_group=None):
    """Swap one item and show what changes."""
    if build_id is not None:
        r = con.execute('SELECT label, pob_code FROM build WHERE id=?', (int(build_id),)).fetchone()
        if not r:
            raise ValueError('no such build in the vault')
        label, pob_code = r['label'], r['pob_code']
    else:
        label = 'pasted build'
    xml = vault.decode(pob_code)
    before = calc(xml, main_group=main_group)
    grp = before.get('main_group') if main_group is None else main_group
    after = calc(swap_item(xml, slot, item_text), main_group=grp)
    a, b = key_stats(before), key_stats(after)
    diff = {k: {'before': a[k], 'after': b.get(k), 'change': round(b.get(k, 0) - a[k], 2),
                'change_pct': round((b.get(k, 0) / a[k] - 1) * 100, 1) if a[k] else None}
            for k in a if b.get(k) != a[k]}
    return {'build': label, 'slot': slot, 'main_skill': after.get('main_skill'), 'changes': diff,
            'unchanged': [k for k in a if b.get(k) == a[k]], 'warnings': before.get('warnings', [])}
