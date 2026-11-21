"""First-run setup for a fresh install (a friend's PC): get Path of Building and the headless launcher in place.
the author's install already has both, so this does nothing there.

  - Path of Building (PoE 2) community edition: the dev branch as a zip from GitHub (no git needed), unpacked to
    HOME\\pob. MIT licensed; its LICENSE.md comes with it.
  - poblua.exe (our tiny launcher that runs PoB's own Lua runtime headless): shipped in the app's bin\\ folder,
    copied to HOME\\tools.
Game data (RePoE) is fetched by the monitor's normal 'gamedata' job. Extracted game files and art are optional."""

import io
import os
import shutil
import time
import urllib.request
import zipfile

from . import config, db

POB_ZIP = 'https://codeload.github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/zip/refs/heads/dev'


def state(con):
    return {'pob': os.path.exists(os.path.join(config.POB_DIR, 'manifest.xml')),
            'poblua': __import__('poe2kit.pob', fromlist=['pob']).runner() is not None,   # Linux: LuaJIT
            'progress': db.kv_get(con, 'bootstrap_progress', '')}


def _say(con, msg):
    db.kv_set(con, 'bootstrap_progress', msg)
    con.commit()


def ensure_poblua(con):
    if os.name != 'nt':
        return 'not needed (Linux runs PoB with LuaJIT)'
    dst = os.path.join(config.TOOLS_DIR, 'poblua.exe')
    if os.path.exists(dst):
        return 'present'
    src = os.path.join(config.ROOT, 'bin', 'poblua.exe')
    if not os.path.exists(src):
        return 'missing from the app (bin\\poblua.exe)'
    os.makedirs(config.TOOLS_DIR, exist_ok=True)
    shutil.copy2(src, dst)
    return 'copied'


def ensure_pob(con):
    if os.path.exists(os.path.join(config.POB_DIR, 'manifest.xml')):
        return 'present'
    _say(con, 'Downloading Path of Building (about 100 MB)…')
    req = urllib.request.Request(POB_ZIP, headers={'User-Agent': config.user_agent()})
    tmp = os.path.join(config.HOME, 'pob-download.zip')
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, 'wb') as f:
        got = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if got % (10 << 20) < (1 << 20):
                _say(con, f'Downloading Path of Building… {got >> 20} MB')
    _say(con, 'Unpacking Path of Building…')
    staging = config.POB_DIR + '.new'
    shutil.rmtree(staging, ignore_errors=True)
    with zipfile.ZipFile(tmp) as z:
        z.extractall(staging)
    inner = next((os.path.join(staging, d) for d in os.listdir(staging)), staging)  # zip has one top folder
    shutil.rmtree(config.POB_DIR, ignore_errors=True)
    shutil.move(inner, config.POB_DIR)
    shutil.rmtree(staging, ignore_errors=True)
    os.remove(tmp)
    _say(con, 'Path of Building ready.')
    return 'downloaded'


def run(con):
    """Idempotent: returns what it did."""
    out = {'poblua': ensure_poblua(con)}
    try:
        out['pob'] = ensure_pob(con)
    except Exception as e:  # network trouble: the next run tries again
        out['pob'] = f'failed: {e}'
        _say(con, f'Path of Building download failed ({e}); will retry.')
    return out
