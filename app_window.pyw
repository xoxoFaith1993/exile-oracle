"""The Exile Oracle window: the dashboard in a native window of its own (Windows WebView2 through pywebview), so it
looks and behaves like an app (its own name and icon in the taskbar, no browser menus), not a web page in Edge.

Started by poe2kit.appwindow (tray, shortcut, launcher). If pywebview or WebView2 is missing it falls back to the
Edge / Chrome app window."""

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from poe2kit import config  # noqa: E402

PORT = int(os.environ.get('POE2KIT_PORT', '47830'))
URL = f'http://127.0.0.1:{PORT}/'
TITLE = 'Exile Oracle'
ICON = os.path.join(HERE, 'dashboard', 'poe2kit.ico')


def _set_icon(window):
    """Give the window (and its taskbar button) the Exile Oracle eye instead of Python's icon."""
    if os.name != 'nt' or not os.path.exists(ICON):
        return
    from ctypes import wintypes as wt
    u32 = ctypes.windll.user32
    u32.LoadImageW.restype = wt.HANDLE   # 64-bit handles: don't let ctypes cut them to 32 bits
    u32.LoadImageW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, wt.UINT, ctypes.c_int, ctypes.c_int, wt.UINT]
    u32.SendMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    try:   # this window's own handle (an Edge app window may have the same title)
        hwnd = int(window.native.Handle.ToInt64())
    except Exception:
        hwnd = u32.FindWindowW(None, TITLE)
    if not hwnd:
        return
    for size, which in ((16, 0), (32, 1), (48, 1)):   # ICON_SMALL = 0, ICON_BIG = 1
        h = u32.LoadImageW(None, ICON, 1, size, size, 0x10)   # IMAGE_ICON, LR_LOADFROMFILE
        if h:
            u32.SendMessageW(hwnd, 0x0080, which, h)   # WM_SETICON


def main():
    if os.name == 'nt':
        try:   # its own taskbar group, not "Python"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('ExileOracle.Dashboard')
        except Exception:
            pass
    try:
        import webview
    except ImportError:
        return _fallback()
    w = webview.create_window(TITLE, URL, width=1400, height=950, min_size=(900, 600), background_color='#0c0a09',
                              text_select=True)
    w.events.shown += lambda: _set_icon(w)
    try:
        webview.start(gui='edgechromium' if os.name == 'nt' else None, private_mode=False,
                      storage_path=os.path.join(config.HOME, 'webview'))
    except Exception:
        _fallback()


def _fallback():
    from poe2kit import appwindow
    cmd = appwindow.command()
    if cmd:
        import subprocess
        subprocess.Popen(cmd, creationflags=0x08000000 if os.name == 'nt' else 0)
    else:
        import webbrowser
        webbrowser.open(URL)


if __name__ == '__main__':
    main()
