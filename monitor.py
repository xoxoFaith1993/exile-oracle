"""Exile Oracle live monitor + dashboard server (one light background process).

    python monitor.py            run forever: jobs on a schedule + dashboard at http://127.0.0.1:47830
    python monitor.py --once     run every job once and exit (for testing)

Jobs (all documented/public sources, polite intervals, cached):
  prices      poe.ninja economy snapshot (PoE 2 data refreshes ~hourly)         every 30 min
  exchange    GGG's public Currency Exchange hourly history                      every 60 min
  news        Steam News API for PoE 2 (GGG announcements, patch notes)          every 20 min
  alerts      price moves on items in your builds + big market movers            after each price pull
  install     is the PoE 2 install finished? (then: run launch_sweep.py)         every 10 min
  gamedata    community RePoE export, re-downloaded when older than 3 days        every 12 h
  pob         git pull Path of Building (so 1.0's tree lands the day PoB ships)  every 12 h
  ggg_apps    has GGG reopened app registration? (developer docs page)          every 7 days
  clientlog   new lines in the game's own Client.txt (zones, deaths, level-ups)   every 1 min
Single instance (lock file); logs to F:\\PoE2Toolkit\\logs\\monitor.log."""

import datetime
import http.server
import json
import logging
import logging.handlers
import os
import re
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from poe2kit import config, db, gamedata, ggg_exchange, money, net, ninja  # noqa: E402

PORT = int(os.environ.get("POE2KIT_PORT", "47830"))
LOG_DIR = config.LOG_DIR
LOCK = config.LOCK_PATH
IMG_DIR = config.IMG_DIR
# saved news posts: next to the code for the author's copy (existing folder), else with the user's data
PATCH_WATCH = os.path.join(HERE, 'patch-watch', 'steam') if os.path.isdir(os.path.join(HERE, 'patch-watch')) \
    else os.path.join(config.HOME, 'patch-watch', 'steam')
STEAM_NEWS = 'https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=2694490&count=15&format=json'
NEWS_WORDS = ['patch notes', 'hotfix', '1.0', 'league']   # plus the player's own watch words (config.profile)
JOBS = {'prices': 30, 'exchange': 60, 'news': 20, 'install': 10, 'gamedata': 720, 'pob': 720, 'ggg_apps': 10080,
        'mybuilds': 2, 'clientlog': 1, 'update': 720, 'dataupdate': 360, 'patchwatch': 10}

log = logging.getLogger('monitor')


def setup_log():
    os.makedirs(LOG_DIR, exist_ok=True)
    h = logging.handlers.RotatingFileHandler(os.path.join(LOG_DIR, 'monitor.log'), maxBytes=2_000_000, backupCount=3,
                                             encoding='utf-8')
    h.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    log.addHandler(h)
    log.addHandler(logging.StreamHandler())
    log.setLevel(logging.INFO)


def alert(con, kind, title, detail=''):
    try:   # the player picks which kinds of alert they want (Settings → Alerts)
        from poe2kit import alerts as _al
        if not _al.wanted(kind):
            return
    except Exception:
        pass
    recent = con.execute('SELECT 1 FROM alert WHERE title=? AND ts>?', (title, time.time() - 12 * 3600)).fetchone()
    if recent:
        return
    con.execute('INSERT INTO alert(ts, kind, title, detail) VALUES(?,?,?,?)', (time.time(), kind, title, detail))
    con.commit()
    log.info('ALERT [%s] %s', kind, title)


# ---------------- jobs ----------------

def job_prices(con):
    out = ninja.snapshot(con)
    changed = sum(v for v in out.values() if isinstance(v, int))
    job_alerts(con)
    try:   # keep the barometer uniques' daily log going even when nobody opens the Economy page
        from poe2kit import overview
        overview.overview(con)
        overview.log_uniques(con)   # the league's unique price history, one row per unique per day
    except Exception:
        pass
    return f'{changed} price rows stored' if changed else 'no new data (poe.ninja not updated yet)'


def _my_item_names(con):
    names = set()
    try:
        from poe2kit import vault
        for r in con.execute("SELECT pob_code FROM build WHERE owner='me'"):
            for it in vault.summarize(vault.decode(r['pob_code']))['items']:
                if it['rarity'] == 'UNIQUE':
                    names.add(it['name'].lower())
    except Exception:
        log.warning('could not read vault items: %s', traceback.format_exc(limit=1))
    for w in json.loads(db.kv_get(con, 'watchlist', '[]') or '[]'):
        names.add(w.lower())
    return names


def job_alerts(con):
    """Price alerts by the player's rules (poe2kit/alerts.py): their items, real market moves (or a daily digest),
    and the Oracle's calls."""
    from poe2kit import alerts as _al
    league = ninja.current_league(con)
    rt = money.rates(con, league)
    _al.run(con, alert, league, rt, _my_item_names(con))
    _al.oracle_run(con, alert)


def job_exchange(con):
    import time as _t
    from poe2kit import market
    cur = int(db.kv_get(con, 'ggg_exchange_cursor', '0') or 0)
    behind_h = (_t.time() - cur) / 3600 if cur else 0
    # catching up: up to a week of hours per run (one page a second, cached forever); live: the normal 48
    pages, stored, live = ggg_exchange.sync(con, max_pages=168 if behind_h > 48 else 48)
    derived = market.derive(con)
    return f'{pages} hours fetched, {stored} markets, {derived} hours priced' + (' (up to date)' if live else '')


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={'User-Agent': config.user_agent()})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')


