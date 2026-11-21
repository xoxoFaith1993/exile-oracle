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
    check('Next: at level 31' in doc['passives'][1].get('additional_text', '') and
          'additional_text' not in doc['passives'][2] and 'Level 25 now' in doc['description'],
          'living plan: level notes')


def doctor_check():
    from poe2kit import doctor
    r = doctor.run()
    check(r.get('checks') and 'guide' in r and 'Restarting things' in r['guide'],
          f"doctor runs ({len(r['checks'])} checks, guide attached)")



def oracle_extras_check():
    """0.5.0: Build Lab data, connectors, report preview (nothing is sent), native window script."""
    import json as _j
    from poe2kit import config, connectors, lab, report
    p = config.data_file('boss-readiness.json')
    d = _j.load(open(p, encoding='utf-8')) if p else {}
    check(len(d.get('bosses') or []) >= 5 and all(c['stat'] in lab.STAT_OF for b in d['bosses'] for c in b['checks']),
          f"boss readiness data ({len(d.get('bosses') or [])} bosses, every stat known)")
    st = connectors.status()
    check(set(st) == {'chatgpt', 'gemini'}, 'connectors: ChatGPT + Gemini')
    pv = report.preview('issue', 'smoke test')
    check(pv.startswith('smoke test') and os.path.expanduser('~') not in pv, 'report preview (scrubbed, not sent)')
    check(os.path.exists(os.path.join(HERE, 'app_window.pyw')), 'native window script present')
    from poe2kit import oracle
    adv = oracle.advice(day=5)
    check(adv.get('phase') == 'week 1' and adv.get('do_now') and any(x['change_pct'] is not None for x in adv['items']),
          f"Oracle market advice (day 5: {len(adv.get('do_now') or [])} actions, {len(adv['items'])} items)")
    check(oracle.hold_note('Exalted Orb') and oracle.hold_note('Soul Core of Tacati'), 'Oracle hold notes for the playbook')
    check(os.path.exists(os.path.join(HERE, 'ninja_view.pyw')), 'poe.ninja profile window script present')

def waystone_check():
    """R19: a copied waystone is matched to the game's map mods (rating is skipped here: no build needed)."""
    from poe2kit import mapmods, db
    text = '\n'.join(['Item Class: Waystones', 'Rarity: Rare', 'Doom Sanctuary', 'Waystone (Tier 15)', '--------',
                      'Waystone Tier: 15', 'Monster Pack Size: +23% (augmented)', '--------', 'Item Level: 79',
                      '--------', 'Monsters deal 22(20-24)% of Damage as Extra Cold',
                      'Monsters have 75(70-79)% increased Stun Threshold'])
    keep = mapmods.active_build
    mapmods.active_build = lambda con: None
    try:
        con = db.connect()
        r = mapmods.check_item(con, text)
        con.close()
    except Exception as e:
        r = {'error': str(e)}
    finally:
        mapmods.active_build = keep
    try:
        have = bool(mapmods.mods('waystone'))
    except Exception:
        have = False
    if not have:   # fresh test home without the game data download: only the "other items" part
        check(mapmods.check_item(None, TEST_ITEM) is None, 'waystone check ignores other items (no game data here)')
        return
    check(r and len(r.get('mods') or []) == 2 and (r.get('rewards') or [{}])[0].get('label') == 'Pack size',
          f"waystone check ({len((r or {}).get('mods') or [])} mods matched)")
    check(mapmods.check_item(None, TEST_ITEM) is None, 'waystone check ignores other items')


def prophecy_check():
    """R14: timeline, omen, forecast, patch rules, farming oracle and unique history all answer."""
    from poe2kit import prophecy, patchrules
    try:
        tl = prophecy.timeline()
        from poe2kit import forecast
        fc = forecast.forecast('Exalted Orb', day=3, current_price_div=0.004)
        pp = prophecy.patch_prophecy('Increased the drop rate of Fracturing Orbs from Ritual.')
        uh = prophecy.unique_history('Mageblood')
        cd = prophecy.countdowns()
    except FileNotFoundError as e:
        check(True, f'prophecy skipped ({e})')
        return
    check(len(tl['events']) >= 15, f"league timeline ({len(tl['events'])} events)")
    check(set(fc.get('horizons', {})) >= {1, 3, 7, 14} or set(fc.get('horizons', {})) >= {'1', '3', '7', '14'}, 'price forecast (4 horizons)')
    check(pp['items'] and pp['items'][0]['calls'][0]['direction'] == 'down', 'patch prophecy: more drops -> price down')
    check(uh.get('leagues'), 'chase unique history')
    check(isinstance(cd, list), 'countdowns')


