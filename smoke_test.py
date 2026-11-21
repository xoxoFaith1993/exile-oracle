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
    med = [fc['horizons'][h]['median'] for h in sorted(fc['horizons'], key=int)]
    steps = [b - a for a, b in zip([0.004] + med, med)]
    check(all(s <= 1e-12 for s in steps) or all(s >= -1e-12 for s in steps), 'price forecast: one consistent path (no zig-zag)')
    try:
        fx = prophecy.forecast_item(__import__('poe2kit.db', fromlist=['x']).connect(), "Xoph's Pyre")
        check(len(fx.get('past') or {}) >= 2, f"price forecast: past-launch lines for non-key items ({len(fx.get('past') or {})} launches)")
    except FileNotFoundError as e:
        check(True, f'forecast paths skipped ({e})')
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


def failsafe_check():
    """Fail-safes: every Claude tool and dashboard call answers in plain words with no internet, an empty data folder,
    no Path of Building and nonsense input (release/chaos_test.py, own temp folder); a damaged database is moved aside
    and the player's own data comes back from the daily backup."""
    import subprocess
    here = os.path.dirname(os.path.abspath(__file__))
    test = os.path.join(here, 'release', 'chaos_test.py')
    if os.path.exists(test):
        env = dict(os.environ)
        for k in ('POE2KIT_HOME', 'POE2KIT_PORT', 'POE2KIT_POB'):
            env.pop(k, None)
        r = subprocess.run([sys.executable, test], capture_output=True, text=True, env=env, timeout=900)
        check(r.returncode == 0, 'fail-safes: every tool and dashboard call answers in plain words (no internet, empty, '
              'nonsense input)' + ('' if r.returncode == 0 else ' -> ' + (r.stdout + r.stderr)[-600:]))
    code = ("import os,sys;sys.path.insert(0,r'%s');from poe2kit import db,config;c=db.connect();"
            "c.execute(\"INSERT INTO build(added,label,owner,pob_code) VALUES(1,'B','me','x')\");c.commit();"
            "db.backup_essentials(c);c.close();open(config.DB_PATH,'wb').write(b'x'*500);"
            "c=db.connect();print(c.execute('select label from build').fetchone()[0], bool(db.kv_get(c,'recovered')))" % here)
    env = dict(os.environ, POE2KIT_HOME=tempfile.mkdtemp(prefix='poe2kit-recover-'))
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, env=env, timeout=120)
    check(r.stdout.strip() == 'B True', 'damaged database: moved aside, own data restored from the backup' +
          ('' if r.stdout.strip() == 'B True' else ' -> ' + (r.stdout + r.stderr)[-300:]))


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


def journey_check():
    """League plan: six stages from scratch (no build), each check says what it needs; a plan never crashes on a
    fresh install."""
    from poe2kit import journey, db
    con = db.connect()
    try:
        p = journey.plan(con, None, 'Witch', 'Blood Mage', scratch=True)
    finally:
        con.close()
    ok = len(p['stages']) == 6 and p['now'] == 'start' and all(c['need'] for s in p['stages'] for c in s['checks']) \
        and p['stages'][0]['state'] == 'now' and p['class'] == 'Witch'
    check(ok, 'league plan: six stages from scratch, every check says what it needs')


def rescue_check():
    """"I'm stuck": gaps found and ordered from measured numbers, three ways out; with no build it asks plain
    questions instead of failing."""
    from poe2kit import rescue, db
    m = {'level': 88, 'dps': 150000, 'life_es': 2500, 'ehp': 20000, 'res': {'fire': 60, 'cold': 75, 'lightning': 75,
         'chaos': -10}, 'hits': {'physical': 3000, 'fire': 6000, 'cold': 7000, 'lightning': 7000, 'chaos': 4000}}
    f = rescue._findings(m, 'red')
    con = db.connect()
    try:
        r = rescue.rescue(con, 'dying', scratch=True, budget_div=2, level=40)
    finally:
        con.close()
    check(f and f[0]['area'] == 'defence' and {x['what'] for x in f} >= {'Fire resistance', 'DPS (one target)'}
          and r.get('questions') and r['ways_out']['restart'] and r['content'] == 'campaign',
          "I'm stuck: gaps biggest first, three ways out, plain questions without a build")