def job_news(con):
    d = json.loads(_get(STEAM_NEWS))
    seen = set(json.loads(db.kv_get(con, 'news_seen', '[]') or '[]'))
    first_run = not seen
    new = 0
    os.makedirs(PATCH_WATCH, exist_ok=True)
    for it in d.get('appnews', {}).get('newsitems', []):
        gid = it['gid']
        if gid in seen:
            continue
        seen.add(gid)
        new += 1
        when = datetime.datetime.fromtimestamp(it['date'])
        safe = re.sub(r'[^A-Za-z0-9]+', '-', it['title']).strip('-')[:70]
        path = os.path.join(PATCH_WATCH, f"{when:%Y-%m-%d}-{safe}.md")
        body = re.sub(r'\[/?[a-z0-9*]+[^\]]*\]', '', it.get('contents', ''))  # strip Steam BBCode tags
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"# {it['title']}\n\n{when:%Y-%m-%d %H:%M} · {it.get('feedlabel', '')} · {it.get('url', '')}\n\n{body}\n")
        if first_run:
            continue  # don't alert on the backlog the first time
        text = (it['title'] + ' ' + body).lower()
        hits = [w for w in NEWS_WORDS + config.watch_words() if w in text]
        official = it.get('feedname') == 'steam_community_announcements'
        if official or hits:
            alert(con, 'news', f"News: {it['title']}",
                  ('mentions: ' + ', '.join(hits) + ' · ' if hits else '') + f'saved to patch-watch/steam/{os.path.basename(path)}')
    db.kv_set(con, 'news_seen', json.dumps(sorted(seen)))
    try:  # new patch notes / hotfixes -> analyse against the author's builds
        from poe2kit import patchnotes
        for pn in patchnotes.sync(con, 20):
            if not first_run:
                alert(con, 'patch', f"{pn['title']}: {pn['for_you']} change(s) hit your builds",
                      f"{pn['watch']} more lines on your watch list. Open the Patch notes tab.")
    except Exception as e:
        log.warning('patch notes analysis failed: %s', e)
    return f'{new} new posts' + (' (first run: saved, no alerts)' if first_run and new else '')


def install_state():
    acf = config.steam_manifest()
    try:
        s = open(acf or '', encoding='utf-8').read()
    except OSError:
        return {'state': 'not installed'}
    st = int((re.search(r'"StateFlags"\s+"(\d+)"', s) or [0, 0])[1])
    got = int((re.search(r'"BytesDownloaded"\s+"(\d+)"', s) or [0, 0])[1])
    tot = int((re.search(r'"BytesToDownload"\s+"(\d+)"', s) or [0, 0])[1])
    bid = (re.search(r'"buildid"\s+"(\d+)"', s) or [0, '?'])[1]
    return {'state': 'installed' if st == 4 else 'downloading/updating', 'steam_flags': st, 'build': bid,
            'downloaded_gb': round(got / 1e9, 1), 'total_gb': round(tot / 1e9, 1)}


def job_install(con):
    st = install_state()
    was = db.kv_get(con, 'install_state')
    db.kv_set(con, 'install_state', st['state'])
    if st['state'] == 'installed' and was != 'installed':
        alert(con, 'install', 'PoE 2 is installed: ready for the game-file sweep',
              'Close the game, then ask the Oracle to run launch_sweep.py (or run it yourself).')
    return json.dumps(st)


def setting_up():
    """What a fresh install is still waiting for (empty once ready)."""
    from poe2kit import pob
    wait = []
    if not os.path.exists(os.path.join(config.DATA_DIR, 'repoe', 'base_items.min.json')):
        wait.append('game data')
    if not pob.ready():
        wait.append('Path of Building')
    return wait


def job_gamedata(con):
    return json.dumps(gamedata.update(max_age_days=3))


def job_pob(con):
    from poe2kit import bootstrap
    if not os.path.isdir(os.path.join(config.POB_DIR, '.git')):
        # fresh install: no git checkout; make sure PoB + the launcher are in place (downloads once)
        return 'bootstrap: ' + ', '.join(f'{k} {v}' for k, v in bootstrap.run(con).items())
    bootstrap.ensure_poblua(con)
    from poe2kit import osutil
    p = subprocess.run(['git', '-C', config.POB_DIR, 'pull', '--ff-only', '--depth', '1'],
                       capture_output=True, text=True, timeout=600, creationflags=osutil.NO_WINDOW)
    out = (p.stdout + p.stderr).strip().splitlines()
    msg = out[-1] if out else 'no output'
    if p.returncode == 0 and 'Already up to date' not in msg:
        alert(con, 'pob', 'Path of Building updated', msg)
    return msg


def job_ggg_apps(con):
    page = _get('https://www.pathofexile.com/developer/docs')
    closed = 'unable to process new applications' in page
    if not closed and 'Registering your Application' in page:
        alert(con, 'ggg', 'GGG may have reopened API app registration', 'Check pathofexile.com/developer/docs')
    return 'registration closed' if closed else 'page changed: check it'


def job_mybuilds(con):
    """Snapshot builds the author saves in Path of Building (PoE 2), e.g. after re-importing his character there."""
    from poe2kit import vault
    added = vault.sync_pob_builds(con)
    for a in added:
        alert(con, 'build', f"Saved your build: {a['file']} ({a['ascendancy']} level {a['level']})",
              f"Vault build #{a['id']}. Open it on the Builds tab.")
    return f'{len(added)} new snapshot(s)' if added else 'no changes'


def job_clientlog(con):
    from poe2kit import clientlog
    if not clientlog.log_path():
        return 'no Client.txt yet (play once after installing)'
    since = float(db.kv_get(con, 'planner_levelup_ts', '0') or 0)
    n = clientlog.sync(con)
    msg = f'{n} new log events'
    if n:   # B2: a followed character levelled up -> rewrite its in-game Build Planner file (the game reloads it)
        from poe2kit import buildplan
        last = con.execute("SELECT MAX(ts) FROM log_event WHERE kind='levelup'").fetchone()[0] or since
        try:
            done = buildplan.on_levelups(con, since)
            if done:
                msg += '; plan updated: ' + ', '.join(done)
        except Exception as e:
            msg += f'; plan update failed: {e}'
        db.kv_set(con, 'planner_levelup_ts', str(last))
    return msg