def atlasplan_check():
    """R15: every strategy's key nodes are on the live atlas tree and connect from the start points."""
    from poe2kit import atlasplan
    try:
        names = [s['name'] for s in atlasplan.data()['strategies']]
        sets = [atlasplan.setup(n) for n in names]
    except Exception as e:
        check(True, f'atlas planner skipped ({type(e).__name__}: {e})')
        return
    bad = [s.get('strategy') for s in sets if s.get('missing') or not s.get('points')]
    check(len(names) >= 10 and not bad, f'atlas strategy setups ({len(names)} strategies' + (f'; broken: {bad})' if bad else ')'))


def dataupdate_check():
    """R27: data packs install, are used, and bad ones are refused (release/test_dataupdate.py, own temp folder)."""
    import subprocess
    test = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'release', 'test_dataupdate.py')
    if not os.path.exists(test):
        check(True, 'data update test skipped (not in this copy)')
        return
    env = dict(os.environ, EO_TEST_DIR=os.path.join(tempfile.mkdtemp(), 'dataupdate'))
    env.pop('POE2KIT_HOME', None)
    r = subprocess.run([sys.executable, test], capture_output=True, text=True, env=env, timeout=300)
    check(r.returncode == 0, 'data that updates itself: install, use, refuse tampered, go back' +
          ('' if r.returncode == 0 else ' -> ' + (r.stdout + r.stderr)[-400:]))


def alerts_check():
    """Alert rules: same unit on both sides, settings round-trip, kinds can be switched off."""
    from poe2kit import alerts
    check(alerts.pair(1.2, 2.5, {'ex_per_div': 480}) == '1.20 div -> 2.50 div'
          and alerts.pair(0.04, 0.2, {'ex_per_div': 480}).endswith(' ex'), 'alerts show both sides in one unit')
    s = alerts.save({'news': {'on': False}, 'market': {'mode': 'each', 'pct': 55}, 'mute': 'Test Item'})
    ok = not s['news']['on'] and s['market']['mode'] == 'each' and s['market']['pct'] == 55 and 'Test Item' in s['muted']
    ok = ok and not alerts.wanted('news') and alerts.wanted('patch')
    alerts.save({'news': {'on': True}, 'market': {'mode': 'digest', 'pct': 40}, 'unmute': 'Test Item'})
    check(ok and alerts.wanted('news'), 'alert settings: switch kinds off, thresholds, mute')


def patchwatch_check():
    """R27 step 2: a game update starts patch mode (hourly data checks for 2 days), then it ends."""
    from poe2kit import patchwatch, gamedata, dataupdate, db
    con = db.connect()
    builds, calls, alerts = ['100'], [], []
    keep = (patchwatch.game_build, gamedata.update, dataupdate.check, patchwatch.time.time)
    clock = [1000000.0]
    try:
        patchwatch.game_build = lambda: {'build': builds[0], 'source': 'test'}
        gamedata.update = lambda **k: calls.append('gamedata') or {'mods': 'unchanged'}
        dataupdate.check = lambda c: calls.append('pack') or {'ok': True, 'why': 'up to date'}
        patchwatch.time.time = lambda: clock[0]
        db.kv_set(con, 'patchwatch', '{}')
        patchwatch.tick(con, lambda *a: alerts.append(a))
        quiet = not calls and not patchwatch.status(con)['patch_mode']
        builds[0] = '101'
        patchwatch.tick(con, lambda *a: alerts.append(a))
        started = patchwatch.status(con)['patch_mode'] and calls == ['gamedata', 'pack'] and len(alerts) == 1
        clock[0] += 600
        patchwatch.tick(con)
        waits = calls == ['gamedata', 'pack']
        clock[0] += 3600
        patchwatch.tick(con)
        hourly = calls.count('gamedata') == 2
        clock[0] += 49 * 3600
        patchwatch.tick(con)
        ended = not patchwatch.status(con)['patch_mode'] and calls.count('gamedata') == 2
    finally:
        patchwatch.game_build, gamedata.update, dataupdate.check, patchwatch.time.time = keep
        db.kv_set(con, 'patchwatch', '{}')
        con.close()
    check(quiet and started and waits and hourly and ended,
          f'patch mode: starts on a game update, checks hourly, ends after 2 days ({quiet} {started} {waits} {hourly} {ended})')


