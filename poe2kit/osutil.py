"""The few things that differ between Windows and Linux (Steam Deck included), in one place."""

import os
import signal
import subprocess
import sys

IS_WIN = os.name == 'nt'
# console programs started from the windowless toolkit (pythonw) would flash a command window without this
NO_WINDOW = 0x08000000 if IS_WIN else 0


def _win_exe(pid):
    """Full path of a running process's program, or '' if it isn't running (no command window involved)."""
    import ctypes
    import ctypes.wintypes as wt
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = wt.HANDLE
    h = k32.OpenProcess(0x1000, False, int(pid))   # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ''
    try:
        code = wt.DWORD()
        if not k32.GetExitCodeProcess(h, ctypes.byref(code)) or code.value != 259:   # STILL_ACTIVE
            return ''
        buf, n = ctypes.create_unicode_buffer(520), wt.DWORD(520)
        return buf.value if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else '?'
    finally:
        k32.CloseHandle(h)


def pid_alive(pid):
    if not pid:
        return False
    if IS_WIN:
        exe = _win_exe(pid)
        return bool(exe) and 'python' in os.path.basename(exe).lower()
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:   # make sure it's a Python (pids get reused)
        with open(f'/proc/{pid}/cmdline', 'rb') as f:
            return b'python' in f.read().lower()
    except OSError:
        return True


def kill(pid):
    if not pid:
        return
    if IS_WIN:
        subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True, creationflags=NO_WINDOW)
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def background_python():
    """The Python to run background jobs with: pythonw.exe on Windows (no console window), else this Python."""
    if IS_WIN:
        pyw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
        if os.path.exists(pyw):
            return pyw
    return sys.executable


def console_python():
    """A Python that talks over stdin/stdout (for the Claude tools server)."""
    if IS_WIN:
        exe = os.path.join(os.path.dirname(sys.executable), 'python.exe')
        if os.path.exists(exe):
            return exe
    return sys.executable


def detached(args, cwd=None):
    """Start a process that outlives this one, with no console window."""
    if IS_WIN:
        return subprocess.Popen(args, cwd=cwd, creationflags=0x00000008 | 0x00000200)  # DETACHED | NEW_GROUP
    return subprocess.Popen(args, cwd=cwd, start_new_session=True, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def bring_to_front(hwnd):
    """Put a window of ours in front even when a background process opened it (the monitor starts the poe.ninja
    window, and Windows keeps background programs from stealing the foreground). Windows only; best effort."""
    if not IS_WIN or not hwnd:
        return False
    import ctypes
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    if u32.IsIconic(hwnd):
        u32.ShowWindow(hwnd, 9)                          # SW_RESTORE
    fg = u32.GetForegroundWindow()
    me, other = k32.GetCurrentThreadId(), u32.GetWindowThreadProcessId(fg, None)
    attached = bool(other and other != me and u32.AttachThreadInput(other, me, True))
    try:
        flags = 0x0001 | 0x0002 | 0x0040                 # SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW
        u32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, flags)     # HWND_TOPMOST, then back: lifts it above everything
        u32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, flags)     # HWND_NOTOPMOST
        u32.BringWindowToTop(hwnd)
        ok = bool(u32.SetForegroundWindow(hwnd))
    finally:
        if attached:
            u32.AttachThreadInput(other, me, False)
    return ok


def set_window_icon(hwnd, ico):
    """Give a window (and its taskbar button) our icon instead of Python's. Windows only; best effort."""
    if not IS_WIN or not hwnd or not os.path.exists(ico):
        return False
    import ctypes
    from ctypes import wintypes as wt
    u32 = ctypes.windll.user32
    u32.LoadImageW.restype = wt.HANDLE   # 64-bit handles: don't let ctypes cut them to 32 bits
    u32.LoadImageW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, wt.UINT, ctypes.c_int, ctypes.c_int, wt.UINT]
    u32.SendMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    for size, which in ((16, 0), (32, 1), (48, 1)):   # ICON_SMALL = 0, ICON_BIG = 1
        h = u32.LoadImageW(None, ico, 1, size, size, 0x10)   # IMAGE_ICON, LR_LOADFROMFILE
        if h:
            u32.SendMessageW(hwnd, 0x0080, which, h)   # WM_SETICON
    return True