def job_update(con):
    from poe2kit import updates
    info = updates.check(con)
    if info.get('available'):
        alert(con, 'update', f"Update available: Exile Oracle {info['latest']}", 'Open the dashboard to install it.')
    return 'development copy (no updates)' if info.get('why') else f"latest {info.get('latest')}, you have {info.get('current')}"


def job_dataupdate(con):
    """R27: a newer data pack (no new app needed) is checked, verified and switched to by itself."""
    from poe2kit import dataupdate
    r = dataupdate.check(con)
    if r.get('installed'):
        alert(con, 'update', f"Game data updated to {r['installed']}", 'New data is in use: nothing to install.')
        return f"installed data {r['installed']}"
    return r.get('why') or ('up to date' if r.get('ok') else 'failed')


def job_patchwatch(con):
    """R27: notice a game update and look for new game data every hour for 2 days after it."""
    from poe2kit import patchwatch
    return patchwatch.tick(con, alert)


JOB_FUNCS = {'prices': job_prices, 'exchange': job_exchange, 'news': job_news, 'install': job_install,
             'gamedata': job_gamedata, 'pob': job_pob, 'ggg_apps': job_ggg_apps, 'mybuilds': job_mybuilds,
             'clientlog': job_clientlog, 'update': job_update, 'dataupdate': job_dataupdate,
             'patchwatch': job_patchwatch}


def run_job(con, name):
    t0 = time.time()
    try:
        res, ok = JOB_FUNCS[name](con), True
    except Exception as e:
        res, ok = f'{type(e).__name__}: {e}', False
        log.warning('job %s failed: %s', name, res)
    st = json.loads(db.kv_get(con, 'monitor_jobs', '{}') or '{}')
    st[name] = {'last': time.time(), 'ok': ok, 'result': str(res)[:300], 'secs': round(time.time() - t0, 1),
                'every_min': JOBS[name]}
    db.kv_set(con, 'monitor_jobs', json.dumps(st))
    log.info('job %s: %s', name, str(res)[:200])


def scheduler(stop):
    con = db.connect()
    while not stop.is_set():
        st = json.loads(db.kv_get(con, 'monitor_jobs', '{}') or '{}')
        for name, every in JOBS.items():
            last = (st.get(name) or {}).get('last', 0)
            if time.time() - last >= every * 60:
                run_job(con, name)
        db.kv_set(con, 'monitor_heartbeat', time.time())
        stop.wait(60)


# ---------------- dashboard server ----------------

