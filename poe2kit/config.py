"""Paths and settings for the PoE 2 toolkit.

Everything the toolkit writes lives under one HOME folder:
  - POE2KIT_HOME environment variable, if set;
  - else F:\\PoE2Toolkit if it exists (the author's original install, keeps working unchanged);
  - else %LOCALAPPDATA%\\PoE2Toolkit (a fresh install on a friend's PC).
User settings are HOME\\settings.json (the app folder may be read-only, e.g. under Program Files).
A per-user profile (class, ascendancy, main build, watch words) replaces anything specific to one player."""

import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # the app folder (code, dashboard, pobhost)

VERSION = '0.2.0'
REPO = 'xoxoFaith1993/poe2-toolkit'   # GitHub: releases + update check


def _home():
    h = os.environ.get('POE2KIT_HOME')
    if h:
        return h
    if os.name != 'nt':   # Linux / Steam Deck: XDG data folder
        base = os.environ.get('XDG_DATA_HOME') or os.path.join(os.path.expanduser('~'), '.local', 'share')
        return os.path.join(base, 'poe2toolkit')
    if os.path.isdir(r'F:\PoE2Toolkit'):
        return r'F:\PoE2Toolkit'
    return os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'PoE2Toolkit')


HOME = _home()
DATA_DIR = os.environ.get('POE2KIT_DATA', os.path.join(HOME, 'data'))
DB_PATH = os.path.join(DATA_DIR, 'poe2kit.db')
LOG_DIR = os.path.join(HOME, 'logs')
TOOLS_DIR = os.path.join(HOME, 'tools')
POB_DIR = os.environ.get('POE2KIT_POB', os.path.join(HOME, 'pob'))
GAMEFILES_DIR = os.path.join(HOME, 'gamefiles')
IMG_DIR = os.path.join(DATA_DIR, 'img')
LOCK_PATH = os.path.join(HOME, 'monitor.lock')
SCHEMA_PATH = os.environ.get('POE2KIT_SCHEMA', os.path.join(DATA_DIR, 'schema', 'schema-poe2.min.json'))
# the author's vault sits next to the code; a fresh install keeps its vault in HOME.
VAULT_DIR = os.path.join(ROOT, 'vault') if os.path.isdir(os.path.join(ROOT, 'vault')) else os.path.join(HOME, 'vault')
SETTINGS_PATH = os.path.join(HOME, 'settings.json')
LEGACY_SETTINGS = os.path.join(ROOT, 'settings.json')

DEFAULTS = {
    # Contact for API User-Agents. Never a person's email unless they add it themselves.
    'contact': '',
    # Where the app is published (named in the User-Agent so GGG / poe.ninja can see what the traffic is).
    'homepage': '',
    # None = follow poe.ninja's current challenge league automatically.
    'league': None,
    # Minimum minutes between polls of the same URL (poe.ninja PoE 2 data refreshes ~hourly).
    'poll_minutes': 30,
    # PoE 2 install folder; None = detect (Steam libraries, then the standalone GGG folder).
    'poe2_dir': None,
    # The player's profile; set in the dashboard's setup. None until then.
    'profile': None,
}

for d in (HOME, DATA_DIR, LOG_DIR, TOOLS_DIR):
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass


def settings():
    s = dict(DEFAULTS)
    for p in (LEGACY_SETTINGS, SETTINGS_PATH):
        try:
            with open(p, encoding='utf-8') as f:
                s.update(json.load(f))
        except (OSError, ValueError):
            pass
    return s


def save_settings(changes):
    cur = {}
    try:
        with open(SETTINGS_PATH, encoding='utf-8') as f:
            cur = json.load(f)
    except (OSError, ValueError):
        pass
    cur.update(changes)
    with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(cur, f, indent=1)
    return cur


def user_agent():
    s = settings()
    ua = f'poe2-toolkit/{VERSION}'
    extra = [x for x in (s.get('homepage'), (f"contact: {s['contact']}" if s.get('contact') else None)) if x]
    if extra:
        ua += f' ({"; ".join(extra)})'
    return ua


# ---------------- profile ----------------

GENERIC_WATCH = ['energy shield', 'spirit', 'critical hit chance']


def profile():
    """The player's choices. the author's original install keeps its Witch / Blood Mage defaults."""
    p = settings().get('profile')
    if p:
        return p
    if os.path.normcase(os.path.normpath(HOME)) == os.path.normcase(r'F:\PoE2Toolkit'):
        return {'name': 'the author', 'class': 'Witch', 'ascendancy': 'Blood Mage', 'path': ['Lich', 'Blood Mage'],
                'watch': ['blood mage', 'witch', 'corrupted blood', 'sanguimancy', 'life remnants', 'spell critical',
                          'critical hit chance', 'eldritch battery', 'mind over matter', 'energy shield', 'spirit',
                          'lightning', 'cast on critical'], 'configured': True}
    return {'name': None, 'class': None, 'ascendancy': None, 'path': [], 'watch': [], 'configured': False}


def watch_words():
    p = profile()
    words = [w.lower() for w in (p.get('watch') or [])]
    for k in ('class', 'ascendancy'):
        if p.get(k) and p[k].lower() not in words:
            words.append(p[k].lower())
    return words or GENERIC_WATCH


