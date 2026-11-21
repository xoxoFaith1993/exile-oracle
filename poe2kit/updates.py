"""Update check for installed copies: asks GitHub's public Releases API (no login) whether a newer version of the
installer exists, and on the player's click downloads it and starts it (the installer closes the running app first).
The author's own development copy (F:\\PoE2Toolkit) never updates itself."""

import json
import os
import re
import subprocess
import time
import urllib.request

from . import config, db

API = f'https://api.github.com/repos/{config.REPO}/releases/latest'


def _ver(s):
    return tuple(int(x) for x in re.findall(r'\d+', s or '0')[:3])


def dev_copy():
    return os.path.normcase(os.path.normpath(config.HOME)) == os.path.normcase(r'F:\PoE2Toolkit')


def check(con):
    if dev_copy():
        return {'checked': False, 'why': 'development copy'}
    req = urllib.request.Request(API, headers={'User-Agent': config.user_agent(), 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        rel = json.loads(r.read())
    asset = next((a for a in rel.get('assets', []) if a['name'].lower().endswith('.exe')), None)
    info = {'checked': time.time(), 'current': config.VERSION, 'latest': (rel.get('tag_name') or '').lstrip('v'),
            'page': rel.get('html_url'), 'notes': (rel.get('body') or '')[:2000],
            'asset': asset and {'name': asset['name'], 'url': asset['browser_download_url'], 'size': asset['size']}}
    info['available'] = bool(asset) and _ver(info['latest']) > _ver(config.VERSION)
    db.kv_set(con, 'update', json.dumps(info))
    con.commit()
    return info


def status(con):
    try:
        return json.loads(db.kv_get(con, 'update', '{}') or '{}')
    except ValueError:
        return {}


def install(con):
    """Download the new installer (the player clicked the button) and start it."""
    info = status(con)
    a = info.get('asset')
    if not (info.get('available') and a and a['url'].startswith('https://github.com/' + config.REPO + '/')):
        return {'ok': False, 'why': 'no update available'}
    d = os.path.join(config.HOME, 'updates')
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, os.path.basename(a['name']))
    req = urllib.request.Request(a['url'], headers={'User-Agent': config.user_agent()})
    with urllib.request.urlopen(req, timeout=300) as r, open(path, 'wb') as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    if os.path.getsize(path) != a['size']:
        return {'ok': False, 'why': 'download incomplete, try again'}
    subprocess.Popen([path], creationflags=0x00000008)  # DETACHED: the installer closes this app, then updates it
    return {'ok': True, 'file': path}