def api(path, q):
    import server as tools  # reuse the MCP tool functions
    con = db.connect()
    try:
        if path == '/api/lab/roadmap':   # Build Lab stage 1
            from poe2kit import lab, buildplan
            # the followed plan, else the newest build
            bid = q.get('build') or next(iter(buildplan.followed(con).values()), None) \
                or con.execute('SELECT MAX(id) FROM build').fetchone()[0]
            return lab.roadmap(con, bid)
        if path == '/api/lab/curves':   # Build Lab stage 2: ?build=<id>[&start=1]
            from poe2kit import lab
            if q.get('start'):
                lab.start_curves(q['build'])
            return lab.curves_state(con, q['build'])
        if path == '/api/lab/cards':   # Build Lab stage 3: ?build=<id>[&retest=<card>|&remove=<card>]
            from poe2kit import lab
            if q.get('retest'):
                lab.retest(con, q['build'], q['retest'])
            if q.get('remove'):
                lab.remove_card(con, q['build'], q['remove'])
            return {'cards': lab.cards(con, q['build'])}
        if path == '/api/lab/upgrades':   # Build Lab stage 4
            from poe2kit import lab
            return lab.upgrades(con, q['build'], float(q.get('budget') or 10))
        if path == '/api/lab/defence':   # Build Lab stage 5
            from poe2kit import lab
            return lab.defence(con, q['build'])
        if path == '/api/lab/history':   # Build Lab stage 7
            from poe2kit import lab
            return lab.history(con, q['build'])
        if path == '/api/lab/feed':   # Build Lab stage 8: the Oracle's recent tool calls
            return {'feed': json.loads(db.kv_get(con, 'oracle:feed') or '[]')[-30:]}
        if path == '/api/connectors':
            from poe2kit import connectors
            return connectors.status()
        if path == '/api/lab/bosses':   # Build Lab stage 6
            from poe2kit import lab
            return lab.readiness(con, q['build'])
        if path == '/api/oracle':   # the Oracle's market advice: phase, what to do now, item outlook
            from poe2kit import oracle
            return oracle.advice(con, league=q.get('league') or None, day=float(q['day']) if q.get('day') else None)
        if path == '/api/top1/links':   # R10: character name -> poe.ninja 'account/character' link (from the benchmark read)
            import urllib.parse as _up
            out, league = {}, None
            for lg, rows in con.execute("SELECT league, rows FROM bench WHERE metric='level' AND scope=? ORDER BY ts DESC",
                                        (q.get('scope') or '',)):
                for p in json.loads(rows).get('paths') or []:
                    out.setdefault(_up.unquote(p).rpartition('/')[2], p)
                league = league or lg
            return {'league': league, 'links': out}
        if path == '/api/prophecy':   # R14: timeline, countdowns, the daily omen
            from poe2kit import prophecy
            return {'timeline': prophecy.timeline(con, q.get('league') or None),
                    'countdowns': prophecy.countdowns(con, q.get('league') or None),
                    'omen': prophecy.omen(con, q.get('league') or None)}
        if path == '/api/prophecy/omen':
            from poe2kit import prophecy
            return {'omen': prophecy.omen(con), 'countdowns': prophecy.countdowns(con)}
        if path == '/api/forecast':   # R14: one item's forecast fan + its past launches
            from poe2kit import prophecy
            if not q.get('item'):
                return dict(prophecy.forecast_groups(), items=prophecy.forecast_items())
            return prophecy.forecast_item(con, q['item'], q.get('league') or None,
                                          float(q['day']) if q.get('day') else None)
        if path == '/api/prophecy/patch':   # R14: the newest stored patch notes, read by the rulebook
            from poe2kit import prophecy
            return prophecy.latest_patch_prophecy(con, q.get('gid') or None) or {'items': [], 'error': 'no patch notes stored yet'}
        if path == '/api/prophecy/farm':   # R14: farming oracle for a build
            from poe2kit import prophecy, mapmods
            return prophecy.farm_oracle(con, int(q.get('build') or 0) or mapmods.active_build(con),
                                        float(q['day']) if q.get('day') else None)
        if path == '/api/prophecy/uniques':   # R14: chase unique history by league day
            from poe2kit import prophecy
            return prophecy.unique_history(q.get('name') or None)
        if path == '/api/active':   # R17: the player's characters and the active one
            from poe2kit import chars
            return chars.characters(con)
        if path == '/api/data/status':   # R27: which data version is in use, and the game's own version
            from poe2kit import dataupdate, patchwatch
            return dict(dataupdate.status(con), game=patchwatch.status(con))
        if path == '/api/compare':   # the Compare page: two builds side by side (a = you, b = them)
            from poe2kit import compare, mapmods
            p = compare.pushed(con)
            a = int(q.get('a') or p.get('a') or mapmods.active_build(con) or 0)
            b = q.get('b') or p.get('b')
            if not b:   # default: a top player's build, else another of your builds
                r = con.execute("SELECT id FROM build WHERE id<>? ORDER BY (owner='me'), id DESC LIMIT 1", (a,)).fetchone()
                b = r['id'] if r else None
            if not a or not b:
                return {'error': 'Save two builds in the vault to compare them (Builds page: paste a build).'}
            return compare.compare_view(con, a, int(b))
        if path == '/api/campaign':   # R16: campaign rush guide + checklist + where you are now
            from poe2kit import campaign
            return campaign.guide(con)
        if path == '/api/atlas/strategies':   # R15: strategies with div / hour now and next phase
            from poe2kit import atlasplan
            return atlasplan.strategies(con)
        if path == '/api/atlas/setup':   # R15: a strategy's setup on the atlas tree
            from poe2kit import atlasplan
            return atlasplan.setup(q.get('name') or '')
        if path == '/api/atlas/rolling':
            from poe2kit import atlasplan
            return atlasplan.rolling(con)
        if path == '/api/atlas/tablets':
            from poe2kit import atlasplan
            return atlasplan.tablets()
        if path == '/api/atlas/roi':   # earnings calculator (net of the usual inputs; your own map pace)
            from poe2kit import atlasplan
            fl = lambda k: float(q.get(k) or 0)
            return atlasplan.roi(con, q.get('strategy'), maps_per_hour=fl('mph') or None, extra_div=fl('extra'))
        if path == '/api/atlas/mods':   # R15: waystone / tablet mods, search tokens, danger for a build
            from poe2kit import mapmods
            return mapmods.overview(con, q.get('build') or None, q.get('kind') or 'waystone')
        if path == '/api/atlas/search':   # R15: our own in-game search string (?avoid=g1,g2&want=g3&kind=waystone)
            from poe2kit import mapmods
            sp = lambda k: [x for x in (q.get(k) or '').split(',') if x]
            return mapmods.search_string(sp('avoid'), sp('want'), q.get('kind') or 'waystone')
        if path == '/api/pagever':   # the dashboard reloads itself when its files change (after an update or a fix)
            d = os.path.join(HERE, 'dashboard')
            return {'v': max(os.path.getmtime(os.path.join(d, f)) for f in ('index.html', 'theme.css') if os.path.exists(os.path.join(d, f)))}
        if path == '/api/status':
            s = tools.t_status({})
            s['rates'] = money.rates(con, s['league'])
            s['jobs'] = json.loads(db.kv_get(con, 'monitor_jobs', '{}') or '{}')
            hb = db.kv_get(con, 'monitor_heartbeat')
            s['monitor_alive'] = bool(hb and time.time() - float(hb) < 180)
            s['install'] = install_state()
            s['profile'] = config.profile()
            s['dashboard_window'] = config.settings().get('dashboard_window') or 'app'
            s['paths'] = {'home': config.HOME, 'poe2': config.poe2_dir(), 'client_log': config.client_log(),
                          'version': config.VERSION}
            return s
        if path == '/api/alerts/settings':
            from poe2kit import alerts as _al
            return _al.settings()
        if path == '/api/alerts':
            rows = con.execute('SELECT * FROM alert ORDER BY ts DESC LIMIT 150').fetchall()
            return [dict(r) for r in rows]
        if path == '/api/alerts/seen':
            con.execute('UPDATE alert SET seen=1')
            con.commit()
            return {'ok': True}
        if path == '/api/movers':
            r = tools.t_movers({'hours': float(q.get('hours', 24)), 'limit': 12, 'min_value': float(q.get('min', 0.01))})
            league = ninja.current_league(con)
            rt = money.rates(con, league)
            for lst in (r.get('risers', []), r.get('fallers', [])):
                for x in lst:
                    x['now_text'], x['before_text'] = money.fmt(x['now'], rt), money.fmt(x['before'], rt)
            return r
        if path == '/api/search':
            return tools.t_price({'query': q.get('q', ''), 'limit': 25}) if q.get('q') else []
        if path == '/api/history':
            return tools.t_history({'query': q.get('q', '')})
        if path == '/api/builds':
            return tools.t_vault_list({})
        if path == '/api/patches':
            from poe2kit import patchnotes
            return patchnotes.listing(con)
        if path == '/api/patch':
            from poe2kit import patchnotes
            r = patchnotes.get(con, q.get('gid', ''))
            if r:
                r.pop('all', None) if q.get('lite') else None
            return r or {'error': 'not found'}
        if path == '/api/craft/bases':
            from poe2kit import craftsim
            return craftsim.bases()
        if path == '/api/craft/pool':
            from poe2kit import craftsim
            return craftsim.pool_for_ui(q.get('base', ''), int(q.get('ilvl', 82)))
        if path == '/api/top1':
            from poe2kit import topcheck
            bid = q.get('id')
            if not bid:
                r = con.execute("SELECT id FROM build WHERE owner='me' ORDER BY id DESC LIMIT 1").fetchone()
                if not r:
                    return {'error': 'No character yet. Import one on the Character tab, then come back here.'}
                bid = r['id']
            return topcheck.check(con, int(bid))
        if path == '/api/playbook':
            from poe2kit import leaguestart
            r = leaguestart.playbook(con)
            r.pop('items', None)
            try:   # the Oracle's research: some week-1 risers reverse (e.g. Tacati peaks ~day 10, then falls)
                from poe2kit import oracle
                for x in (r.get('hold') or []) + (r.get('sell_day1') or []):
                    n = oracle.hold_note(x.get('item'))
                    if n:
                        x['oracle'] = n
            except Exception:
                pass
            return r
        if path == '/api/sessions':
            from poe2kit import clientlog
            return clientlog.sessions(con)
        if path == '/api/market':
            from poe2kit import market
            return market.history(con, league=q.get('league') or None, category=q.get('cat') or None, days=int(q.get('days', 7)))
        if path == '/api/icons':
            league = ninja.current_league(con)
            rows = con.execute("""SELECT name, MAX(icon) icon FROM price WHERE league=? AND icon IS NOT NULL AND category IN
                ('Currency','Ritual','Essences','Breach','Delirium','Abyss','Runes','SoulCores','Fragments','Expedition')
                GROUP BY name""", (league,)).fetchall()
            return {r['name']: r['icon'] for r in rows}
        if path == '/api/update':
            from poe2kit import updates
            return updates.status(con)
        if path == '/api/claude':
            from poe2kit import claudelink
            return claudelink.status()
        if path == '/api/farm':
            from poe2kit import farm
            return farm.board(con)
        if path == '/api/classes':
            from poe2kit import leagueplan
            return leagueplan.classes()
        if path == '/api/leagueplan':
            from poe2kit import leagueplan
            prof = config.profile()
            asc = [x for x in q.get('asc', ','.join(prof.get('path') or [prof.get('ascendancy') or ''])).split(',') if x]
            tb = q.get('target') or None
            return leagueplan.plan(con, q.get('cls') or prof.get('class') or 'Witch', asc, int(tb) if tb else None, float(q.get('budget', 0.05)))
        if path == '/api/overview':   # ?league= to look at another league (prices fetched once if not stored)
            from poe2kit import overview
            lg = q.get('league') or None
            if lg and not con.execute('SELECT 1 FROM price WHERE league=? AND ts > ? LIMIT 1', (lg, time.time() - 3 * 3600)).fetchone():
                ninja.snapshot(con, lg)
            return overview.overview(con, league=lg)
        if path == '/api/leagues':   # the leagues poe.ninja lists right now, plus the app's choice
            return {'leagues': ninja.leagues(con), 'chosen': config.settings().get('league'), 'current': ninja.current_league(con)}
        if path == '/api/mychars':
            from poe2kit import charimport
            return charimport.list_characters(con, fresh=q.get('fresh') == '1')
        if path == '/api/import':
            from poe2kit import charimport
            return charimport.import_character(con, q.get('name', ''), fresh=q.get('fresh') == '1')
        if path == '/api/character':
            from poe2kit import character
            return character.character(con, int(q.get('id', 1)))
        if path == '/api/tree':
            if q.get('v') == 'atlas':   # the atlas passive tree, from the game files (poe2kit/atlas.py)
                from poe2kit import atlas
                return atlas.tree_for_viewer()
            from poe2kit import character
            return character.tree(q.get('v', '0_5'))
        if path == '/api/show':
            v = db.kv_get(con, 'show')
            return json.loads(v) if v else {}
        return {'error': 'unknown endpoint'}
    finally:
        con.close()


