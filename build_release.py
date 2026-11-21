"""Build the friend release: a clean app folder (embedded Python + toolkit) and, with Inno Setup, the installer.

    python build_release.py            stage only            -> F:\\Tools\\poe2kit-build\\stage
    python build_release.py --setup    stage + installer     -> F:\\Tools\\poe2kit-build\\out\\PoE2Toolkit-Setup-<ver>.exe
    python build_release.py --repo     stage + GitHub source copy -> F:\\Tools\\poe2kit-build\\repo (a git working tree)
    python build_release.py --gameart  stage + game art for the Linux package -> out/poe2-toolkit-gameart-<build>.tar.gz

Only an ALLOW-LIST of files is copied, so the author's vault, settings, screenshots, notes and database can never ship.
After staging, every text file is scanned for personal details; the build stops if any are found."""

import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from poe2kit import config  # noqa: E402

BUILD = r'F:\Tools\poe2kit-build'
STAGE = os.path.join(BUILD, 'stage')
OUT = os.path.join(BUILD, 'out')
PY_ZIP = os.path.join(BUILD, 'python-3.15.0-embed-amd64.zip')
ISCC = next((p for p in (r'F:\Tools\InnoSetup\ISCC.exe', r'C:\Program Files\Inno Setup 7\ISCC.exe',
                          r'C:\Program Files (x86)\Inno Setup 7\ISCC.exe') if os.path.exists(p)),
            r'C:\Program Files\Inno Setup 7\ISCC.exe')

FILES = ['monitor.py', 'server.py', 'tray.pyw', 'overlay.pyw', 'launcher.py', 'cli.py', 'leaguestart_pull.py', 'make_datapack.py',
         'launch_sweep.py', 'art_sweep.py', 'smoke_test.py', 'TROUBLESHOOTING.md']
DIRS = {'poe2kit': ('.py',), 'dashboard': ('.html', '.ico', '.png'), 'pobhost': ('.lua', '.c'),
        'datapack': ('.json',), 'bin': ('.exe',)}
RESEARCH = ['drop-rates.json', 'drop-rates.md']
# personal details that must never ship: regexes in release\\private_patterns.txt (that file never ships)
PRIVATE = os.path.join(HERE, 'release', 'private_patterns.txt')
FORBIDDEN = [l.strip() for l in open(PRIVATE, encoding='utf-8') if l.strip() and not l.startswith('#')] \
    if os.path.exists(PRIVATE) else []
# the author's first name in comments/notes is replaced with a neutral word in the staged copy
SOFTEN = [(r"\bEthan's\b", "the author's"), (r'\bEthan\b', 'the author')]


def stage():
    shutil.rmtree(STAGE, ignore_errors=True)
    app = os.path.join(STAGE, 'toolkit')
    os.makedirs(app)
    for f in FILES:
        shutil.copy2(os.path.join(HERE, f), app)
    for d, exts in DIRS.items():
        os.makedirs(os.path.join(app, d))
        for f in os.listdir(os.path.join(HERE, d)):
            if f.endswith(exts):
                shutil.copy2(os.path.join(HERE, d, f), os.path.join(app, d, f))
    os.makedirs(os.path.join(app, 'research'))
    for f in RESEARCH:
        shutil.copy2(os.path.join(HERE, 'research', f), os.path.join(app, 'research', f))
    # public icon: the original drawing if the author ever switches (USE_ORIGINAL_ICON), else the dashboard's icon
    shutil.copy2(os.path.join(HERE, 'release', 'github', 'CLAUDE-GUIDE.md'), os.path.join(STAGE, 'CLAUDE-GUIDE.md'))
    for f in ('README-friends.md', 'LICENSES.md'):
        if os.path.exists(os.path.join(HERE, 'release', f)):
            shutil.copy2(os.path.join(HERE, 'release', f), os.path.join(STAGE, f.replace('-friends', '')))
    # game art from the author's own extraction (newest build): pictures + index only, not the raw game tables
    idxs = sorted((os.path.join(config.GAMEFILES_DIR, d, 'art-index.json') for d in os.listdir(config.GAMEFILES_DIR)
                   if os.path.exists(os.path.join(config.GAMEFILES_DIR, d, 'art-index.json'))), key=os.path.getmtime)
    if idxs:
        src = os.path.dirname(idxs[-1])
        dst = os.path.join(app, 'gameart', os.path.basename(src))
        os.makedirs(dst)
        shutil.copy2(idxs[-1], dst)
        shutil.copytree(os.path.join(src, 'art'), os.path.join(dst, 'art'))
    # embedded Python, told where the toolkit lives (an embedded Python ignores PYTHONPATH and the script folder)
    py = os.path.join(STAGE, 'python')
    with zipfile.ZipFile(PY_ZIP) as z:
        z.extractall(py)
    pth = next(f for f in os.listdir(py) if f.endswith('._pth'))
    with open(os.path.join(py, pth), 'a', encoding='utf-8') as f:
        f.write('\n..\\toolkit\n')
    soften_and_scan(STAGE)
    print('staged', STAGE, f'{sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(STAGE) for f in fs) / 1e6:.1f} MB')


