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
