"""Break-everything test (the author, 2026-11-21: "We need fail safes for absolutely everything").

Runs every Claude tool and every dashboard call under bad conditions and lists what a player would see:
  - a brand-new, empty data folder (no prices, no builds, no history);
  - no Path of Building, no game folder;
  - no internet (every request goes to a dead proxy);
  - three kinds of input per call: nothing, sensible, nonsense (wrong types, ids that don't exist).
A result is BAD when the player would get a raw Python error ("KeyError: 'query'", a traceback, an HTTP 500) or the
call hangs, instead of a plain message that says what's missing and what to do.

    python release/chaos_test.py            # everything (about a minute)
    python release/chaos_test.py --quick    # Claude tools only
Exit code 1 if anything is BAD. Runs in a temporary folder; touches nothing of yours."""

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix='poe2kit-chaos-')
os.environ['POE2KIT_HOME'] = TMP
os.environ['POE2KIT_POB'] = os.path.join(TMP, 'no-pob')
os.environ['POE2KIT_PORT'] = '47898'
for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy'):
    os.environ[k] = 'http://127.0.0.1:9'   # nothing listens there: every web request fails fast
os.environ['NO_PROXY'] = os.environ['no_proxy'] = '127.0.0.1,localhost'
sys.path.insert(0, HERE)

from poe2kit import config  # noqa: E402

config.save_settings({'poe2_dir': os.path.join(TMP, 'no-game'), 'live_trade': True})

RAW = re.compile(r'\b(KeyError|TypeError|AttributeError|IndexError|ValueError|NameError|UnboundLocalError|'
                 r'ZeroDivisionError|sqlite3\.\w+|OperationalError|JSONDecodeError|RecursionError|'
                 r'FileNotFoundError|PermissionError|AssertionError|StopIteration|Traceback)\b')
TIMEOUT = 40

SENSIBLE = {
    'query': 'Divine', 'item': 'Omen of Light', 'name': 'Mageblood', 'type': 'Utility Belt', 'league': None,
    'build_id': 1, 'a_build_id': 1, 'b_build_id': 2, 'id': 1, 'pob_code': 'eNqrVkrOz8nJTEpVslJQMjQ1NDA0',
    'text': 'Increased the drop rate of Fracturing Orbs.', 'view': 'market', 'mode': 'omen', 'action': 'list',
    'class_name': 'Witch', 'ascendancies': 'Lich,Blood Mage', 'item_text': 'Rarity: Rare\nDoom Song\nGold Ring\n--------\n+30 to maximum Life',
    'slot': 'Ring 1', 'base': 'Gold Ring', 'mods': '+30 to maximum Life', 'level': 20, 'strategy': 'Breach',
    'part': 'acts', 'hours': 24, 'limit': 3, 'budget_div': 10, 'target': 5, 'unit': 'div',
}


def nonsense(props):
    out = {}
    for k, s in props.items():
        t = (s or {}).get('type')
        out[k] = {'number': 'lots', 'integer': 'x', 'boolean': 'maybe', 'object': 'zzz', 'array': 42}.get(t, 99999 if 'id' in k else {'a': 1})
    return out


def run_with_timeout(fn):
    box = {}

    def go():
        try:
            box['r'] = fn()
        except BaseException as e:   # noqa: BLE001
            box['e'] = e
    t = threading.Thread(target=go, daemon=True)
    t.start()
    t.join(TIMEOUT)
    if t.is_alive():
        return 'HANG', None
    return box.get('e'), box.get('r')


def tools():
    import server
    bad, n = [], 0
    for name, _desc, schema, fn in server.TOOLS:
        props = (schema or {}).get('properties') or {}
        cases = {'nothing': {}, 'sensible': {k: SENSIBLE[k] for k in props if k in SENSIBLE and SENSIBLE[k] is not None},
                 'nonsense': nonsense(props)}
        for label, args in cases.items():
            n += 1
            # what the MCP layer would send back to the AI app
            err, res = run_with_timeout(lambda: server._dispatch(name, args))
            if err == 'HANG':
                bad.append((name, label, f'hung for {TIMEOUT}+ s'))
                continue
            if err is not None:
                bad.append((name, label, f'escaped the tool layer: {type(err).__name__}: {err}'))
                continue
            text, is_err = res
            head = (text or '').split('\n[for you')[0]
            if is_err and (RAW.search(head) or "didn't expect" in head):
                bad.append((name, label, (text or '').split('assistant: ')[-1][:140].replace('\n', ' ')))
    return bad, n


