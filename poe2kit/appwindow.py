"""Open the dashboard in its own app window, never a browser tab.

Windows: Edge in app mode with its own profile (HOME/edge-app). If that window is already open it is brought to the
front instead of opening a second one. Linux: the first Chromium-family browser found (Edge, Chrome, Chromium,
Brave, also as Flatpaks) in app mode. Without one, or with the setting dashboard_window='browser', it opens in the
default browser as before."""

import os
import shutil
import subprocess
import webbrowser

from . import config, osutil

URL = 'http://127.0.0.1:47830/'
TITLE = 'Exile Oracle'          # the dashboard page's <title>; the app window takes it as its own
SIZE = '1400,950'
WIN_BROWSERS = [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
                os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe'),
                r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe')]
LINUX_BROWSERS = ['microsoft-edge', 'microsoft-edge-stable', 'google-chrome', 'google-chrome-stable',
                  'chromium', 'chromium-browser', 'brave-browser', 'brave']
LINUX_FLATPAKS = ['com.microsoft.Edge', 'com.google.Chrome', 'org.chromium.Chromium', 'com.brave.Browser']


def mode():
    """'app' (own window, the default) or 'browser' (a tab in the default browser)."""
    return 'browser' if config.settings().get('dashboard_window') == 'browser' else 'app'


def _flags(prof):
    # no account sync and no extensions: Edge otherwise signs a new profile into the Windows account and syncs its
    # extensions, which can then run in the background
    f = [f'--app={URL}', f'--window-size={SIZE}', '--no-first-run', '--no-default-browser-check', '--disable-sync',
         '--disable-extensions']
    return f + ([f'--user-data-dir={prof}'] if prof else [])


def _find_window():
    """The open dashboard app window on Windows (exact title, a Chromium window), or None."""
    import ctypes
    from ctypes import wintypes as wt
    u32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def each(hwnd, _):
        if not u32.IsWindowVisible(hwnd) and not u32.IsIconic(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(256)
        u32.GetWindowTextW(hwnd, buf, 256)
        if buf.value != TITLE:
            return True
        cls = ctypes.create_unicode_buffer(64)
        u32.GetClassNameW(hwnd, cls, 64)
        if cls.value.startswith('Chrome_WidgetWin'):
            found.append(hwnd)
            return False
        return True

    u32.EnumWindows(each, 0)
    return found[0] if found else None


def _raise(hwnd):
    import ctypes
    u32 = ctypes.windll.user32
    if u32.IsIconic(hwnd):
        u32.ShowWindow(hwnd, 9)        # SW_RESTORE
    u32.ShowWindow(hwnd, 5)            # SW_SHOW
    u32.SetForegroundWindow(hwnd)


def _linux_cmd(prof):
    for name in LINUX_BROWSERS:
        exe = shutil.which(name)
        if exe:
            return [exe] + _flags(prof)
    fp = shutil.which('flatpak')
    if fp:
        for app in LINUX_FLATPAKS:
            try:
                ok = subprocess.run([fp, 'info', app], capture_output=True, timeout=10).returncode == 0
            except Exception:
                ok = False
            if ok:   # a Flatpak browser keeps its own profile inside its sandbox
                return [fp, 'run', app] + _flags(None)
    return None


def command():
    """The command that opens the app window here, or None (then the default browser is used)."""
    prof = os.path.join(config.HOME, 'edge-app')
    if osutil.IS_WIN:
        exe = next((p for p in WIN_BROWSERS if os.path.exists(p)), None)
        return [exe] + _flags(prof) if exe else None
    return _linux_cmd(os.path.join(config.HOME, 'browser-app'))


def open_dashboard():
    """Show the dashboard: bring the open window forward, or open a new app window (or a browser tab).
    Returns 'raised', 'app' or 'browser'."""
    if mode() == 'app':
        if osutil.IS_WIN:
            try:
                hwnd = _find_window()
            except Exception:
                hwnd = None
            if hwnd:
                _raise(hwnd)
                return 'raised'
        cmd = command()
        if cmd:
            try:
                kw = {'creationflags': osutil.NO_WINDOW} if osutil.IS_WIN else {'start_new_session': True}
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)
                return 'app'
            except OSError:
                pass
    webbrowser.open(URL)
    return 'browser'