def find_window(title_start):
    """The first visible top-level window whose title starts with this text (Windows), else None."""
    if not IS_WIN:
        return None
    import ctypes
    import ctypes.wintypes as wt
    u32 = ctypes.windll.user32
    found = []

    def each(h, _):
        buf = ctypes.create_unicode_buffer(512)
        u32.GetWindowTextW(h, buf, 512)
        if u32.IsWindowVisible(h) and buf.value.startswith(title_start):
            found.append(h)
            return False
        return True
    u32.EnumWindows(ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)(each), 0)
    return found[0] if found else None


def process_running(fragment):
    """Is a program whose name or command line contains `fragment` running? (e.g. 'Path of Building')"""
    frag = fragment.lower()
    if IS_WIN:
        out = subprocess.run(['tasklist', '/NH'], capture_output=True, text=True, creationflags=NO_WINDOW).stdout.lower()
        return frag in out
    for pid in os.listdir('/proc'):
        if pid.isdigit():
            try:
                with open(f'/proc/{pid}/cmdline', 'rb') as f:
                    if frag.encode() in f.read().lower():
                        return True
            except OSError:
                pass
    return False


def documents_dirs():
    """Where a player's Documents folder can be: Windows itself, or Wine / Proton prefixes on Linux (Path of
    Building runs under Wine there and keeps its builds and login in that prefix's Documents)."""
    home = os.path.expanduser('~')
    if IS_WIN:
        out = []
        try:   # the real Documents folder, also when OneDrive or the user moved it
            import ctypes
            from ctypes import wintypes as wt

            class GUID(ctypes.Structure):
                _fields_ = [('a', wt.DWORD), ('b', wt.WORD), ('c', wt.WORD), ('d', ctypes.c_ubyte * 8)]
            docs = GUID(0xFDD39AD0, 0x238F, 0x46AF, (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
            p = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(docs), 0, None, ctypes.byref(p)) == 0:
                out.append(p.value)
                ctypes.windll.ole32.CoTaskMemFree(p)
        except Exception:
            pass
        plain = os.path.join(home, 'Documents')
        return out + [plain] if plain not in out else out
    import glob
    user = os.environ.get('USER') or os.path.basename(home)
    cands = [os.path.join(home, '.wine', 'drive_c', 'users', user, 'Documents'),
             os.path.join(home, 'Documents')]
    # Proton prefixes live in the Steam library the game is installed in: the home one, Flatpak Steam, or an SD card
    # / extra drive (Steam Deck: /run/media/<user>/<card>/steamapps or /run/media/mmcblk0p1/steamapps)
    libs = [os.path.join(home, '.local', 'share', 'Steam'), os.path.join(home, '.steam', 'steam'),
            os.path.join(home, '.var', 'app', 'com.valvesoftware.Steam', '.local', 'share', 'Steam')]
    for pat in ('/run/media/*', '/run/media/*/*', '/run/media/*/*/SteamLibrary', '/media/*/*', '/media/*/*/SteamLibrary',
                '/mnt/*', '/mnt/*/SteamLibrary'):
        libs += glob.glob(pat)
    pfx = []
    for lib in libs:
        base = os.path.join(lib, 'steamapps', 'compatdata')
        if os.path.isdir(base):
            pfx += [os.path.join(base, '2694490')]                       # Path of Exile 2 first
            pfx += sorted(glob.glob(os.path.join(base, '*')))
    seen = set()
    for p in pfx:
        d = os.path.join(p, 'pfx', 'drive_c', 'users', 'steamuser', 'Documents')
        real = os.path.realpath(d)
        if real not in seen and os.path.isdir(d):
            seen.add(real)
            cands.append(d)
    cands += glob.glob(os.path.join(home, 'Games', '*', 'drive_c', 'users', '*', 'Documents'))   # Lutris
    return cands


def find_documents(sub):
    """First Documents folder that has `sub` (e.g. 'Path of Building (PoE2)'), else the most likely one."""
    for d in documents_dirs():
        if os.path.isdir(os.path.join(d, sub)):
            return os.path.join(d, sub)
    return os.path.join(documents_dirs()[0], sub)
