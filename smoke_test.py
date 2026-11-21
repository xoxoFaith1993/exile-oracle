"""Smoke test for a fresh copy (GitHub Actions runs it on Linux and Windows; you can run it anywhere):
compile everything, check folder detection, start the monitor in a throwaway home folder, call the dashboard's
API views, ask the Claude tools server for its tool list, then stop.

    python smoke_test.py"""

import json
import os
import py_compile
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
INSTALLED = '--installed' in sys.argv   # testing an installed copy: use its real data folder
if not INSTALLED:
    os.environ.setdefault('POE2KIT_HOME', tempfile.mkdtemp(prefix='poe2kit-smoke-'))
os.environ.setdefault('POE2KIT_PORT', '47899')
sys.path.insert(0, HERE)

VIEWS = ['status', 'overview', 'alerts', 'builds', 'classes', 'claude', 'farm', 'icons', 'leagueplan', 'market',
         'movers', 'mychars', 'patches', 'playbook', 'sessions', 'top1', 'update']
fails = []


def check(ok, what):
    print(('ok   ' if ok else 'FAIL ') + what, flush=True)
    if not ok:
        fails.append(what)


def compile_all():
    n = 0
    for r, ds, fs in os.walk(HERE):
        ds[:] = [d for d in ds if d not in ('.git', '__pycache__', 'python', 'vault')]
        for f in fs:
            if f.endswith(('.py', '.pyw')):
                try:
                    py_compile.compile(os.path.join(r, f), doraise=True)
                    n += 1
                except py_compile.PyCompileError as e:
                    check(False, f'compile {f}: {e.msg}')
    check(True, f'compiled {n} files')


def detection():
    from poe2kit import config, osutil, claudelink
    want = os.environ.get('POE2KIT_HOME') or (os.path.join(os.environ.get('XDG_DATA_HOME') or
                                                           os.path.expanduser('~/.local/share'), 'poe2toolkit')
                                               if os.name != 'nt' else config.HOME)
    check(os.path.normpath(config.HOME) == os.path.normpath(want), f'home folder {config.HOME}')
    print('     game folder :', config.poe2_dir())
    print('     Client.txt  :', config.client_log())
    print('     PoB folder  :', osutil.find_documents('Path of Building (PoE2)'))
    print('     Claude      :', claudelink.status()['config'])
    check(osutil.pid_alive(os.getpid()), 'process check sees itself')


def get(url, timeout=30):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read()


def monitor(strict=False):
    import launcher
    t0 = time.time()
    launcher.main(['--background'])
    check(launcher.up(), f'monitor started ({time.time() - t0:.1f} s)')
    if not launcher.up():
        from poe2kit import config
        log = os.path.join(config.LOG_DIR, 'monitor.log')   # noqa
        if os.path.exists(log):
            print(open(log, encoding='utf-8', errors='replace').read()[-3000:])
        return
    try:
        code, body = get(launcher.URL)
        check(code == 200 and b'<html' in body.lower()[:2000], 'dashboard page')
        for v in VIEWS:
            try:
                code, body = get(launcher.URL + 'api/' + v, timeout=60)
                json.loads(body)
                check(code == 200, f'/api/{v}')
            except urllib.error.HTTPError as e:
                body = e.read()
                try:
                    j = json.loads(body)
                except ValueError:
                    j = {}
                if e.code == 503 and j.get('setup') and not strict:   # first-start downloads still running
                    check(True, f'/api/{v} (waits for {", ".join(j["waiting_for"])})')
                else:
                    check(False, f'/api/{v}: {e.code} {body[:400].decode("utf-8", "replace")}')
            except Exception as e:
                check(False, f'/api/{v}: {e}')
        overlay_check()
    finally:
        launcher.stop()
        time.sleep(1)
        check(not launcher.up(), 'monitor stopped')


# a plain Ctrl+C copy written for this test (not a real listing)
TEST_ITEM = '''Item Class: Rings
Rarity: Rare
Test Loop
Ruby Ring
--------
Requires: Level 40
--------
Item Level: 75
--------
+25% to Fire Resistance (implicit)
--------
+60 to maximum Life
+30% to Cold Resistance
12% increased Rarity of Items found
--------
Corrupted'''