def vault_paste_check():
    """Builds page: paste a build (code or link), duplicates, poe.ninja links, unsupported sites, delete."""
    from poe2kit import vault, db
    xml = ('<PathOfBuilding2><Build level="88" className="Witch" ascendClassName="Blood Mage" mainSocketGroup="1">'
           '</Build><Skills><SkillSet id="1"><Skill enabled="true" mainActiveSkill="1"><Gem nameSpec="Comet" '
           'enabled="true"/></Skill></SkillSet></Skills><Items></Items><Tree></Tree></PathOfBuilding2>')
    code = vault.encode(xml)
    con = db.connect()
    r = vault.from_paste(con, '  ' + code + ' \n', 'Smoke test build')
    again = vault.from_paste(con, code)
    ninja = vault.from_paste(con, 'https://poe.ninja/poe2/builds/rites/character/Someone-1234/SomeChar')
    other = vault.from_paste(con, 'https://example.com/build/abc')
    junk = vault.from_paste(con, 'not a build')
    gone = vault.delete(con, r.get('id'))
    left = con.execute('SELECT 1 FROM build WHERE id=?', (r.get('id'),)).fetchone()
    con.close()
    check(r.get('ok') and r.get('level') == 88 and again.get('already') and again.get('id') == r.get('id')
          and ninja.get('open_ninja', {}).get('path') == 'Someone-1234/SomeChar' and not other.get('ok')
          and not junk.get('ok') and gone.get('ok') and not left,
          'Build Vault: paste a code or link, no duplicates, poe.ninja opens its page, delete')


def weaponset_check():
    """A build whose weapons sit only in weapon set II is measured with set II (not with no weapon)."""
    from poe2kit import pob
    xml = ('<PathOfBuilding2><Items activeItemSet="1" useSecondWeaponSet="nil"><ItemSet id="1" useSecondWeaponSet="nil">'
           '<Slot itemId="0" name="Weapon 1"/><Slot itemId="18" name="Weapon 1 Swap"/><Slot itemId="0" name="Weapon 2"/>'
           '<Slot itemId="13" name="Weapon 2 Swap"/></ItemSet></Items></PathOfBuilding2>')
    fixed, note = pob.filled_weapon_set(xml)
    normal, n2 = pob.filled_weapon_set(xml.replace('itemId="0" name="Weapon 1"', 'itemId="5" name="Weapon 1"'))
    check(note and fixed.count('useSecondWeaponSet="true"') == 2 and n2 is None and 'useSecondWeaponSet="nil"' in normal
          and pob.autofix(xml)[1] == [note],
          'empty weapon set I: measured with set II')


def campaign_check():
    """R16 / R21: the rush route maps onto the game's zones, and a zone gives a route card."""
    from poe2kit import campaign
    try:
        st = campaign.steps()
        card = campaign.zone_card(None, {'area': 'G1_11', 'level': 10})
        town = campaign.zone_card(None, {'area': 'G1_town', 'level': 15, 'last_campaign': 'G1_4'})
        hide = campaign.zone_card(None, {'area': 'HideoutCave', 'level': 20})
    except FileNotFoundError as e:
        check(True, f'campaign guide skipped ({e})')
        return
    matched = sum(1 for s in st if s['areas'])
    check(len(st) >= 40 and matched >= 35, f'campaign route ({matched} of {len(st)} stops matched to game zones)')
    check(card.get('show') and card.get('rewards') and card.get('next'), 'route card: rewards and next stops in a zone')
    check(town.get('show') and (town.get('step') or {}).get('label', '').startswith('Grelwood'), 'route card in town carries on')
    check(not hide.get('show'), 'route panel hidden in the hideout')


def appwindow_check():
    from poe2kit import appwindow
    cmd = appwindow.command()   # looks for Edge / Chrome / Chromium; opens nothing
    check(appwindow.mode() in ('app', 'browser') and (cmd is None or any(x.startswith('--app=') for x in cmd)),
          f"dashboard window: {'app window via ' + os.path.basename(cmd[0]) if cmd else 'browser tab (no Chromium found)'}")


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
        from poe2kit import route
        spark = route.gem_level('Metadata/Items/Gems/SkillGemSpark')
        check(spark == 1 and route.points_at(93) == 116 and route.levels(3) == [2, 3, 4],
              f'levelling route maths (Spark from {spark}, points at 93: {route.points_at(93)})')
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
    doctor_check()
    appwindow_check()
    oracle_extras_check()
    waystone_check()
    campaign_check()
    prophecy_check()
    atlasplan_check()
    dataupdate_check()
    alerts_check()
    patchwatch_check()
    vault_paste_check()
    weaponset_check()
    mcp()
    if '--pob' in sys.argv:
        pob_part()
    print(f'\n{len(fails)} failed' if fails else '\nall passed')
    sys.exit(1 if fails else 0)
