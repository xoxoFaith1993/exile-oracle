"""PoE 2 Toolkit price-check overlay (Windows).

Press Ctrl+C on an item in Path of Exile 2 (the game copies the item's text). This program sees PoE item text on the
clipboard while the game is the window in front, sends it to the toolkit's monitor to be priced, and shows a small
always-on-top popup in the middle of the screen. Click back into the game, or press Esc, and it hides.

It never sends keys or clicks to the game and never reads the game's memory: it only reads the clipboard.
The popup is a borderless Edge app window showing http://127.0.0.1:47830/overlay. The game must run in windowed
fullscreen (borderless) for a popup to show over it.

    pythonw overlay.pyw                  run (the monitor starts it when the overlay is switched on)
    python overlay.pyw --test item.txt   price that item text and show the popup now, without the game"""

import ctypes
import ctypes.wintypes as wt
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from poe2kit import config, osutil  # noqa: E402

PORT = int(os.environ.get('POE2KIT_PORT', '47830'))
URL = f'http://127.0.0.1:{PORT}/'
LOCK = os.path.join(config.HOME, 'overlay.lock')
QUIT = os.path.join(config.HOME, 'overlay.quit')
TITLE = 'PoE2 price check'
W, H = 460, 720          # popup size at 100% Windows scaling
EDGE = [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']

u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
WM_DESTROY, WM_TIMER, WM_HOTKEY, WM_CLIPBOARDUPDATE = 0x0002, 0x0113, 0x0312, 0x031D
CF_UNICODETEXT = 13
HWND_TOPMOST = -1
SWP_NOACTIVATE, SWP_SHOWWINDOW, SWP_FRAMECHANGED = 0x0010, 0x0040, 0x0020
SW_HIDE = 0
GWL_STYLE, GWL_EXSTYLE = -16, -20
WS_CAPTION, WS_THICKFRAME, WS_SYSMENU = 0x00C00000, 0x00040000, 0x00080000
WS_EX_TOOLWINDOW, WS_EX_APPWINDOW = 0x80, 0x40000
VK_ESCAPE, HOTKEY_ESC = 0x1B, 1
TIMER_ID = 7

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
ENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
u32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
u32.DefWindowProcW.restype = ctypes.c_ssize_t
u32.GetClipboardData.restype = wt.HANDLE
k32.GlobalLock.restype = ctypes.c_void_p
k32.GlobalLock.argtypes = [wt.HANDLE]
k32.GlobalUnlock.argtypes = [wt.HANDLE]
u32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
u32.GetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
u32.SetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_ssize_t]
u32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
u32.MonitorFromPoint.restype = wt.HANDLE
u32.MonitorFromWindow.restype = wt.HANDLE
u32.MonitorFromWindow.argtypes = [wt.HWND, wt.DWORD]
u32.SetWindowRgn.argtypes = [wt.HWND, wt.HANDLE, wt.BOOL]
ctypes.windll.gdi32.CreateRectRgn.restype = wt.HANDLE


