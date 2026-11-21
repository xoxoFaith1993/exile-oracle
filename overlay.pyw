"""PoE 2 Toolkit price-check overlay (Windows).

Hover an item in Path of Exile 2 and press
  Ctrl+D       quick check: the popup closes when you move the mouse away
  Ctrl+Alt+D   detailed: the popup stays so you can tick stats and search again (click the game or Esc to close)
  Ctrl+Shift+D overlay settings
  F5, F9, ...  chat commands (/hideout, /exit, ...: Enter, the text, Enter; edit them in the settings)
The hotkeys exist only while the game is in front. Each press makes this program press Ctrl+Alt+C once in the game
(the game copies the item's text, the way Exiled Exchange 2 does it; the author's choice, 2026-11-20); it then reads the
clipboard, sends the text to the toolkit's monitor to be priced and shows the popup in the middle of the screen.
It never reads the game's memory. A plain Ctrl+C of your own shows nothing unless the setting overlay_on_copy is on.
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
HOTKEY_QUICK, HOTKEY_DETAIL, HOTKEY_SETTINGS = 2, 3, 4   # Ctrl+D, Ctrl+Alt+D, Ctrl+Shift+D (game in front only)
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x4000
VK_D, VK_C, VK_CONTROL, VK_MENU = 0x44, 0x43, 0x11, 0x12
AWAY = 150   # quick check default: hides when the mouse moves this far (px at 100%); setting quick_close_px
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


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wt.WORD), ('wScan', wt.WORD), ('dwFlags', wt.DWORD), ('time', wt.DWORD),
                ('dwExtraInfo', ctypes.c_size_t)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [('ki', KEYBDINPUT), ('pad', ctypes.c_byte * 32)]
    _anonymous_ = ('u',)
    _fields_ = [('type', wt.DWORD), ('u', _U)]


VK_RETURN = 0x0D
CMD_BASE = 100   # hotkey ids for chat commands: 100, 101, ...


def parse_key(spec):
    """'F5' / 'Ctrl+F1' / 'Alt+K' -> (modifiers, virtual key) for RegisterHotKey, or None."""
    mods, vk = 0, None
    for part in (spec or '').split('+'):
        p = part.strip().upper()
        if p == 'CTRL':
            mods |= MOD_CONTROL
        elif p == 'ALT':
            mods |= MOD_ALT
        elif p == 'SHIFT':
            mods |= MOD_SHIFT
        elif len(p) > 1 and p[0] == 'F' and p[1:].isdigit() and 1 <= int(p[1:]) <= 12:
            vk = 0x6F + int(p[1:])          # F1 = 0x70
        elif len(p) == 1 and p.isalnum():
            vk = ord(p)
    return (mods, vk) if vk else None


def _send(events):
    arr = (INPUT * len(events))()
    for i, (vk, scan, fl) in enumerate(events):
        arr[i].type = 1
        arr[i].ki = KEYBDINPUT(vk, scan, fl, 0, 0)
    u32.SendInput(len(events), arr, ctypes.sizeof(INPUT))


def type_in_chat(text):
    """One chat command, the way Exiled Exchange 2 does it: Enter (open chat), Ctrl+A (replace anything half-typed),
    the text, Enter. Waits for the player to let go of the hotkey's modifier keys first."""
    for _ in range(50):
        if not any(u32.GetAsyncKeyState(vk) & 0x8000 for vk in (VK_CONTROL, VK_MENU, 0x10)):
            break
        time.sleep(0.02)
    ev = [(VK_RETURN, 0, 0), (VK_RETURN, 0, 2),                               # open chat
          (VK_CONTROL, 0, 0), (0x41, 0, 0), (0x41, 0, 2), (VK_CONTROL, 0, 2)]  # Ctrl+A: replace half-typed text
    for ch in text:
        ev += [(0, ord(ch), 4), (0, ord(ch), 4 | 2)]                         # KEYEVENTF_UNICODE (+ KEYUP)
    ev += [(VK_RETURN, 0, 0), (VK_RETURN, 0, 2)]                             # send
    _send(ev)   # one burst, no pauses: the chat box is open for a frame or two at most


