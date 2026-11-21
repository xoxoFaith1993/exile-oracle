"""End-to-end test of data that updates itself (R27), in a throwaway data folder. Developer tool, never shipped.

Makes two test packs from datapack/ (one with a changed campaign.json), serves them from a local web server, and
checks: install + the new file is really used, a tampered pack is refused, the "go back" button, an older pack is
ignored. Run: python release/test_dataupdate.py"""

import functools
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
base = os.environ.get('EO_TEST_DIR') or (r'F:\Tools\poe2kit-build\test-dataupdate' if os.path.isdir('F:\\') else tempfile.mkdtemp())
shutil.rmtree(base, ignore_errors=True)
os.makedirs(base)
os.environ['POE2KIT_HOME'] = os.path.join(base, 'home')
sys.path.insert(0, HERE)
from poe2kit import config, db, dataupdate  # noqa: E402

SERVE = os.path.join(base, 'serve')
fails = []


def check(ok, what):
    print(('ok   ' if ok else 'FAIL ') + what)
    if not ok:
        fails.append(what)


def make_pack(ver, change=None, tamper=False):
    src = os.path.join(base, 'src-' + ver)
    shutil.copytree(os.path.join(HERE, 'datapack'), src)
    for f in os.listdir(src):
        if not f.endswith('.json') or f == 'manifest.json':
            os.remove(os.path.join(src, f))
    if change:
        p = os.path.join(src, 'campaign.json')
        d = json.load(open(p, encoding='utf-8'))
        d['meta']['researched'] = change
        json.dump(d, open(p, 'w', encoding='utf-8'))
    man = dataupdate.make_manifest(src, ver, '0.1.0')
    d = os.path.join(SERVE, ver)
    os.makedirs(d)
    zname = f'pack-{ver}.zip'
    with zipfile.ZipFile(os.path.join(d, zname), 'w') as z:
        for n in man['files']:
            data = open(os.path.join(src, n), 'rb').read()
            if tamper and n == 'campaign.json':
                data = data.replace(b'Campaign', b'Kampaign', 1)
            z.writestr(n, data)
    man['zip'], man['zip_size'] = zname, os.path.getsize(os.path.join(d, zname))
    json.dump(man, open(os.path.join(d, 'manifest.json'), 'w'))
    return f'http://127.0.0.1:{PORT}/{ver}/manifest.json'


os.makedirs(SERVE)
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=SERVE))
srv.RequestHandlerClass.log_message = lambda *a: None
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

con = db.connect()
check(dataupdate.current()['source'] == 'shipped', 'starts on the shipped data')
u1 = make_pack('2099.01.01.1', change='TEST-1')
r = dataupdate.check(con, manifest_url=u1)
config._live['at'] = 0
check(r.get('installed') == '2099.01.01.1', f'newer pack installed ({r})')
from poe2kit import campaign  # noqa: E402
check(campaign.data()['meta']['researched'] == 'TEST-1', 'the new data is really used (campaign.json from the pack)')
bad = make_pack('2099.01.01.2', change='TEST-2', tamper=True)
r = dataupdate.check(con, manifest_url=bad)
config._live['at'] = 0
check(not r.get('ok') and 'does not match' in (r.get('why') or ''), f'tampered pack refused ({r.get("why")})')
check(dataupdate.current()['data_version'] == '2099.01.01.1', 'still on the good pack after the refusal')
u3 = make_pack('2099.01.01.3', change='TEST-3')
r = dataupdate.check(con, manifest_url=u3)
config._live['at'] = 0
campaign._cache.clear()
check(r.get('installed') == '2099.01.01.3' and campaign.data()['meta']['researched'] == 'TEST-3', 'a second update installs')
r = dataupdate.rollback()
config._live['at'] = 0
campaign._cache.clear()
check(r.get('ok') and campaign.data()['meta']['researched'] == 'TEST-1', f'go back to the previous data ({r})')
old = make_pack('2098.01.01.1', change='OLD')
r = dataupdate.check(con, manifest_url=old)
check(r.get('why') == 'up to date', 'an older pack is ignored')
dirs = [d for d in os.listdir(dataupdate.LIVE) if os.path.isdir(os.path.join(dataupdate.LIVE, d))]
check(len(dirs) <= 2, f'only the current and previous packs are kept ({dirs})')
con.close()
srv.shutdown()
shutil.rmtree(base, ignore_errors=True)
print(f'\n{len(fails)} failed' if fails else '\nall passed')
sys.exit(1 if fails else 0)
