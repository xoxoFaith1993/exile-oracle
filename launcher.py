"""Cross-platform launcher (the Linux app-menu entry and autostart use it; Windows uses tray.pyw):
start the monitor if it isn't running, then open the dashboard in the default browser.

    python launcher.py               start if needed + open the dashboard
    python launcher.py --background  start if needed, don't open anything (autostart)
    python launcher.py --stop        stop the monitor"""

import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from poe2kit import config, osutil  # noqa: E402

PORT = int(os.environ.get('POE2KIT_PORT', '47830'))
URL = f'http://127.0.0.1:{PORT}/'


def up():
    try:
        with urllib.request.urlopen(URL + 'api/status', timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def stop():
    try:
        pid = int(open(config.LOCK_PATH).read().strip() or 0)
    except (OSError, ValueError):
        return False
    osutil.kill(pid)
    try:
        os.remove(config.LOCK_PATH)
    except OSError:
        pass
    return True


def main(argv):
    if '--stop' in argv:
        print('stopped' if stop() else 'not running')
        return
    if not up():
        osutil.detached([osutil.background_python(), os.path.join(HERE, 'monitor.py')], cwd=HERE)
        for _ in range(60):   # up to ~30 s on a cold start
            time.sleep(0.5)
            if up():
                break
    if '--background' not in argv:
        from poe2kit import appwindow
        appwindow.open_dashboard()


if __name__ == '__main__':
    main(sys.argv[1:])
