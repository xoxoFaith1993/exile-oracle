"""PoE 2 Toolkit tray icon (for installed copies). Starts the monitor if it isn't running, puts an icon by the clock:
  Open dashboard | Start with Windows (on/off) | Quit (stops the monitor too)
Plain Windows API through ctypes, so the installer needs nothing beyond Python itself."""

import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from poe2kit import config  # noqa: E402

PORT = int(os.environ.get('POE2KIT_PORT', '47830'))
URL = f'http://127.0.0.1:{PORT}/'
RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_NAME = 'PoE2Toolkit'
ICON = os.path.join(HERE, 'dashboard', 'poe2kit.ico')

u32, s32, k32 = ctypes.windll.user32, ctypes.windll.shell32, ctypes.windll.kernel32
WM_USER, WM_COMMAND, WM_DESTROY = 0x0400, 0x0111, 0x0002
WM_TRAY = WM_USER + 20
WM_LBUTTONUP, WM_RBUTTONUP, WM_LBUTTONDBLCLK = 0x0202, 0x0205, 0x0203
NIM_ADD, NIM_DELETE, NIF_MESSAGE, NIF_ICON, NIF_TIP = 0, 2, 1, 2, 4
ID_OPEN, ID_AUTOSTART, ID_QUIT = 1001, 1002, 1003
MF_STRING, MF_CHECKED, MF_SEPARATOR, TPM_RIGHTBUTTON = 0, 8, 0x800, 2
LR_LOADFROMFILE, IMAGE_ICON = 0x10, 1

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
u32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
u32.DefWindowProcW.restype = ctypes.c_ssize_t


class WNDCLASS(ctypes.Structure):
    _fields_ = [('style', wt.UINT), ('lpfnWndProc', WNDPROC), ('cbClsExtra', ctypes.c_int), ('cbWndExtra', ctypes.c_int),
                ('hInstance', wt.HINSTANCE), ('hIcon', wt.HICON), ('hCursor', wt.HANDLE), ('hbrBackground', wt.HBRUSH),
                ('lpszMenuName', wt.LPCWSTR), ('lpszClassName', wt.LPCWSTR)]


class NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [('cbSize', wt.DWORD), ('hWnd', wt.HWND), ('uID', wt.UINT), ('uFlags', wt.UINT),
                ('uCallbackMessage', wt.UINT), ('hIcon', wt.HICON), ('szTip', wt.WCHAR * 128)]


def monitor_up():
    try:
        with urllib.request.urlopen(URL + 'api/status', timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def start_monitor():
    if monitor_up():
        return
    pyw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
    subprocess.Popen([pyw if os.path.exists(pyw) else sys.executable, os.path.join(HERE, 'monitor.py')], cwd=HERE,
                     creationflags=0x00000008 | 0x00000200)  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP


def stop_monitor():
    try:
        pid = int(open(config.LOCK_PATH).read().strip() or 0)
        if pid:
            subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True, creationflags=0x08000000)
        os.remove(config.LOCK_PATH)
    except (OSError, ValueError):
        pass


def open_dashboard():
    for _ in range(30):
        if monitor_up():
            break
        time.sleep(0.5)
    webbrowser.open(URL)


def autostart(enable=None):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
        if enable is None:
            try:
                winreg.QueryValueEx(k, RUN_NAME)
                return True
            except OSError:
                return False
        if enable:
            pyw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, f'"{pyw}" "{os.path.abspath(__file__)}" --background')
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except OSError:
                pass
        return enable


def menu(hwnd):
    m = u32.CreatePopupMenu()
    u32.AppendMenuW(m, MF_STRING, ID_OPEN, 'Open dashboard')
    u32.AppendMenuW(m, MF_STRING | (MF_CHECKED if autostart() else 0), ID_AUTOSTART, 'Start with Windows')
    u32.AppendMenuW(m, MF_SEPARATOR, 0, None)
    u32.AppendMenuW(m, MF_STRING, ID_QUIT, 'Quit PoE 2 Toolkit')
    pt = wt.POINT()
    u32.GetCursorPos(ctypes.byref(pt))
    u32.SetForegroundWindow(hwnd)
    u32.TrackPopupMenu(m, TPM_RIGHTBUTTON, pt.x, pt.y, 0, hwnd, None)
    u32.DestroyMenu(m)


def main():
    start_monitor()
    hinst = k32.GetModuleHandleW(None)
    nid = NOTIFYICONDATA()

    @WNDPROC
    def proc(hwnd, msg, wp, lp):
        if msg == WM_TRAY and lp in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
            open_dashboard()
        elif msg == WM_TRAY and lp == WM_RBUTTONUP:
            menu(hwnd)
        elif msg == WM_COMMAND:
            cmd = wp & 0xFFFF
            if cmd == ID_OPEN:
                open_dashboard()
            elif cmd == ID_AUTOSTART:
                autostart(not autostart())
            elif cmd == ID_QUIT:
                s32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
                stop_monitor()
                u32.PostQuitMessage(0)
        elif msg == WM_DESTROY:
            u32.PostQuitMessage(0)
        return u32.DefWindowProcW(hwnd, msg, wp, lp)

    wc = WNDCLASS()
    wc.lpfnWndProc = proc
    wc.hInstance = hinst
    wc.lpszClassName = 'PoE2ToolkitTray'
    u32.RegisterClassW(ctypes.byref(wc))
    hwnd = u32.CreateWindowExW(0, wc.lpszClassName, 'PoE 2 Toolkit', 0, 0, 0, 0, 0, None, None, hinst, None)
    hicon = u32.LoadImageW(None, ICON, IMAGE_ICON, 16, 16, LR_LOADFROMFILE) if os.path.exists(ICON) else None
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
    nid.hWnd, nid.uID = hwnd, 1
    nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
    nid.uCallbackMessage = WM_TRAY
    nid.hIcon = hicon or u32.LoadIconW(None, ctypes.c_void_p(32512))  # IDI_APPLICATION
    nid.szTip = 'PoE 2 Toolkit'
    s32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
    if '--background' not in sys.argv:
        open_dashboard()
    msg = wt.MSG()
    while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        u32.TranslateMessage(ctypes.byref(msg))
        u32.DispatchMessageW(ctypes.byref(msg))


if __name__ == '__main__':
    main()
