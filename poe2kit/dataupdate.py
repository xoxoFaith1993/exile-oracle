"""Data that updates itself (R27, step 1): data-only packs from our own GitHub, separate from app releases.

Exile Oracle = code + data. New code still comes as a release (the update banner). New DATA (campaign rewards, atlas
strategies, research results, zone tables, the atlas tree...) comes as a small data pack, so every installed copy is
right again within hours of a patch, with nothing to install.

How a pack is made (on the author's PC): `python build_release.py --data` zips datapack/ with a manifest
(data_version, built, min_app, and every file's size + sha256) and it is posted as a GitHub *pre-release* tagged
`data-<version>` (pre-releases never show as the app's "latest" release, so the app update check ignores them).

How an app takes it (job `dataupdate`, every 6 hours; hourly for a day after the game updates):
  1. read the releases list (public API, no login) and find the newest `data-*` release whose manifest is newer than
     what we have and whose min_app <= this app's version;
  2. download its zip from github.com/<our repo> only, check the size, unpack into a NEW folder;
  3. check every file: listed in the manifest, size + sha256 match, every .json parses;
  4. only then switch `HOME/datapack-live/current.txt` to it, keep the previous pack for rollback, delete older ones,
     and clear the in-memory caches so the new data is used at once.
Anything wrong at any step: nothing changes. Data only, never code: a pack can't change what the app does.
"""

import hashlib
import json
import os
import shutil
import sys
import time
import urllib.request
import zipfile

from . import config, db

LIVE = os.path.join(config.HOME, 'datapack-live')
RELEASES = f'https://api.github.com/repos/{config.REPO}/releases?per_page=30'
ALLOWED = f'https://github.com/{config.REPO}/releases/download/'
MAX_ZIP = 60 * 1024 * 1024


def _ver(s):
    out = []
    for x in str(s or '').replace('data-', '').split('.'):
        try:
            out.append(int(x))
        except ValueError:
            out.append(0)
    return tuple(out)


def _req(url, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers={
        'User-Agent': config.user_agent(), 'Accept': 'application/vnd.github+json'}), timeout=timeout)