def overlay_check():
    from poe2kit import itemtext
    it = itemtext.parse(TEST_ITEM)
    check(it['rarity'] == 'RARE' and it['base'] == 'Ruby Ring' and len(it['explicits']) == 3 and it['corrupted']
          and it['mods'][0]['kind'] == 'implicit', 'item text reader')
    import launcher
    code, body = get(launcher.URL + 'overlay')
    check(code == 200, 'overlay page')
    req = urllib.request.Request(launcher.URL + 'api/overlay/item', data=json.dumps({'text': TEST_ITEM}).encode(),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    urllib.request.urlopen(req, timeout=10).read()
    st = {}
    for _ in range(20):
        _, body = get(launcher.URL + 'api/overlay/latest?after=0')
        st = json.loads(body)
        if st.get('status') in ('done', 'error'):
            break
        time.sleep(0.5)
    r = st.get('result') or {}
    t = r.get('trade') or {}
    check(st.get('status') == 'done' and (r.get('item') or {}).get('base') == 'Ruby Ring',
          f"overlay price check ({st.get('status')}, trade: {t.get('state')})")
    check(t.get('state') in (None, 'off'), 'live trade stays off unless switched on')


def planner_check():
    from poe2kit import buildplanner
    ids = buildplanner._ids()
    check(ids['ascendancies'].get('Blood Mage') == 'Witch2' and len(ids['passives']) > 5000,
          f"Build Planner id map ({len(ids['passives'])} passives)")
    check(buildplanner._levels('Level 30') == 30 and buildplanner._levels('Endgame') == 100, 'Build Planner stage titles')
    from poe2kit import buildplan
    doc = {'description': 'x', 'passives': ['a', {'id': 'b', 'level_interval': [31, 100]},
                                           {'id': 'c', 'level_interval': [60, 100]}]}
    buildplan._level_notes(doc, 25)
    check('Next: from level 31' in doc['passives'][1].get('additional_text', '') and
          'additional_text' not in doc['passives'][2] and 'Level 25 now' in doc['description'],
          'living plan: level notes')


def mcp():
    p = subprocess.Popen([sys.executable, os.path.join(HERE, 'server.py')], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, text=True, encoding='utf-8')
    try:
        for m in ({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18'}},
                  {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                  {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}):
            p.stdin.write(json.dumps(m) + '\n')
        p.stdin.flush()
        tools = None
        for _ in range(5):
            line = p.stdout.readline()
            if not line:
                break
            msg = json.loads(line)
            if msg.get('id') == 2:
                tools = msg['result']['tools']
                break
        check(bool(tools), f'Claude tools server lists {len(tools or [])} tools')
    finally:
        p.kill()


MINI_BUILD = ('<PathOfBuilding2><Build level="90" className="Witch" ascendClassName="None"/><Skills/>'
              '<Items/><Config/></PathOfBuilding2>')   # an empty level-90 character, no gear or tree


def pob_part():
    """--pob: download Path of Building + game data like a first start does, then run real PoB work through
    this platform's Lua runtime and check the views that waited for it."""
    from poe2kit import bootstrap, db, gamedata, leagueplan, pob
    con = db.connect()
    t0 = time.time()
    got = bootstrap.run(con)
    check(pob.ready(), f'Path of Building set up: {got} ({time.time() - t0:.0f} s)')
    gamedata.update(max_age_days=3)
    check(True, 'game data downloaded')
    if not pob.ready():
        return
    t0 = time.time()
    try:
        r = pob.calc(MINI_BUILD, use_cache=False)
        check(r.get('level') == 90 and (r['output'].get('Life') or 0) > 0,
              f'PoB calculation: level {r.get("level")} {r.get("class")}, life {r["output"].get("Life")} '
              f'({time.time() - t0:.1f} s)')
    except Exception as e:
        check(False, f'PoB calculation: {e}')
    try:   # living plan edits on PoB's own tree: a far-away keystone must be flagged as not connected
        from poe2kit import buildplan
        xml = ('<PathOfBuilding2><Build level="90" className="Witch"/><Tree activeSpec="1"><Spec treeVersion="0_5" '
               'nodes=""/></Tree><Skills/><Items/></PathOfBuilding2>')
        new_xml, warn = buildplan.apply_edits(xml, {'add_passives': ['Ritual Cadence']})
        check('nodes=""' not in new_xml and any("isn't connected" in w for w in warn), 'living plan: edits + connection check')
    except Exception as e:
        check(False, f'living plan edits: {e}')
    try:
        cl = leagueplan.classes()
        check(any(c['name'] == 'Witch' for c in cl), f'passive tree read through PoB: {len(cl)} classes')
    except Exception as e:
        check(False, f'passive tree: {e}')
    monitor(strict=True)


if __name__ == '__main__':
    print('python', sys.version.split()[0], 'on', sys.platform, '| home', os.environ.get('POE2KIT_HOME', '(installed default)'))
    compile_all()
    detection()
    planner_check()
    monitor()
    mcp()
    if '--pob' in sys.argv:
        pob_part()
    print(f'\n{len(fails)} failed' if fails else '\nall passed')
    sys.exit(1 if fails else 0)
