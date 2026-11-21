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
    check(config.HOME == os.environ['POE2KIT_HOME'], f'home folder {config.HOME}')
    print('     game folder :', config.poe2_dir())
    print('     Client.txt  :', config.client_log())
    print('     PoB folder  :', osutil.find_documents('Path of Building (PoE2)'))
    print('     Claude      :', claudelink.status()['config'])
    check(osutil.pid_alive(os.getpid()), 'process check sees itself')


def get(url, timeout=30):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read()


def monitor():
    import launcher
    t0 = time.time()
    launcher.main(['--background'])
    check(launcher.up(), f'monitor started ({time.time() - t0:.1f} s)')
    if not launcher.up():
        from poe2kit import config
        log = os.path.join(config.LOG_DIR, 'monitor.log')
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
                if e.code == 503 and j.get('setup'):   # first-start downloads still running: an honest answer
                    check(True, f'/api/{v} (waits for {", ".join(j["waiting_for"])})')
                else:
                    check(False, f'/api/{v}: {e.code} {body[:400].decode("utf-8", "replace")}')
            except Exception as e:
                check(False, f'/api/{v}: {e}')
    finally:
        launcher.stop()
        time.sleep(1)
        check(not launcher.up(), 'monitor stopped')


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


if __name__ == '__main__':
    print('python', sys.version.split()[0], 'on', sys.platform, '| home', os.environ['POE2KIT_HOME'])
    compile_all()
    detection()
    monitor()
    mcp()
    print(f'\n{len(fails)} failed' if fails else '\nall passed')
    sys.exit(1 if fails else 0)