def shipped_manifest():
    try:
        return json.load(open(os.path.join(config.DATAPACK_DIR, 'manifest.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return {'data_version': '0', 'built': 0, 'source': 'shipped'}


def live_dir():
    """The folder of the downloaded pack in use, or None."""
    try:
        name = open(os.path.join(LIVE, 'current.txt'), encoding='utf-8').read().strip()
    except OSError:
        return None
    d = os.path.join(LIVE, name)
    return d if name and os.path.isfile(os.path.join(d, 'manifest.json')) else None


def current():
    """The data in use: the downloaded pack if it's newer than the one that shipped, else the shipped one."""
    d = live_dir()
    ship = shipped_manifest()
    if d:
        try:
            m = json.load(open(os.path.join(d, 'manifest.json'), encoding='utf-8'))
            if _ver(m.get('data_version')) > _ver(ship.get('data_version')):
                return dict(m, source='downloaded', folder=d)
        except (OSError, ValueError):
            pass
    return dict(ship, source='shipped', folder=config.DATAPACK_DIR)


def _clear_caches():
    """New data is used at once: empty every poe2kit module's in-memory data cache."""
    for name, mod in list(sys.modules.items()):
        if name.startswith('poe2kit.') and name != __name__:
            for attr in ('_cache', '_default', '_names_cache', '_pts_cache'):
                c = getattr(mod, attr, None)
                if isinstance(c, dict):
                    c.clear()


def _find(manifest_url=None):
    """(manifest, zip url) of the newest usable data pack, or (None, why)."""
    if manifest_url:   # tests: a manifest next to its zip
        m = json.loads(_req(manifest_url).read())
        return m, manifest_url.rsplit('/', 1)[0] + '/' + m['zip']
    rels = json.loads(_req(RELEASES).read())
    best = None
    for r in rels:
        tag = r.get('tag_name') or ''
        if not tag.startswith('data-') or r.get('draft'):
            continue
        assets = {a['name']: a for a in r.get('assets') or []}
        man = next((a for n, a in assets.items() if n == 'manifest.json'), None)
        z = next((a for n, a in assets.items() if n.endswith('.zip')), None)
        if man and z and (best is None or _ver(tag) > _ver(best[0])):
            best = (tag, man['browser_download_url'], z['browser_download_url'])
    if not best:
        return None, 'no data packs published yet'
    if not best[1].startswith(ALLOWED) or not best[2].startswith(ALLOWED):
        return None, 'data pack not on our own GitHub: ignored'
    return json.loads(_req(best[1]).read()), best[2]


def _sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def check(con, manifest_url=None, force=False):
    """Look for a newer data pack and install it if it passes every check. Returns what happened."""
    from . import updates
    if updates.dev_copy() and not (manifest_url or force):
        return {'checked': False, 'why': 'development copy: data comes from the source folder'}
    have = current()
    try:
        m, zurl = _find(manifest_url)
    except Exception as e:
        return _note(con, {'checked': time.time(), 'ok': False, 'why': f'could not check: {e}', 'have': have.get('data_version')})
    if not m:
        return _note(con, {'checked': time.time(), 'ok': True, 'why': zurl, 'have': have.get('data_version')})
    if _ver(m.get('data_version')) <= _ver(have.get('data_version')):
        return _note(con, {'checked': time.time(), 'ok': True, 'why': 'up to date', 'have': have.get('data_version')})
    if _ver(m.get('min_app')) > _ver(config.VERSION):
        return _note(con, {'checked': time.time(), 'ok': True, 'why': f"data {m['data_version']} needs app {m['min_app']}: update the app first",
                           'have': have.get('data_version'), 'waiting': m['data_version']})
    res = install(m, zurl)
    res.update(checked=time.time(), have=current().get('data_version'))
    return _note(con, res)


def install(m, zurl):
    os.makedirs(LIVE, exist_ok=True)
    ver = str(m['data_version'])
    tmp_zip = os.path.join(LIVE, f'.download-{ver}.zip')
    new_dir = os.path.join(LIVE, ver)
    tmp_dir = new_dir + '.unpacking'
    shutil.rmtree(tmp_dir, ignore_errors=True)
    try:
        with _req(zurl, timeout=300) as r, open(tmp_zip, 'wb') as f:
            total = 0
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_ZIP:
                    raise ValueError('pack larger than expected')
                f.write(chunk)
        if m.get('zip_size') and os.path.getsize(tmp_zip) != m['zip_size']:
            raise ValueError('download incomplete')
        with zipfile.ZipFile(tmp_zip) as z:
            names = set(z.namelist())
            want = set(m['files']) | {'manifest.json'}
            if names - want:
                raise ValueError(f'unexpected files in the pack: {sorted(names - want)[:3]}')
            for n in names:
                if os.path.isabs(n) or '..' in n.replace('\\', '/').split('/') or not n.endswith('.json'):
                    raise ValueError(f'bad file name in the pack: {n}')
            z.extractall(tmp_dir)
        for name, info in m['files'].items():
            p = os.path.join(tmp_dir, name)
            if not os.path.isfile(p) or os.path.getsize(p) != info['size'] or _sha(p) != info['sha256']:
                raise ValueError(f'{name} does not match the manifest')
            json.load(open(p, encoding='utf-8'))
        with open(os.path.join(tmp_dir, 'manifest.json'), 'w', encoding='utf-8') as f:   # the one we checked against
            json.dump({k: v for k, v in m.items() if k not in ('zip', 'zip_size')}, f, indent=1)
        shutil.rmtree(new_dir, ignore_errors=True)
        os.replace(tmp_dir, new_dir)
        prev = live_dir()
        with open(os.path.join(LIVE, 'current.txt.tmp'), 'w', encoding='utf-8') as f:
            f.write(ver)
        os.replace(os.path.join(LIVE, 'current.txt.tmp'), os.path.join(LIVE, 'current.txt'))
        keep = {ver, os.path.basename(prev) if prev else None}
        for d in os.listdir(LIVE):   # keep the new pack and the one before it (rollback)
            p = os.path.join(LIVE, d)
            if os.path.isdir(p) and d not in keep:
                shutil.rmtree(p, ignore_errors=True)
        if prev:
            with open(os.path.join(LIVE, 'previous.txt'), 'w', encoding='utf-8') as f:
                f.write(os.path.basename(prev))
        _clear_caches()
        return {'ok': True, 'installed': ver, 'files': len(m['files'])}
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return {'ok': False, 'why': f'data pack {ver} not used: {e}'}
    finally:
        try:
            os.remove(tmp_zip)
        except OSError:
            pass


def rollback():
    """Go back to the pack before (the player or the doctor can ask for this)."""
    try:
        prev = open(os.path.join(LIVE, 'previous.txt'), encoding='utf-8').read().strip()
    except OSError:
        return {'ok': False, 'why': 'no earlier data pack kept'}
    if not os.path.isfile(os.path.join(LIVE, prev, 'manifest.json')):
        return {'ok': False, 'why': 'the earlier data pack is gone'}
    with open(os.path.join(LIVE, 'current.txt'), 'w', encoding='utf-8') as f:
        f.write(prev)
    _clear_caches()
    return {'ok': True, 'now': prev}


def _note(con, info):
    db.kv_set(con, 'dataupdate', json.dumps(info))
    con.commit()
    return info


def status(con):
    cur = current()
    try:
        last = json.loads(db.kv_get(con, 'dataupdate') or '{}')
    except ValueError:
        last = {}
    return {'version': cur.get('data_version'), 'source': cur.get('source'), 'built': cur.get('built'),
            'files': len(cur.get('files') or {}), 'last_check': last}


def make_manifest(folder, data_version, min_app):
    """For build_release.py: the manifest of a data pack folder (every .json with size + sha256)."""
    files = {}
    for n in sorted(os.listdir(folder)):
        p = os.path.join(folder, n)
        if n.endswith('.json') and n != 'manifest.json' and os.path.isfile(p):
            files[n] = {'size': os.path.getsize(p), 'sha256': _sha(p)}
    return {'data_version': data_version, 'built': int(time.time()), 'min_app': min_app, 'files': files}
