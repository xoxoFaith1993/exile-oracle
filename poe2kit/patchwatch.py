"""Patch day (R27, step 2): notice when Path of Exile 2 itself updates, then look for new data every hour.

The game's version: Steam's install record has a build id that changes with every patch and hotfix
(steamapps/appmanifest_2694490.acf "buildid"); standalone installs use the size + time of Bundles2/_.index.bin.
Read-only, like everything else: nothing in the game folder is touched.

When the version changes, "patch mode" runs for 48 hours: every hour the community game data (items, mods, gems)
is checked and only downloaded if it really changed (conditional requests), and our data packs are checked too.
Outside patch mode the normal schedule applies (community data every 3 days, data packs every 6 hours)."""

import json
import os
import re
import time

from . import config, db

PATCH_HOURS = 48
EVERY = 3600


def game_build():
    """{'build', 'source', 'updated'} for the installed game, or None."""
    acf = config.steam_manifest()
    if acf and os.path.exists(acf):
        try:
            text = open(acf, encoding='utf-8', errors='replace').read()
            b = re.search(r'"buildid"\s+"(\d+)"', text)
            u = re.search(r'"LastUpdated"\s+"(\d+)"', text)
            if b:
                return {'build': b.group(1), 'source': 'steam', 'updated': int(u.group(1)) if u else None}
        except OSError:
            pass
    d = config.poe2_dir()
    idx = os.path.join(d, 'Bundles2', '_.index.bin') if d else None
    if idx and os.path.exists(idx):
        st = os.stat(idx)
        return {'build': f'{int(st.st_mtime)}-{st.st_size}', 'source': 'index', 'updated': int(st.st_mtime)}
    return None


def state(con):
    try:
        return json.loads(db.kv_get(con, 'patchwatch') or '{}')
    except ValueError:
        return {}


def _save(con, s):
    db.kv_set(con, 'patchwatch', json.dumps(s))
    con.commit()


def tick(con, alert=None):
    """Run by the monitor every few minutes. Returns a short line for the job log."""
    s = state(con)
    g = game_build()
    now = time.time()
    if g:
        if s.get('build') and g['build'] != s['build']:
            s.update(previous=s['build'], changed_at=now, patch_until=now + PATCH_HOURS * 3600, last_run=0)
            if alert:
                alert(con, 'update', f"Path of Exile 2 updated (build {g['build']})",
                      'Exile Oracle checks for new game data every hour for the next 2 days.')
        s.update(build=g['build'], source=g['source'], game_updated=g.get('updated'))
    active = now < (s.get('patch_until') or 0)
    if not active:
        _save(con, s)
        return f"game build {s.get('build') or '?'} ({s.get('source') or 'not found'})"
    if now - (s.get('last_run') or 0) < EVERY:
        _save(con, s)
        return f"patch mode: next check in {int((EVERY - (now - s['last_run'])) / 60)} min"
    s['last_run'] = now
    out = []
    try:
        from . import gamedata
        r = gamedata.update(max_age_days=0, conditional=True)
        changed = [k for k, v in r.items() if v not in ('fresh', 'unchanged')]
        out.append(f"community data: {', '.join(changed) + ' updated' if changed else 'no change yet'}")
        if changed:
            s['data_changed_at'] = now
    except Exception as e:
        out.append(f'community data check failed: {e}')
    try:
        from . import dataupdate
        r = dataupdate.check(con)
        out.append(f"data pack: {'installed ' + r['installed'] if r.get('installed') else r.get('why') or 'up to date'}")
        if r.get('installed') and alert:
            alert(con, 'update', f"Game data updated to {r['installed']}", 'New data is in use: nothing to install.')
    except Exception as e:
        out.append(f'data pack check failed: {e}')
    s['last_result'] = '; '.join(out)
    _save(con, s)
    return 'patch mode: ' + s['last_result']


def status(con):
    s = state(con)
    now = time.time()
    return {'build': s.get('build'), 'source': s.get('source'), 'previous': s.get('previous'),
            'patch_mode': now < (s.get('patch_until') or 0), 'patch_until': s.get('patch_until'),
            'changed_at': s.get('changed_at'), 'last_result': s.get('last_result')}
