"""The few things that differ between Windows and Linux (Steam Deck included), in one place."""

import os
import signal
import subprocess
import sys

IS_WIN = os.name == 'nt'


def pid_alive(pid):
    if not pid:
        return False
    if IS_WIN:
        out = subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/NH'], capture_output=True, text=True).stdout
        return str(pid) in out and 'python' in out.lower()
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
        subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True)
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
        out = subprocess.run(['tasklist', '/NH'], capture_output=True, text=True).stdout.lower()
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
        return [os.path.join(home, 'Documents')]
    import glob
    user = os.environ.get('USER') or os.path.basename(home)
    cands = [os.path.join(home, '.wine', 'drive_c', 'users', user, 'Documents'),
             os.path.join(home, 'Documents')]
    cands += glob.glob(os.path.join(home, '.local', 'share', 'Steam', 'steamapps', 'compatdata', '*', 'pfx',
                                    'drive_c', 'users', 'steamuser', 'Documents'))
    cands += glob.glob(os.path.join(home, 'Games', '*', 'drive_c', 'users', '*', 'Documents'))   # Lutris
    return cands


def find_documents(sub):
    """First Documents folder that has `sub` (e.g. 'Path of Building (PoE2)'), else the most likely one."""
    for d in documents_dirs():
        if os.path.isdir(os.path.join(d, sub)):
            return os.path.join(d, sub)
    return os.path.join(documents_dirs()[0], sub)
