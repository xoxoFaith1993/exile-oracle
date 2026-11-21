"""poe2_doctor: checks every part of the toolkit and says which TROUBLESHOOTING.md sections apply.
Read-only: it never changes anything."""

import json
import os
import re
import time
import urllib.request

from . import config, osutil


def _get(path, timeout=5):
    port = int(os.environ.get('POE2KIT_PORT', '47830'))
    with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}', timeout=timeout) as r:
        return json.loads(r.read())


def _lock_pid(name):
    try:
        return int(open(os.path.join(config.HOME, name)).read().strip() or 0)
    except (OSError, ValueError):
        return 0


def _log_problems(name, n=8):
    p = os.path.join(config.LOG_DIR, name)
    try:
        lines = open(p, encoding='utf-8', errors='replace').read().splitlines()[-400:]
    except OSError:
        return []
    bad = [l for l in lines if re.search(r'error|traceback|failed|exception', l, re.I)
           and not re.search(r'currency-exchange/poe2/\d+ -> HTTP 404', l)]   # fixed: next hour not out yet
    return bad[-n:]


def run():
    out = {'version': config.VERSION, 'system': 'Windows' if osutil.IS_WIN else 'Linux', 'home': config.HOME,
           'checks': [], 'see': []}

    def add(part, ok, detail, see=None):
        out['checks'].append({'part': part, 'ok': bool(ok), 'detail': detail})
        if not ok and see and see not in out['see']:
            out['see'].append(see)

    # monitor + dashboard
    try:
        st = _get('/api/status')
        jobs = st.get('jobs') or {}
        failing = {k: v for k, v in jobs.items() if isinstance(v, dict) and re.search(r'fail|error', str(v.get('result', '')), re.I)}
        add('monitor', True, f"running; league {st.get('league')}" + (f'; jobs with errors: {", ".join(failing)}' if failing else ''),
            'Dashboard' if failing else None)
        if failing:
            out['checks'][-1]['ok'] = False
    except Exception as e:
        add('monitor', False, f'dashboard not answering ({type(e).__name__}); lock pid {_lock_pid("monitor.lock") or "none"}',
            'Restarting things')
    s = config.settings()

    # Path of Building
    try:
        from . import pob
        r = pob.runner()
        add('path of building', pob.ready(), 'ready' if pob.ready() else
            ('PoB not downloaded yet' if not os.path.exists(os.path.join(config.POB_DIR, 'manifest.xml'))
             else 'no Lua runner (' + ('tools\\poblua.exe' if osutil.IS_WIN else 'linux/bin/luajit') + ')') +
            ('' if r else ''), 'Path of Building')
    except Exception as e:
        add('path of building', False, str(e), 'Path of Building')

    # game + its log
    try:
        d, log = config.poe2_dir(), config.client_log()
        age = (time.time() - os.path.getmtime(log)) / 3600 if log else None
        add('game', bool(d), f'game folder {d or "not found"}; log {log or "none yet (play once)"}' +
            (f'; last written {age:.1f} h ago' if age is not None else ''), 'Linux / Steam Deck' if not osutil.IS_WIN else 'Dashboard')
    except Exception as e:
        add('game', False, str(e), 'Dashboard')

    # overlay
    if osutil.IS_WIN:
        on = s.get('overlay', config.is_dev_copy())
        try:
            from . import overlaysrv
            running = overlaysrv.running()
        except Exception:
            running = False
        add('overlay', (not on) or running, f"setting {'on' if on else 'off'}; process {'running' if running else 'not running'}",
            'Overlay (Windows)')
        probs = _log_problems('overlay.log')
        if probs:
            add('overlay log', False, ' | '.join(probs[-4:]), 'Overlay (Windows)')
        try:   # can the hotkeys be had? (only meaningful while the game isn't in front)
            import ctypes
            u, k = ctypes.windll.user32, ctypes.windll.kernel32
            held = []
            for name, mods in (('Ctrl+D', 0x2), ('Ctrl+Alt+D', 0x3), ('Ctrl+Shift+D', 0x6)):
                if u.RegisterHotKey(None, 0x7700, mods | 0x4000, 0x44):
                    u.UnregisterHotKey(None, 0x7700)
                else:
                    held.append(name)
            if held:
                add('hotkeys', True, f'{", ".join(held)} currently registered (normal while the game is in front with '
                                     'the overlay on; if the game is NOT in front, another program holds them)')
        except Exception:
            pass
    else:
        add('overlay', True, 'Windows-only for now')
    add('live trade prices', True, 'on' if s.get('live_trade', config.is_dev_copy()) else
        "off (the player's choice; Ctrl+Shift+D)")
    add('ask claude', True, f"sends to {s.get('ask_claude_target') or 'app'}")

    # build planner
    try:
        from . import buildplanner, buildplan, db
        f = buildplanner.folder()
        files = buildplanner.files()
        con = db.connect()
        try:
            follow = buildplan.followed(con)
        finally:
            con.close()
        add('build planner', bool(f), f"folder {f or 'not found (start the game once)'}; "
            f"toolkit plans: {', '.join(x['file'] for x in files if x['mine']) or 'none'}; "
            f"following: {', '.join(follow) or 'nobody'}; allowed to write: {bool(s.get('build_planner_ok'))}",
            'In-game Build Planner')
    except Exception as e:
        add('build planner', False, str(e), 'In-game Build Planner')

    probs = _log_problems('monitor.log')
    if probs:
        add('monitor log', False, ' | '.join(probs[-4:]), 'Dashboard')

    guide = os.path.join(config.ROOT, 'TROUBLESHOOTING.md')
    out['guide_file'] = guide
    try:
        out['guide'] = open(guide, encoding='utf-8').read()
    except OSError:
        out['guide'] = 'TROUBLESHOOTING.md missing from this install'
    out['summary'] = ('All checks passed.' if all(c['ok'] for c in out['checks']) else
                      'Problems: ' + '; '.join(f"{c['part']}: {c['detail']}" for c in out['checks'] if not c['ok']))
    return out