def craft_post(path, b):
    import random
    from poe2kit import craftsim, crafting
    con = db.connect()
    try:
        pr = crafting.prices(con)
        if path in ('/api/claude/connect', '/api/claude/disconnect'):
            from poe2kit import claudelink
            return claudelink.connect() if path.endswith('/connect') else claudelink.disconnect()
        if path == '/api/update/install':
            from poe2kit import updates
            return updates.install(con)
        if path == '/api/profile':
            keep = {k: b[k] for k in ('class', 'ascendancy', 'path', 'watch', 'name') if k in b}
            keep['configured'] = True
            ch = {'profile': keep}
            if 'poe2_dir' in b:
                ch['poe2_dir'] = b['poe2_dir'] or None
            config.save_settings(ch)
            return {'ok': True, 'profile': config.profile(), 'poe2': config.poe2_dir()}
        if path == '/api/report':   # Report an issue / Suggestions: to the developer (anonymous, see poe2kit/report.py)
            from poe2kit import report
            try:
                return report.send(b.get('kind'), b.get('text') or '', b.get('name') or '', bool(b.get('attach', True)))
            except ValueError as e:
                return {'ok': False, 'why': str(e)}
            except Exception as e:
                return {'ok': False, 'why': f'Could not send ({type(e).__name__}). Check the internet connection, or use GitHub.'}
        if path == '/api/report/preview':
            from poe2kit import report
            return {'text': report.preview(b.get('kind'), b.get('text') or '', bool(b.get('attach', True)))}
        if path == '/api/connectors':   # other AI apps: {target: chatgpt|gemini, action: connect|disconnect}
            from poe2kit import connectors
            return connectors.connect(b.get('target')) if b.get('action') == 'connect' else connectors.disconnect(b.get('target'))
        if path == '/api/ninja/open':   # R10: a player's poe.ninja page in an Exile Oracle window (the one page clicked)
            import re as _re
            from poe2kit import osutil
            p, lg = str(b.get('path') or ''), str(b.get('league') or '')
            if not _re.fullmatch(r"[A-Za-z0-9%._~'()!*-]+/[A-Za-z0-9%._~'()!*-]+", p):
                return {'ok': False, 'why': 'bad character link'}
            slug = _re.sub(r'[^a-z0-9]', '', lg.lower())
            osutil.detached([osutil.background_python(), os.path.join(HERE, 'ninja_view.pyw'), p, slug, lg], cwd=HERE)
            return {'ok': True}
        if path == '/api/vault/from_ninja':   # R10: "Save this build" pressed on that page
            from poe2kit import vault
            code = str(b.get('code') or '').strip()
            try:
                vault.decode(code)
            except Exception:
                return {'ok': False, 'why': "That doesn't look like a Path of Building code."}
            ch, acct, lg = b.get('character') or 'player', b.get('account') or '', b.get('league') or None
            bid, _sum = vault.add(con, code, f'{ch} (poe.ninja, {lg})' if lg else f'{ch} (poe.ninja)',
                            owner=f'{acct} (poe.ninja)' if acct else 'poe.ninja', league=lg, source_url=b.get('url'))
            return {'ok': True, 'id': bid, 'message': f'Saved as vault #{bid}: open it in the Build Lab, or ask the Oracle to compare it with yours.'}
        if path == '/api/league':   # Settings: which league the whole app follows ('' = automatic: the newest)
            config.save_settings({'league': (b.get('league') or None)})
            return {'ok': True, 'current': ninja.current_league(con)}
        if path == '/api/window':   # how the tray / shortcut open the dashboard: 'app' window or 'browser' tab
            config.save_settings({'dashboard_window': 'browser' if b.get('mode') == 'browser' else 'app'})
            from poe2kit import appwindow
            return {'ok': True, 'mode': appwindow.mode()}
        if path == '/api/patch/analyze':
            from poe2kit import patchnotes
            return patchnotes.analyze(con, b.get('text', ''), b.get('title') or 'pasted notes')
        if path == '/api/craft/plan':
            return craftsim.plan(b['state'], b.get('targets', []), pr)
        if path == '/api/craft/apply':
            st, msg, used = craftsim.apply(b['state'], b['action'], random.Random(b.get('seed')))
            return {'state': st, 'message': msg, 'used': used,
                    'cost_div': round(sum(pr.get(i) or 0 for i in used), 4),
                    'plan': craftsim.plan(st, b.get('targets', []), pr)}
        if path == '/api/craft/simulate':
            return craftsim.simulate(b['state'], b.get('targets', []), pr, runs=min(int(b.get('runs', 200)), 1000),
                                     max_steps=min(int(b.get('max_steps', 200)), 600))
        if path == '/api/craft/import':
            from poe2kit.character import _item
            it = _item(b['text'])
            base = it['base'] if it['rarity'] in ('RARE', 'UNIQUE') else b.get('base') or it['base']
            ilvl = int(''.join(ch for ch in (it.get('item_level') or '') if ch.isdigit()) or b.get('ilvl') or 82)
            mods = craftsim.import_item(base, ilvl, [m['t'] for m in it['explicits']])
            rarity = it['rarity'].lower() if it['rarity'] in ('NORMAL', 'MAGIC', 'RARE') else 'rare'
            return {'base': base, 'ilvl': ilvl, 'rarity': rarity, 'mods': mods}
        if path == '/api/craft/from_build':
            from poe2kit import character
            c = character.character(con, int(b['build_id']))
            it = next((g for g in c['gear'] + c['jewels'] if g['slot'].lower() == b['slot'].lower()), None)
            if not it:
                raise ValueError('no item in that slot')
            ilvl = int(''.join(ch for ch in (it.get('item_level') or '') if ch.isdigit()) or 82)
            mods = craftsim.import_item(it['base'], ilvl, [m['t'] for m in it['explicits']])
            return {'base': it['base'], 'ilvl': ilvl, 'rarity': 'rare', 'mods': mods, 'name': it['name']}
        return {'error': 'unknown endpoint'}
    finally:
        con.close()


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _img(self, url):
        """Item pictures from GGG's image CDN, cached on F: so each is fetched once."""
        import hashlib
        if not url.startswith('https://web.poecdn.com/'):
            return self._send(400, b'bad image url', 'text/plain')
        os.makedirs(IMG_DIR, exist_ok=True)
        path = os.path.join(IMG_DIR, hashlib.sha1(url.encode()).hexdigest() + '.png')
        if not os.path.exists(path):
            try:
                req = urllib.request.Request(url, headers={'User-Agent': config.user_agent()})
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = r.read()
                with open(path + '.part', 'wb') as f:
                    f.write(data)
                os.replace(path + '.part', path)
            except Exception:
                return self._send(404, b'', 'text/plain')
        with open(path, 'rb') as f:
            body = f.read()
        self.send_response(200)
        self.send_header('Content-Type', 'image/png')
        self.send_header('Cache-Control', 'max-age=604800')
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        try:
            n = int(self.headers.get('Content-Length') or 0)
            body = json.loads(self.rfile.read(n) or b'{}')
            if u.path == '/api/overlay/item':
                from poe2kit import overlaysrv
                data = {'id': overlaysrv.submit(body.get('text', ''))}
            elif u.path == '/api/overlay/search':
                from poe2kit import overlaysrv
                data = overlaysrv.research(body.get('filters'))
            elif u.path == '/api/overlay/options':
                from poe2kit import overlaysrv
                data = overlaysrv.set_options(body)
            elif u.path == '/api/overlay/send_claude':   # popup's "Ask the Oracle": save it, bring Claude forward
                from poe2kit import overlaysrv, osutil
                data = overlaysrv.send_to_claude()
                data['target'] = config.settings().get('ask_claude_target') or 'app'
                if data.get('ok') and body.get('open', True) and data['target'] == 'app':
                    try:
                        if osutil.IS_WIN:
                            os.startfile('claude://')
                        else:
                            import webbrowser
                            webbrowser.open('https://claude.ai/new')
                    except OSError as e:
                        data['open_error'] = str(e)
            elif u.path == '/api/overlay/settings_open':
                from poe2kit import overlaysrv
                data = overlaysrv.open_settings()
            elif u.path == '/api/overlay/size':
                from poe2kit import overlaysrv
                data = overlaysrv.set_size(body)
            elif u.path == '/api/route/zone':   # R21: overlay.pyw saw a zone change in Client.txt
                from poe2kit import campaign
                data = {'ver': campaign.set_zone(str(body.get('area') or '')[:80] or None, body.get('level'))}
            elif u.path == '/api/prophecy/patch':   # R14: pasted patch notes -> expected price moves
                from poe2kit import prophecy, db as _db
                c = _db.connect()
                try:
                    data = prophecy.patch_prophecy(str(body.get('text') or '')[:200000], c)
                finally:
                    c.close()
            elif u.path == '/api/active':   # R17: pick the active character
                from poe2kit import chars, db as _db
                c = _db.connect()
                try:
                    data = chars.set_active(c, body.get('build_id'))
                finally:
                    c.close()
            elif u.path in ('/api/data/check', '/api/data/rollback'):   # R27: Settings buttons
                from poe2kit import dataupdate, db as _db
                c = _db.connect()
                try:
                    data = dataupdate.check(c) if u.path.endswith('check') else dataupdate.rollback()
                    from poe2kit import patchwatch
                    data['status'] = dict(dataupdate.status(c), game=patchwatch.status(c))
                finally:
                    c.close()
            elif u.path == '/api/ask/open':   # a question chip: open the AI app with the question typed in
                from poe2kit import overlaysrv
                data = overlaysrv.open_question(body.get('text'))
            elif u.path == '/api/alerts/settings':   # Settings → Alerts (and "mute this item")
                from poe2kit import alerts as _al
                data = _al.save(body)
            elif u.path == '/api/alerts/delete':   # clear read alerts
                from poe2kit import db as _db
                c = _db.connect()
                try:
                    c.execute('DELETE FROM alert WHERE seen=1')
                    c.commit()
                    data = {'ok': True}
                finally:
                    c.close()
            elif u.path in ('/api/vault/paste', '/api/vault/delete'):   # Builds page: paste a build / delete one
                from poe2kit import vault, db as _db, osutil
                c = _db.connect()
                try:
                    if u.path.endswith('paste'):
                        data = vault.from_paste(c, str(body.get('text') or '')[:200000], body.get('label'), bool(body.get('mine')))
                        n = data.get('open_ninja')
                        if n:   # a poe.ninja character: its page in our own window, with the Save button
                            osutil.detached([osutil.background_python(), os.path.join(HERE, 'ninja_view.pyw'), n['path'],
                                             n['slug'], ''], cwd=HERE)
                    else:
                        data = vault.delete(c, body.get('id'))
                finally:
                    c.close()
            elif u.path == '/api/route/size':
                from poe2kit import campaign
                data = campaign.set_size(body)
            elif u.path == '/api/route/toggle':   # R21: the route panel's show / hide key
                from poe2kit import campaign
                data = {'hidden': campaign.toggle_hidden()}
            elif u.path == '/api/campaign/done':   # R16: tick a permanent reward on the checklist
                from poe2kit import campaign, db as _db
                c = _db.connect()
                try:
                    data = {'done': campaign.set_done(c, str(body.get('key') or ''), bool(body.get('on')))}
                finally:
                    c.close()
            elif u.path == '/api/planner':   # character page: send this build to the game's Build Planner
                import server as tools
                args = {'build_id': body.get('build_id'), 'write': True, 'confirm': bool(body.get('confirm'))}
                if 'follow' in body:
                    args['follow'] = str(body.get('follow') or '')
                data = tools.t_build_planner(args)
                data.pop('preview', None)
            elif u.path == '/api/open':   # the overlay's "Open on trade" button: only the official trade site
                url = str(body.get('url', ''))
                if not url.startswith('https://www.pathofexile.com/trade2/'):
                    return self._send(400, b'{"error":"only trade site links"}', 'application/json')
                import webbrowser
                webbrowser.open(url)
                data = {'ok': True}
            else:
                data = craft_post(u.path, body)
            return self._send(200, json.dumps(data, default=str).encode('utf-8'), 'application/json')
        except Exception as e:
            return self._send(500, json.dumps({'error': f'{type(e).__name__}: {e}'}).encode(), 'application/json')

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path in ('/', '/index.html'):
            with open(os.path.join(HERE, 'dashboard', 'index.html'), 'rb') as f:
                return self._send(200, f.read(), 'text/html; charset=utf-8')
        if u.path.startswith('/static/'):   # theme.css, fonts, the emblem (only files inside dashboard/)
            base = os.path.join(HERE, 'dashboard')
            fp = os.path.normpath(os.path.join(base, urllib.parse.unquote(u.path[8:])))
            kinds = {'.css': 'text/css; charset=utf-8', '.ttf': 'font/ttf', '.woff2': 'font/woff2',
                     '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.js': 'text/javascript',
                     '.html': 'text/html; charset=utf-8'}
            ext = os.path.splitext(fp)[1].lower()
            if not fp.startswith(base + os.sep) or ext not in kinds or not os.path.isfile(fp):
                return self._send(404, b'', 'text/plain')
            with open(fp, 'rb') as f:
                body = f.read()
            self.send_response(200)
            self.send_header('Content-Type', kinds[ext])
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(body)
            return
        if u.path == '/route':   # R21: the route panel page
            with open(os.path.join(HERE, 'dashboard', 'route.html'), 'rb') as f:
                return self._send(200, f.read(), 'text/html; charset=utf-8')
        if u.path == '/api/route/size':
            from poe2kit import campaign
            return self._send(200, json.dumps(campaign.size()).encode(), 'application/json')
        if u.path == '/api/route/state':   # R21: long poll, returns when the zone changes
            from poe2kit import campaign, db as _db
            q = urllib.parse.parse_qs(u.query)
            c = _db.connect()
            try:
                st = campaign.zone_state(int(q.get('after', ['-1'])[0] or -1),
                                         min(25, int(q.get('wait', ['25'])[0] or 25)), c)
            except FileNotFoundError as e:
                st = {'show': False, 'error': str(e), 'ver': 0}
            finally:
                c.close()
            st['page'] = os.path.getmtime(os.path.join(HERE, 'dashboard', 'route.html'))
            st['on'] = bool(config.settings().get('route_overlay', True))
            return self._send(200, json.dumps(st, default=str).encode('utf-8'), 'application/json')
        if u.path == '/overlay':
            with open(os.path.join(HERE, 'dashboard', 'overlay.html'), 'rb') as f:
                return self._send(200, f.read(), 'text/html; charset=utf-8')
        if u.path == '/api/planner':   # the saved in-game plan of a vault build (followed character, notes, edits)
            from poe2kit import buildplan, db as _db
            c = _db.connect()
            try:
                bid = int(urllib.parse.parse_qs(u.query).get('build_id', ['0'])[0] or 0)
                return self._send(200, json.dumps(buildplan.get(c, bid)).encode(), 'application/json')
            finally:
                c.close()
        if u.path == '/api/overlay/options':
            from poe2kit import overlaysrv
            return self._send(200, json.dumps(overlaysrv.options()).encode(), 'application/json')
        if u.path == '/api/overlay/size':
            from poe2kit import overlaysrv
            return self._send(200, json.dumps(overlaysrv.size()).encode(), 'application/json')
        if u.path == '/api/overlay/latest':
            from poe2kit import overlaysrv
            q = urllib.parse.parse_qs(u.query)
            st = overlaysrv.wait(int(q.get('after', ['0'])[0] or 0))
            st['page'] = os.path.getmtime(os.path.join(HERE, 'dashboard', 'overlay.html'))   # page reloads on change
            return self._send(200, json.dumps(st, default=str).encode('utf-8'), 'application/json')
        if u.path == '/artfind':   # game-art picture by name: ?n=<name>&b=<base>&k=unique|skill|base (any kind if no k)
            from poe2kit import art
            q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
            n, b, k = q.get('n', ''), q.get('b', ''), q.get('k', '')
            rel = None
            for kind in ([k] if k else ['unique', 'skill', 'base']):
                rel = rel or art.find(kind, n)
            rel = rel or (art.find('base', b) if b else None) or (art.for_item(n, b, 'UNIQUE') if n else None)
            fp = art.file_for(rel) if rel else None
            if not fp:
                return self._send(404, b'', 'text/plain')
            with open(fp, 'rb') as f:
                body = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Cache-Control', 'max-age=604800')
            self.end_headers()
            self.wfile.write(body)
            return
        if u.path.startswith('/art/'):
            from poe2kit import art
            fp = art.file_for(urllib.parse.unquote(u.path[5:]))
            if not fp:
                return self._send(404, b'', 'text/plain')
            with open(fp, 'rb') as f:
                body = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Cache-Control', 'max-age=604800')
            self.end_headers()
            self.wfile.write(body)
            return
        if u.path == '/img':
            return self._img(urllib.parse.parse_qs(u.query).get('u', [''])[0])
        if u.path.startswith('/api/'):
            q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
            try:
                data = api(u.path, q)
                return self._send(200, json.dumps(data, default=str).encode('utf-8'), 'application/json')
            except FileNotFoundError as e:
                wait = setting_up()
                if wait:   # a fresh install still downloading: say so instead of a crash
                    return self._send(503, json.dumps({'setup': True, 'waiting_for': wait, 'error':
                        'Still setting up (first start): downloading ' + ' and '.join(wait) +
                        '. This takes a few minutes; this view works once it finishes.'}).encode(), 'application/json')
                return self._send(500, json.dumps({'error': f'{type(e).__name__}: {e}'}).encode(), 'application/json')
            except Exception as e:
                return self._send(500, json.dumps({'error': f'{type(e).__name__}: {e}'}).encode(), 'application/json')
        return self._send(404, b'not found', 'text/plain')