def judge(st, body):
    """None if the player would see a plain message, else why not."""
    if st in ('HANG', 'DOWN'):
        return f'{st}: {body[:120]}'
    try:
        j = json.loads(body)
    except ValueError:
        return f'{st}: not JSON: {body[:120]}' if st >= 400 else None
    head = j.get('error') if isinstance(j, dict) else None
    if st >= 500 and not (isinstance(j, dict) and (j.get('setup') or j.get('kind') in ('offline', 'missing'))):
        return f"{st}: {(j.get('detail') if isinstance(j, dict) else None) or head}"[:200]
    if isinstance(head, str) and RAW.search(head):
        return f'{st}: {head[:160]}'
    return None


def routes():
    src = open(os.path.join(HERE, 'monitor.py'), encoding='utf-8').read()
    gets = sorted(set(re.findall(r"if path == '(/api/[^']+)'", src)))
    posts = sorted(set(re.findall(r"u\.path == '(/api/[^']+)'", src)) |
                   {p for grp in re.findall(r"u\.path in \(([^)]*)\)", src) for p in re.findall(r"'(/api/[^']+)'", grp)})
    skip = {'/api/update/install', '/api/claude/connect', '/api/claude/disconnect', '/api/open', '/api/wanted/browse',
            '/api/ask/open', '/api/report', '/api/datapack/publish', '/api/vault/open_ninja'}   # open windows / change the PC
    p = subprocess.Popen([sys.executable, '-u', os.path.join(HERE, 'monitor.py'), '--serve'], cwd=HERE,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=os.environ.copy())
    base = f"http://127.0.0.1:{os.environ['POE2KIT_PORT']}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        for _ in range(60):
            try:
                socket.create_connection(('127.0.0.1', int(os.environ['POE2KIT_PORT'])), 1).close()
                break
            except OSError:
                time.sleep(0.5)
        bad, n = [], 0

        def call(method, path, body=None):
            req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                         method=method, headers={'Content-Type': 'application/json'})
            try:
                with opener.open(req, timeout=TIMEOUT) as r:
                    return r.status, r.read().decode('utf-8', 'replace')
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode('utf-8', 'replace')
            except Exception as e:   # noqa: BLE001
                return 'HANG' if 'timed out' in str(e) else 'DOWN', str(e)
        for path in gets:
            if path in skip:
                continue
            for label, q in (('nothing', ''), ('nonsense', '?id=zzz&item=zzz&build_id=zzz&q=zzz&league=zzz&hours=x&limit=x&day=x')):
                n += 1
                st, body = call('GET', path + q)
                why = judge(st, body)
                if why:
                    bad.append(('GET ' + path, label, why))
        for path in posts:
            if path in skip:
                continue
            for label, b in (('nothing', {}), ('nonsense', {'id': 'zzz', 'name': 99999, 'text': {'a': 1}, 'target': 'lots',
                                                            'build_id': 'zzz', 'listing': 5, 'url': 'file:///C:/'})):
                n += 1
                st, body = call('POST', path, b)
                why = judge(st, body)
                if why:
                    bad.append(('POST ' + path, label, why))
        return bad, n
    finally:
        p.kill()


def main():
    t0 = time.time()
    bad, n = tools()
    if '--quick' not in sys.argv:
        b2, n2 = routes()
        bad += b2
        n += n2
    for what, label, msg in bad:
        print(f'BAD  {what} [{label}]  {msg}')
    print(f'\n{len(bad)} bad of {n} calls ({time.time() - t0:.0f} s, data folder {TMP})')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