def press_copy(advanced):
    """One copy key press in the game, the way Exiled Exchange 2 does it (the author chose Ctrl+D, 2026-11-20):
    Ctrl+C, or Ctrl+Alt+C for the detailed text. Modifiers the player is still holding are left as they are."""
    keys = []
    held = lambda vk: u32.GetAsyncKeyState(vk) & 0x8000
    mods = [VK_CONTROL] + ([VK_MENU] if advanced else [])
    add = [vk for vk in mods if not held(vk)]
    drop = [VK_MENU] if not advanced and held(VK_MENU) else []
    for vk in drop:
        keys.append((vk, 2))
    for vk in add:
        keys.append((vk, 0))
    keys += [(VK_C, 0), (VK_C, 2)]
    for vk in reversed(add):
        keys.append((vk, 2))
    arr = (INPUT * len(keys))()
    for i, (vk, fl) in enumerate(keys):
        arr[i].type = 1                      # INPUT_KEYBOARD
        arr[i].ki = KEYBDINPUT(vk, 0, fl, 0, 0)   # fl 2 = KEYEVENTF_KEYUP
    u32.SendInput(len(keys), arr, ctypes.sizeof(INPUT))


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
        if config.settings().get('popup_position') == 'mouse' and getattr(self, 'origin', None):
            gap = int(28 * dip)
            px, py = self.origin
            x = px + gap if px + gap + cw <= m.right else px - gap - cw
            x = max(m.left, min(x, m.right - cw)) - bx
            y = max(m.top, min(py - content // 3, m.bottom - content)) - int(by + bar)
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

    def moved_away(self):
        """Quick check: the mouse left the spot where the hotkey was pressed (and isn't on the popup)."""
        if not getattr(self, 'origin', None):
            return False
        pt, r = wt.POINT(), wt.RECT()
        u32.GetCursorPos(ctypes.byref(pt))
        u32.GetWindowRect(self.hwnd, ctypes.byref(r))
        if r.left <= pt.x < r.right and r.top <= pt.y < r.bottom:
            return False
        scale = (u32.GetDpiForWindow(self.hwnd) or 96) / 96
        away = config.settings().get('quick_close_px') or AWAY
        return max(abs(pt.x - self.origin[0]), abs(pt.y - self.origin[1])) > float(away) * scale

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

def overlaysrv_defaults():
    from poe2kit import overlaysrv
    return overlaysrv.CHAT_DEFAULTS


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
    hk = {'on': False, 'mode': None, 'at': 0, 'origin': None}

    cmds = {'on': [], 'sig': None, 'list': []}

    def set_commands(on):
        """Chat command keys from the settings (F5 /hideout, F9 /exit, ...), only while the game is in front."""
        lst = [c for c in (config.settings().get('chat_commands') or overlaysrv_defaults()) if c.get('key')]
        sig = json.dumps(lst)
        if cmds['on'] and (not on or sig != cmds['sig']):
            for i in cmds['on']:
                u32.UnregisterHotKey(hwnd_main, i)
            cmds['on'] = []
        if on and not cmds['on']:
            for n, c in enumerate(lst):
                k = parse_key(c['key'])
                if k and u32.RegisterHotKey(hwnd_main, CMD_BASE + n, k[0] | MOD_NOREPEAT, k[1]):
                    cmds['on'].append(CMD_BASE + n)
            cmds['sig'], cmds['list'] = sig, lst

    def set_hotkeys(on):
        """Ctrl+D / Ctrl+Alt+D exist only while the game is the window in front: other programs keep their Ctrl+D."""
        if on and not hk['on']:
            a = u32.RegisterHotKey(hwnd_main, HOTKEY_QUICK, MOD_CONTROL | MOD_NOREPEAT, VK_D)
            b = u32.RegisterHotKey(hwnd_main, HOTKEY_DETAIL, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_D)
            c = u32.RegisterHotKey(hwnd_main, HOTKEY_SETTINGS, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, VK_D)
            hk['on'] = bool(a or b or c)
        elif not on and hk['on']:
            u32.UnregisterHotKey(hwnd_main, HOTKEY_QUICK)
            u32.UnregisterHotKey(hwnd_main, HOTKEY_DETAIL)
            u32.UnregisterHotKey(hwnd_main, HOTKEY_SETTINGS)
            hk['on'] = False

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
        mode = hk['mode'] if time.time() - hk['at'] < 2 else None
        hk['mode'] = None
        if not mode and not config.settings().get('overlay_on_copy'):
            return
        text = clipboard_text(hwnd_main)
        if not looks_like_item(text):
            return
        threading.Thread(target=priced, args=(text,), daemon=True).start()
        popup.quick = mode == 'quick'
        pt = wt.POINT()
        u32.GetCursorPos(ctypes.byref(pt))
        popup.origin = (pt.x, pt.y)
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
        if msg == WM_HOTKEY and wp >= CMD_BASE:
            n = wp - CMD_BASE
            if game_in_front() and n < len(cmds['list']):
                threading.Thread(target=type_in_chat, args=(cmds['list'][n]['text'],), daemon=True).start()
            return 0
        if msg == WM_HOTKEY and wp == HOTKEY_SETTINGS:
            if game_in_front():
                threading.Thread(target=lambda: post('api/overlay/settings_open', {}), daemon=True).start()
                popup.quick = False
                popup.show()
                set_esc(True)
            return 0
        if msg == WM_HOTKEY and wp in (HOTKEY_QUICK, HOTKEY_DETAIL):
            if game_in_front():
                hk.update(mode='quick' if wp == HOTKEY_QUICK else 'detail', at=time.time())
                try:
                    press_copy(advanced=True)   # the detailed copy gives the better search in both modes
                except Exception as e:
                    log(f'copy key failed: {e}')
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
            front = game_in_front()
            set_hotkeys(front)
            if down['tick'] % 5 == 0 or not front:   # re-read the command list twice a second (settings edits)
                set_commands(front)
            if popup.shown and popup.alive() and getattr(popup, 'quick', False) and popup.moved_away()                     and time.time() - popup.since > 0.3:
                popup.hide()
                set_esc(False)
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