# ---------------- PoE 2 install ----------------

STEAM_APPID = '2694490'


def _steam_roots_linux():
    """Steam on Linux: native, the ~/.steam links, Flatpak Steam. (Steam Deck = native.)"""
    home = os.path.expanduser('~')
    return [os.path.join(home, '.steam', 'steam'), os.path.join(home, '.steam', 'root'),
            os.path.join(home, '.local', 'share', 'Steam'),
            os.path.join(home, '.var', 'app', 'com.valvesoftware.Steam', '.local', 'share', 'Steam'),
            os.path.join(home, '.var', 'app', 'com.valvesoftware.Steam', 'data', 'Steam')]


def _steam_libraries():
    libs = []
    roots = []
    if os.name != 'nt':
        roots = _steam_roots_linux()
    try:
        import winreg
        for hive, key in ((winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam'),
                          (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam')):
            try:
                with winreg.OpenKey(hive, key) as k:
                    for name in ('SteamPath', 'InstallPath'):
                        try:
                            roots.append(winreg.QueryValueEx(k, name)[0])
                        except OSError:
                            pass
            except OSError:
                pass
    except ImportError:
        pass
    if os.name == 'nt':
        roots += [r'C:\Program Files (x86)\Steam', r'C:\Program Files\Steam']
    for r in roots:
        vdf = os.path.join(r, 'steamapps', 'libraryfolders.vdf')
        if os.path.exists(vdf):
            txt = open(vdf, encoding='utf-8', errors='ignore').read()
            libs += [p.replace('\\\\', '\\') if os.name == 'nt' else p
                     for p in re.findall(r'"path"\s+"([^"]+)"', txt)]
            libs.append(r)
    if os.name == 'nt':   # drive roots people commonly use
        libs += [f'{d}:\\SteamLibrary' for d in 'CDEFGH']
    else:                 # Steam Deck SD cards and other mounted drives
        import glob as _g
        libs += _g.glob('/run/media/*/*/SteamLibrary') + _g.glob('/run/media/*/*') + _g.glob('/media/*/*/SteamLibrary')
    seen, out = set(), []
    for l in libs:
        n = os.path.normcase(os.path.normpath(l))
        if n not in seen:
            seen.add(n)
            out.append(l)
    return out


def steam_manifest():
    """Path of PoE 2's Steam appmanifest (install state), or None."""
    for lib in _steam_libraries():
        acf = os.path.join(lib, 'steamapps', f'appmanifest_{STEAM_APPID}.acf')
        if os.path.exists(acf):
            return acf
    return None


def _is_game(p):
    """A real install (not a leftover logs folder from an old one)."""
    return os.path.isdir(p) and any(os.path.exists(os.path.join(p, x)) for x in
                                    ('Bundles2', 'Content.ggpk', 'PathOfExileSteam.exe', 'PathOfExile.exe'))


def poe2_dir():
    """The Path of Exile 2 install folder, or None. Steam's manifest wins; leftover folders are skipped."""
    s = settings().get('poe2_dir')
    if s and os.path.isdir(s):
        return s
    acf = steam_manifest()
    if acf:
        p = os.path.join(os.path.dirname(acf), 'common', 'Path of Exile 2')
        if _is_game(p):
            return p
    for lib in _steam_libraries():
        p = os.path.join(lib, 'steamapps', 'common', 'Path of Exile 2')
        if _is_game(p):
            return p
    if os.name == 'nt':
        for p in (r'C:\Program Files (x86)\Grinding Gear Games\Path of Exile 2',
                  r'C:\Program Files\Grinding Gear Games\Path of Exile 2'):
            if _is_game(p):
                return p
    return None


def client_log():
    d = poe2_dir()
    for name in ('Client.txt', 'KakaoClient.txt'):
        if d and os.path.exists(os.path.join(d, 'logs', name)):
            return os.path.join(d, 'logs', name)
    return None


def poe2x():
    """The game-file extractor, if present (HOME\\tools, or the author's build in the poe2-offline project).
    Windows only: the bundled game art covers Linux."""
    if os.name != 'nt':
        return None
    for p in (os.path.join(TOOLS_DIR, 'poe2x', 'poe2x.exe'), os.path.join(TOOLS_DIR, 'poe2x.exe'),
              r'D:\Modding\poe2-offline\tools\poe2x\bin\poe2x.exe'):
        if os.path.exists(p):
            return p
    return None


DATAPACK_DIR = os.path.join(ROOT, 'datapack')


def data_file(name):
    """A data file from this install's own data folder, else the shipped data pack, else None."""
    for d in (DATA_DIR, DATAPACK_DIR):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


def newest_gamefiles(sub):
    """Newest game build folder's file or folder `sub` (e.g. 'tables\\worldareas.json'), or None."""
    hits = sorted(glob.glob(os.path.join(GAMEFILES_DIR, '*', sub)), key=os.path.getmtime)
    return hits[-1] if hits else None


def is_dev_copy():
    """the author's own development copy (F:\\PoE2Toolkit): never self-updates; some opt-in features default on."""
    return os.path.normcase(os.path.normpath(HOME)) == os.path.normcase(r'F:\PoE2Toolkit')