def soften_and_scan(root, skip_images=False):
    bad = []
    for r, ds, fs in os.walk(root):
        ds[:] = [d for d in ds if d != '.git']
        if os.path.basename(r) == 'python' or os.sep + 'python' + os.sep in r + os.sep:
            continue
        if os.sep + 'docs' + os.sep in r + os.sep:   # README screenshots show the author's characters on purpose
            continue
        for f in fs:
            if not f.endswith(('.py', '.pyw', '.html', '.json', '.md', '.lua', '.c', '.txt')):
                continue
            p = os.path.join(r, f)
            s = open(p, encoding='utf-8', errors='ignore').read()
            t = s
            for a, b in SOFTEN:
                t = re.sub(a, b, t)
            if t != s:
                open(p, 'w', encoding='utf-8').write(t)
            for pat in FORBIDDEN:
                for m in re.finditer(pat, t, re.I):
                    line = t.count('\n', 0, m.start()) + 1
                    bad.append(f'{os.path.relpath(p, root)}:{line}: {pat}')
    if bad:
        print('PERSONAL DETAILS FOUND, not building:')
        print('\n'.join(bad[:60]))
        sys.exit(1)
    print('privacy scan: clean')


def setup():
    if not os.path.exists(ISCC):
        print(f'Inno Setup not found at {ISCC}: install it there, then run with --setup again.')
        sys.exit(2)
    os.makedirs(OUT, exist_ok=True)
    iss = os.path.join(HERE, 'release', 'PoE2Toolkit.iss')
    p = subprocess.run([ISCC, f'/DAppVersion={config.VERSION}', f'/DStage={STAGE}', f'/O{OUT}', iss],
                       capture_output=True, text=True)
    print(p.stdout[-1500:], p.stderr[-1500:])
    if p.returncode:
        sys.exit(p.returncode)


REPO_DIR = os.path.join(BUILD, 'repo')
GITATTRIBUTES = '*.sh text eol=lf\n*.desktop.in text eol=lf\n'
REPO_EXTRA = ['build_release.py', 'make_datapack.py']
RELEASE_FILES = ['PoE2Toolkit.iss', 'LICENSES.md', 'README-friends.md', 'make_icon.py', 'icon.png', 'icon.ico']
GITIGNORE = '''__pycache__/
*.pyc
/vault/
settings.json
/patch-watch/
/screenshots/
*.zip
release/private_patterns.txt
gameart/
/linux/
'''


def repo():
    """Refresh the GitHub working tree from the staged app + build files (keeps its .git folder)."""
    os.makedirs(REPO_DIR, exist_ok=True)
    for name in os.listdir(REPO_DIR):
        if name not in ('.git',):
            p = os.path.join(REPO_DIR, name)
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    shutil.copytree(os.path.join(STAGE, 'toolkit'), REPO_DIR, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('gameart'))   # the art ships in the installer only
    for f in REPO_EXTRA:
        shutil.copy2(os.path.join(HERE, f), REPO_DIR)
    os.makedirs(os.path.join(REPO_DIR, 'release'), exist_ok=True)
    for f in RELEASE_FILES:
        if os.path.exists(os.path.join(HERE, 'release', f)):
            shutil.copy2(os.path.join(HERE, 'release', f), os.path.join(REPO_DIR, 'release', f))
    gh = os.path.join(HERE, 'release', 'github')
    if os.path.isdir(gh):   # README.md + docs/ for GitHub
        shutil.copytree(gh, REPO_DIR, dirs_exist_ok=True)
    open(os.path.join(REPO_DIR, '.gitignore'), 'w', encoding='utf-8').write(GITIGNORE)
    open(os.path.join(REPO_DIR, '.gitattributes'), 'w', encoding='utf-8').write(GITATTRIBUTES)
    soften_and_scan(REPO_DIR, skip_images=True)
    print('repo tree ready', REPO_DIR)


def gameart():
    """The game art as its own download for the Linux package (GitHub Actions adds it on a release):
    out/poe2-toolkit-gameart-<build>.tar.gz holding <build>/art-index.json + <build>/art/. Pictures only."""
    import tarfile
    src_root = os.path.join(STAGE, 'toolkit', 'gameart')
    builds = os.listdir(src_root) if os.path.isdir(src_root) else []
    if not builds:
        print('no game art staged (needs your own game-file extraction)')
        sys.exit(3)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f'poe2-toolkit-gameart-{builds[0]}.tar.gz')
    with tarfile.open(path, 'w:gz', compresslevel=6) as t:
        t.add(os.path.join(src_root, builds[0]), arcname=builds[0])
    print('game art', path, f'{os.path.getsize(path) / 1e6:.0f} MB')


if __name__ == '__main__':
    stage()
    if '--setup' in sys.argv:
        setup()
    if '--repo' in sys.argv:
        repo()
    if '--gameart' in sys.argv:
        gameart()