class Server(http.server.ThreadingHTTPServer):
    """On Windows SO_REUSEADDR lets a second process bind the same port (two monitors, both answering): refuse it."""
    allow_reuse_address = os.name != 'nt'
    daemon_threads = True


def take_lock():
    try:
        if os.path.exists(LOCK):
            pid = int(open(LOCK).read().strip() or 0)
            from poe2kit import osutil
            if osutil.pid_alive(pid) and pid != os.getpid():
                return False
        with open(LOCK, 'w') as f:
            f.write(str(os.getpid()))
        return True
    except OSError:
        return True


def main(argv):
    setup_log()
    if '--once' in argv:
        con = db.connect()
        for name in ([a for a in argv if a in JOBS] or JOBS):
            run_job(con, name)
        return 0
    if '--serve' in argv:   # developer mode: only the dashboard (e.g. POE2KIT_PORT=47831), no jobs, no overlay, no lock,
        srv = Server(('127.0.0.1', PORT), Handler)   # so it runs beside the installed app
        log.info('serve-only dashboard on http://127.0.0.1:%d', PORT)
        srv.serve_forever()
        return 0
    if not take_lock():
        print('monitor already running')
        return 0
    stop = threading.Event()
    threading.Thread(target=scheduler, args=(stop,), daemon=True).start()
    srv = Server(('127.0.0.1', PORT), Handler)
    log.info('dashboard on http://127.0.0.1:%d', PORT)
    try:
        from poe2kit import overlaysrv
        overlaysrv.autostart()   # the price-check overlay, when it is switched on (Windows)
    except Exception as e:
        log.warning('overlay not started: %s', e)
    try:
        srv.serve_forever()
    finally:
        stop.set()
        try:
            os.remove(LOCK)
        except OSError:
            pass


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