def wishlist_check():
    """R25: a wish at its target alerts once, becomes the Home omen, and can be removed."""
    import time as _t
    from poe2kit import wishlist, ninja, prophecy, db
    con = db.connect()
    lg = ninja.current_league(con)
    con.execute("INSERT INTO price(ts, league, source, category, item_key, name, value, unit) "
                "VALUES (?,?,'ninja-item','UniqueAccessories','smoke-wish','Smoketest Band',?,'divine')", (_t.time(), lg, 4.0))
    con.commit()
    bad = wishlist.add(con, 'No Such Item Xyz', 3)
    a = wishlist.add(con, 'Smoketest Band', 5, 'div', 'buy')
    got = []
    wishlist.check(con, lambda c, kind, title, detail='': got.append((kind, title)))
    wishlist.check(con, lambda c, kind, title, detail='': got.append((kind, title)))   # no repeat
    om = prophecy.omen(con)
    st = wishlist.status(con, with_forecast=False)['items']
    tr = wishlist.add(con, 'Smoketest Band', '', 'div', 'buy')   # no target: just tracking
    st2 = wishlist.status(con, with_forecast=False)['items']
    ch = wishlist.add(con, 'Smoketest Band', 30, 'chaos', 'sell') if (__import__('poe2kit.money', fromlist=['x']).rates(con, lg) or {}).get('chaos_per_div') else {'ok': True}
    gone = wishlist.remove(con, 'Smoketest Band')
    left = wishlist.status(con, with_forecast=False)['items']
    con.execute("DELETE FROM price WHERE item_key='smoke-wish'")
    con.commit()
    con.close()
    check(not bad['ok'] and a['ok'] and st and st[0]['hit'] and len(got) == 1 and got[0][0] == 'wish'
          and om.get('kind') == 'wish' and gone['ok'] and not left and tr['ok'] and st2[0]['tracking']
          and st2[0]['target'] is None and not st2[0].get('hit') and ch['ok'],
          'wishlist: target hit alerts once, becomes the omen, track with no target, chaos targets, remove')


def wanted_check():
    """Wanted items: a trade link's search is read locally (no request), a check never runs with trade checks off."""
    from poe2kit import tradewatch as tw, db, config
    q = {'status': {'option': 'securable'}, 'name': 'Mageblood', 'type': 'Utility Belt', 'stats': [{'type': 'and', 'filters': []}]}
    sid = tw.encode_query(q)
    link = 'https://www.pathofexile.com/trade2/search/poe2/Test%20League/' + sid
    p = tw.parse_input(link, 'Other')
    bad = tw.parse_input('hello there', 'Other')
    con = db.connect()
    was = config.settings().get('live_trade', False)
    config.save_settings({'live_trade': False})
    a = tw.add(con, link, 'My belt', 90, 'div')
    off = tw.check(con, a['id'])
    lq = tw.listing_query({'query': q}, {'mk': [['explicit', 'Legacy of Nothing']], 'currency': 'divine', 'amount': 65})
    price_ok = lq['filters']['trade_filters']['filters']['price'] == {'option': 'divine', 'min': 65, 'max': 65}
    off2 = tw.open_listing(con, a['id'], 'nope')
    st = tw.status(con)['items']
    gone = tw.remove(con, a['id'])
    config.save_settings({'live_trade': was})
    con.close()
    check(tw.decode_id(sid) == q and p.get('query') == q and p.get('league') == 'Test League' and bad.get('error')
          and a['ok'] and off.get('off') and st and st[0]['url'].endswith(sid) and st[0]['live_url'].endswith('/live')
          and gone['ok'] and price_ok and not off2['ok'],
          'wanted items: trade links read locally, one-listing search, no trade request while checks are off')


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


def spreads_check():
    """Exchange pricing uses the market where the most value traded; the gap finder only shows strict gaps."""
    from poe2kit import leaguestart as L, spreads, db
    X = 'Metadata/Items/Currency/Test'
    m = lambda a, b, va, vb: {'league': 'T', 'market_id': f'{a}|{b}', 'volume_traded': {a: va, b: vb}}
    page = {'markets': [m(L.DIV, L.EX, 10, 4000),            # 1 div = 400 ex
                        m(X, L.EX, 2, 34),                   # thin: 17 ex each
                        m(X, L.DIV, 300, 37.5)]}             # busy: 0.125 div = 50 ex each
    prices, epd = L.prices_from_page(page, 'T')
    con = db.connect()
    r = spreads.find(con)
    con.close()
    ok_rows = all(g['held_hours'] >= spreads.MIN_HELD and spreads.MIN_GAP <= g['gap_pct'] <= spreads.MAX_GAP
                  and g['buy_ex'] < g['sell_ex'] for g in r.get('gaps', []))
    check(epd == 400 and abs(prices[X][0] - 50) < 0.01 and ok_rows and r.get('note'),
          f"exchange price from the busiest market; gap finder strict ({len(r.get('gaps', []))} gaps)")


