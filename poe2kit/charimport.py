"""Background character import through Path of Building's own GGG login (headless PoB, no window).

On request only: nothing calls this on a timer. Gentle on GGG's servers:
- the character list is reused for 15 minutes, and a character imported in the last 15 minutes is reused
  instead of asking again (pass fresh=True to override for one call, still rate-limited by PoB's own
  rate limiter, which follows GGG's headers);
- if PoB's login has expired while PoB's window is open, it stops instead of renewing it (renewing in two
  places at once would sign the window out)."""

import json
import os
import re
import shutil
import subprocess
import tempfile
import time

from . import config, db, osutil, pob, vault

# Path of Building's user folder: Windows Documents, or a Wine / Proton prefix's Documents on Linux
USERPATH = osutil.find_documents('Path of Building (PoE2)') + os.sep
SETTINGS = os.path.join(USERPATH, 'Settings.xml')
SCRIPT = os.path.join(config.ROOT, 'pobhost', 'pobimport.lua')
REUSE_SECONDS = 15 * 60


def _pob_window_open():
    return osutil.process_running('Path of Building-PoE2')


def _token_expiry():
    try:
        s = open(SETTINGS, encoding='utf-8').read()
    except OSError:
        return None
    m = re.search(r'tokenExpiry="(\d+)"', s)
    return int(m.group(1)) if m else None


def _run(mode, char=None):
    exp = _token_expiry()
    if exp is None:
        return {'ok': False, 'error': 'Path of Building is not signed in with GGG (no saved login found).'}
    window = _pob_window_open()
    allow_refresh = not window
    if exp < time.time() + 60 and window:
        return {'ok': False, 'error': "PoB's GGG login has expired and PoB's window is open: press Import once in "
                                      'PoB to renew it, or close PoB and ask again.'}
    tmp = tempfile.mkdtemp(prefix='pobimp-', dir=pob.CACHE)
    outp = os.path.join(tmp, 'out.json')
    if allow_refresh and exp < time.time() + 60:  # a renewal will rewrite PoB's settings: keep a backup
        shutil.copy2(SETTINGS, os.path.join(config.DATA_DIR, 'pob-settings-backup.xml'))
    try:
        env = dict(POB_USERPATH=USERPATH.replace('\\', '/'), POB_OUT=outp, POB_MODE=mode, POB_CHAR=char or '',
                   POB_ALLOW_REFRESH='1' if allow_refresh else '0', TEMP=tmp, TMP=tmp, TMPDIR=tmp)
        p = pob.run(SCRIPT, env, timeout=180)
        if not os.path.exists(outp):
            tail = (p.stderr or p.stdout or '').strip().splitlines()[-4:]
            return {'ok': False, 'error': 'headless PoB failed: ' + ' | '.join(tail)}
        with open(outp, encoding='utf-8') as f:
            return json.load(f)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        # PoB writes the raw API reply next to its scripts; don't leave a copy of it lying around
        try:
            os.remove(os.path.join(pob.POB, 'src', 'poe_api_response.json'))
        except OSError:
            pass


def list_characters(con, fresh=False):
    cached = db.kv_get(con, 'charlist_cache')
    if cached and not fresh:
        c = json.loads(cached)
        if time.time() - c['ts'] < REUSE_SECONDS:
            return {'ok': True, 'characters': c['characters'], 'cached': True}
    r = _run('list')
    if r.get('ok'):
        db.kv_set(con, 'charlist_cache', json.dumps({'ts': time.time(), 'characters': r['characters']}))
    return r


def import_character(con, name, fresh=False):
    key = f'charimport:{name.lower()}'
    last = db.kv_get(con, key)
    if last and not fresh:
        ts, bid = last.split(':')
        if time.time() - float(ts) < REUSE_SECONDS:
            return {'ok': True, 'build_id': int(bid), 'reused': True,
                    'note': 'imported less than 15 minutes ago, reusing it (pass fresh to re-import)'}
    r = _run('import', name)
    if not r.get('ok'):
        return r
    ch = r['character']
    when = time.strftime('%Y-%m-%d %H:%M')
    bid, s = vault.add(con, vault.encode(r['xml']), f"{ch['name']} (live {when})", owner='me', league=ch.get('league'),
                       notes='background import via Path of Building (GGG login)')
    db.kv_set(con, key, f'{time.time()}:{bid}')
    return {'ok': True, 'build_id': bid, 'character': ch, 'ascendancy': s['ascendancy'], 'level': s['level'],
            'gear_items': len(s['items']), 'renewed_pob_login': r.get('refreshed_login', False)}