class WNDCLASS(ctypes.Structure):
    _fields_ = [('style', wt.UINT), ('lpfnWndProc', WNDPROC), ('cbClsExtra', ctypes.c_int), ('cbWndExtra', ctypes.c_int),
                ('hInstance', wt.HINSTANCE), ('hIcon', wt.HICON), ('hCursor', wt.HANDLE), ('hbrBackground', wt.HBRUSH),
                ('lpszMenuName', wt.LPCWSTR), ('lpszClassName', wt.LPCWSTR)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [('cbSize', wt.DWORD), ('rcMonitor', wt.RECT), ('rcWork', wt.RECT), ('dwFlags', wt.DWORD)]


def log(msg):
    try:
        with open(os.path.join(config.LOG_DIR, 'overlay.log'), 'a', encoding='utf-8') as f:
            f.write(time.strftime('%Y-%m-%d %H:%M:%S ') + msg + '\n')
    except OSError:
        pass


def post(path, body):
    req = urllib.request.Request(URL + path, data=json.dumps(body).encode(), method='POST',
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def monitor_up():
    try:
        with urllib.request.urlopen(URL + 'api/status', timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


# ---------------- what is in front ----------------

def _exe_of(hwnd):
    pid = wt.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = k32.OpenProcess(0x1000, False, pid.value)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ''
    try:
        buf, n = ctypes.create_unicode_buffer(520), wt.DWORD(520)
        return buf.value if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else ''
    finally:
        k32.CloseHandle(h)


def game_in_front():
    if os.environ.get('POE2KIT_OVERLAY_ANYWINDOW') == '1':
        return True
    hwnd = u32.GetForegroundWindow()
    cls = ctypes.create_unicode_buffer(64)
    u32.GetClassNameW(hwnd, cls, 64)
    if cls.value == 'POEWindowClass':
        return True
    return 'pathofexile' in os.path.basename(_exe_of(hwnd)).lower()


def clipboard_text(hwnd):
    for _ in range(5):   # another program may hold the clipboard for a moment
        if u32.OpenClipboard(hwnd):
            break
        time.sleep(0.03)
    else:
        return ''
    try:
        h = u32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ''
        p = k32.GlobalLock(h)
        try:
            return ctypes.wstring_at(p) if p else ''
        finally:
            k32.GlobalUnlock(h)
    finally:
        u32.CloseClipboard()


def looks_like_item(t):
    return '--------' in t and ('Rarity:' in t or 'Item Class:' in t) and len(t) < 20000


# ---------------- the popup window (Edge app mode) ----------------

class Popup:
    def __init__(self):
        self.proc = None
        self.hwnd = None
        self.shown = False
        self.since = 0

    def start(self):
        edge = next((p for p in EDGE if os.path.exists(p)), None)
        if not edge:
            log('Edge not found: popup unavailable')
            return
        prof = os.path.join(config.HOME, 'edge-overlay')
        self.proc = subprocess.Popen([
            edge, f'--app={URL}overlay', f'--user-data-dir={prof}', '--no-first-run', '--no-default-browser-check',
            f'--window-size={W},{H}', '--window-position=-32000,-32000',
            '--disable-background-timer-throttling', '--disable-renderer-backgrounding',
            '--disable-backgrounding-occluded-windows',
            '--disable-direct-composition'])   # DirectComposition ignores window regions: the title bar would stay
        for _ in range(100):   # wait up to ~10 s for the window
            time.sleep(0.1)
            self.hwnd = self._find()
            if self.hwnd:
                break
        if not self.hwnd:
            log('popup window did not appear')
            return
        st = u32.GetWindowLongPtrW(self.hwnd, GWL_STYLE)
        u32.SetWindowLongPtrW(self.hwnd, GWL_STYLE, st & ~(WS_CAPTION | WS_THICKFRAME | WS_SYSMENU))
        ex = u32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE)
        u32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, (ex | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW)
        self.hide()
        log('popup ready')

    def _find(self):
        found = []

        def cb(h, _):
            buf = ctypes.create_unicode_buffer(256)
            u32.GetWindowTextW(h, buf, 256)
            if buf.value.startswith(TITLE) and u32.IsWindow(h):
                found.append(h)
                return False
            return True
        u32.EnumWindows(ENUMPROC(cb), 0)
        return found[0] if found else None

    def alive(self):
        return bool(self.hwnd and u32.IsWindow(self.hwnd))

    def show(self):
        """Centred on the screen the game is on, above it, without taking the keyboard from the game."""
        if not self.alive():
            self.start()
            if not self.alive():
                return
        self.layout()
        self.shown, self.since = True, time.time()

    def _measure(self):
        """What the page reported about itself: need (panel height), chrome/sides (Edge's frame), dpr, in CSS px."""
        try:
            with urllib.request.urlopen(URL + 'api/overlay/size', timeout=1) as r:
                return json.loads(r.read())
        except Exception:
            return {}

    @staticmethod
    def _bar(dpi):
        """Fallback before the page has reported: a standard title bar at this scaling."""
        try:
            gm = lambda i: u32.GetSystemMetricsForDpi(i, dpi)
        except AttributeError:
            gm = u32.GetSystemMetrics
        return gm(4) + gm(33) + gm(92)   # SM_CYCAPTION, SM_CYSIZEFRAME, SM_CXPADDEDBORDER

    def layout(self, f=None):
        """Size the window to the panel (no scrolling, up to the screen's height), centre it on the game's screen,
        and cut away Edge's own title bar and borders with a window region so only the panel shows.
        Measured from the real window: Edge draws its title bar inside the client area, above the page, so
        bar = client height - page height (the page reports innerH and its pixel ratio)."""
        f = f if f is not None else self._measure()
        self.size_ver = f.get('ver')
        dpi = u32.GetDpiForWindow(self.hwnd) or 96
        dip = dpi / 96
        dpr = f.get('dpr') or dip
        r, o, c = wt.RECT(), wt.POINT(0, 0), wt.RECT()
        u32.GetWindowRect(self.hwnd, ctypes.byref(r))
        u32.ClientToScreen(self.hwnd, ctypes.byref(o))
        u32.GetClientRect(self.hwnd, ctypes.byref(c))
        bx, by = o.x - r.left, o.y - r.top                  # invisible resize border, frame above the client area
        bar = c.bottom - f['innerH'] * dpr if f.get('innerH') else -1
        if not 0 <= bar <= 120 * dip:
            bar = getattr(self, 'bar', None) or self._bar(dpi)
        self.bar = bar
        mi = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
        u32.GetMonitorInfoW(u32.MonitorFromWindow(u32.GetForegroundWindow(), 2), ctypes.byref(mi))
        m = mi.rcMonitor
        content = int(min((f.get('need') or H) * dpr, (m.bottom - m.top) - 40 * dip))
        cw = int(W * dip)
        w, h = cw + 2 * bx, int(by + bar + content + bx)
        x = m.left + (m.right - m.left - cw) // 2 - bx
        y = m.top + (m.bottom - m.top - content) // 2 - int(by + bar)
        u32.SetWindowPos(self.hwnd, HWND_TOPMOST, x, y, w, h, SWP_NOACTIVATE | SWP_SHOWWINDOW | SWP_FRAMECHANGED)
        rgn = ctypes.windll.gdi32.CreateRectRgn(bx, int(by + bar), bx + cw, int(by + bar) + content)
        u32.SetWindowRgn(self.hwnd, rgn, True)   # Windows owns the region from here

    def refit(self):
        """While shown: if the page's size changed (results arrived, rows ticked), fit the window again."""
        f = self._measure()
        if f.get('ver') != getattr(self, 'size_ver', None):
            self.layout(f)

    def hide(self):
        if self.alive():
            u32.ShowWindow(self.hwnd, SW_HIDE)
        self.shown = False

    def clicked_outside(self):
        """A mouse click anywhere that isn't the popup: the player went back to the game."""
        down = any(u32.GetAsyncKeyState(vk) & 0x8000 for vk in (0x01, 0x02))   # left / right button
        if not down:
            return False
        r, pt = wt.RECT(), wt.POINT()
        u32.GetWindowRect(self.hwnd, ctypes.byref(r))
        u32.GetCursorPos(ctypes.byref(pt))
        return not (r.left <= pt.x < r.right and r.top <= pt.y < r.bottom)

    def stop(self):
        if self.proc:
            try:
                self.proc.terminate()
            except OSError:
                pass


# ---------------- main loop ----------------

def take_lock():
    try:
        pid = int(open(LOCK).read().strip() or 0)
        if pid and pid != os.getpid() and osutil.pid_alive(pid):
            return False
    except (OSError, ValueError):
        pass
    os.makedirs(config.HOME, exist_ok=True)
    open(LOCK, 'w').write(str(os.getpid()))
    return True


def main(argv):
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))   # per-monitor v2: real pixels
    except Exception:
        pass
    test = argv[argv.index('--test') + 1] if '--test' in argv else None
    if not test and not take_lock():
        return
    popup = Popup()
    popup.start()
    esc = {'on': False}
    down = {'n': 0, 'last': time.time()}

    def set_esc(on):
        if on and not esc['on']:
            esc['on'] = bool(u32.RegisterHotKey(hwnd_main, HOTKEY_ESC, 0, VK_ESCAPE))
        elif not on and esc['on']:
            u32.UnregisterHotKey(hwnd_main, HOTKEY_ESC)
            esc['on'] = False

    def priced(text):
        try:
            post('api/overlay/item', {'text': text})
        except Exception as e:
            log(f'monitor not reachable: {e}')

    def on_copy():
        if not game_in_front():
            return
        text = clipboard_text(hwnd_main)
        if not looks_like_item(text):
            return
        threading.Thread(target=priced, args=(text,), daemon=True).start()
        popup.show()
        set_esc(True)

    def proc(hwnd, msg, wp, lp):
        if msg == WM_CLIPBOARDUPDATE:
            try:
                on_copy()
            except Exception as e:
                log(f'copy handling failed: {e}')
            return 0
        if msg == WM_HOTKEY and wp == HOTKEY_ESC:
            popup.hide()
            set_esc(False)
            return 0
        if msg == WM_TIMER:
            down['tick'] = down.get('tick', 0) + 1
            if down['tick'] % 10 == 0 and os.path.exists(QUIT):   # switched off in the dashboard
                try:
                    os.remove(QUIT)
                except OSError:
                    pass
                u32.DestroyWindow(hwnd)
                return 0
            if popup.shown and popup.alive() and down['tick'] % 3 == 0:
                try:
                    popup.refit()
                except Exception as e:
                    log(f'refit failed: {e}')
            if popup.shown and popup.alive() and popup.clicked_outside() and time.time() - popup.since > 0.4:
                popup.hide()
                set_esc(False)
            if time.time() - down['last'] > 30:   # quit when the monitor has been gone for ~2 minutes
                down['last'] = time.time()
                down['n'] = 0 if monitor_up() else down['n'] + 1
                if down['n'] >= 4 and not test:
                    u32.DestroyWindow(hwnd)
            return 0
        if msg == WM_DESTROY:
            u32.PostQuitMessage(0)
            return 0
        return u32.DefWindowProcW(hwnd, msg, wp, lp)

    wndproc = WNDPROC(proc)
    wc = WNDCLASS(lpfnWndProc=wndproc, hInstance=k32.GetModuleHandleW(None), lpszClassName='PoE2ToolkitOverlay')
    u32.RegisterClassW(ctypes.byref(wc))
    hwnd_main = u32.CreateWindowExW(0, 'PoE2ToolkitOverlay', 'PoE2 Toolkit overlay', 0, 0, 0, 0, 0, None, None,
                                    wc.hInstance, None)
    u32.AddClipboardFormatListener(hwnd_main)
    u32.SetTimer(hwnd_main, TIMER_ID, 100, None)
    log(f'overlay started (pid {os.getpid()})')
    if test:
        priced(open(test, encoding='utf-8').read())
        popup.show()
        set_esc(True)
    msg = wt.MSG()
    try:
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            u32.TranslateMessage(ctypes.byref(msg))
            u32.DispatchMessageW(ctypes.byref(msg))
    finally:
        u32.RemoveClipboardFormatListener(hwnd_main)
        popup.stop()
        if not test:
            try:
                os.remove(LOCK)
            except OSError:
                pass
        log('overlay stopped')


if __name__ == '__main__':
    main(sys.argv[1:])