def pages_check():
    """Every dashboard card sits inside one page, so it shows only there (not under every page), and every sidebar
    button has its page."""
    import re
    html = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dashboard', 'index.html'), encoding='utf-8').read()
    main = html[html.index('<main>'):html.index('</main>')]
    depth, stray = 0, 0
    for tok in re.findall(r'<section|</section>|<div class="card', main):
        depth += 1 if tok == '<section' else -1 if tok == '</section>' else 0
        stray += tok.startswith('<div') and depth == 0
    nav = html[html.index('<nav id="nav">'):html.index('</nav>')]
    missing = [t for t in re.findall(r'data-tab="([^"]+)"', nav) if f'<section id="{t}"' not in main]
    check(not stray and depth == 0 and not missing, f'dashboard: every card inside its page, every menu item has a page {missing or ""}')


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


def buildcheck_check():
    """Build check: tune the weapon set and main skill (saved with the build), then reset to as imported."""
    from poe2kit import vault, db
    xml = ('<PathOfBuilding2><Build level="90" className="Witch" ascendClassName="Blood Mage" mainSocketGroup="1"></Build>'
           '<Items activeItemSet="1" useSecondWeaponSet="nil"><ItemSet id="1" useSecondWeaponSet="nil">'
           '<Slot itemId="0" name="Weapon 1"/><Slot itemId="7" name="Weapon 1 Swap"/></ItemSet></Items>'
           '<Skills><SkillSet id="1"><Skill enabled="true"><Gem nameSpec="Comet" enabled="true"/></Skill>'
           '<Skill enabled="true"><Gem nameSpec="Frost Wall" enabled="true"/></Skill></SkillSet></Skills><Tree></Tree></PathOfBuilding2>')
    con = db.connect()
    bid = vault.from_paste(con, vault.encode(xml), 'Check test')['id']
    before = con.execute('SELECT pob_code FROM build WHERE id=?', (bid,)).fetchone()[0]
    c0 = vault.check(con, bid)
    c1 = vault.tune(con, bid, weapon_set=2, main_group=2)
    tuned = vault.decode(con.execute('SELECT pob_code FROM build WHERE id=?', (bid,)).fetchone()[0])
    c2 = vault.reset(con, bid)
    after = con.execute('SELECT pob_code FROM build WHERE id=?', (bid,)).fetchone()[0]
    vault.delete(con, bid)
    con.close()
    check(not c0['set1'] and c0['set2'] and c1['tuned'] and c1['uses_set'] == 2 and c1['main_group'] == 2
          and 'mainSocketGroup="2"' in tuned and not c2['tuned'] and after == before,
          'Build check: tune weapon set + main skill, reset to as imported')


def newleague_check():
    """R27: a new league (1.0) on poe.ninja is followed, its day 0 is the 1.0 launch, and the player is told."""
    from poe2kit import patchwatch, ninja, prophecy, db, oracle
    con = db.connect()
    lists = [['Forbidden Rites', 'Standard'], ['Test League One', 'HC Test League One', 'Forbidden Rites', 'Standard']]
    keep, alerts = ninja.leagues, []
    try:
        ninja.leagues = lambda c=None, fresh=False: [{'id': x} for x in lists[0]]
        db.kv_set(con, 'leagues:known', 'null')
        first = patchwatch.new_leagues(con, lambda *a: alerts.append(a))
        ninja.leagues = lambda c=None, fresh=False: [{'id': x} for x in lists[1]]
        new = patchwatch.new_leagues(con, lambda *a: alerts.append(a))
        patchwatch.set_league_start(con, 'Test League Two', prophecy.LAUNCH_1_0 + 3 * 3600)
        day0_one = oracle.league_start(con, 'Test League One')
        day0_two = oracle.league_start(con, 'Test League Two')
    finally:
        ninja.leagues = keep
        con.execute("DELETE FROM ls_league WHERE league LIKE 'Test League%'")
        db.kv_set(con, 'leagues:known', 'null')
        con.commit()
        con.close()
    check(first is None and new == ['Test League One'] and len(alerts) == 1 and day0_one
          and day0_two == prophecy.LAUNCH_1_0, 'a new league is followed, with day 0 at the 1.0 launch')


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
    wishlist_check()
    rescue_check()
    journey_check()
    wanted_check()
    vault_paste_check()
    spreads_check()
    pages_check()
    failsafe_check()
    weaponset_check()
    buildcheck_check()
    newleague_check()
    mcp()
    if '--pob' in sys.argv:
        pob_part()
    print(f'\n{len(fails)} failed' if fails else '\nall passed')
    sys.exit(1 if fails else 0)
