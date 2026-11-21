"""The monitor's side of the price-check overlay: overlay.pyw posts the item text the author copied in game, this prices
it on a worker thread, and the overlay page (dashboard/overlay.html) long-polls for the result."""

import os
import threading
import time
import traceback

_lock = threading.Condition()
_state = {'ver': 0, 'id': 0, 'ts': 0, 'status': 'idle', 'result': None, 'text': ''}


def _bump(**kv):
    with _lock:
        _state.update(kv)
        _state['ver'] += 1
        _lock.notify_all()


def submit(text):
    """New copied item: price it in the background. Returns the check id."""
    text = (text or '')[:20000]
    with _lock:
        same = text == _state['text'] and time.time() - _state['ts'] < 3
        if same:   # the clipboard fires twice for one copy now and then
            return _state['id']
        cid = _state['id'] + 1
    _bump(id=cid, ts=time.time(), status='pricing', result=None, text=text)
    threading.Thread(target=_work, args=(cid, text), daemon=True).start()
    return cid


def research(filters):
    """The overlay's Search button: the same item again with the player's ticked rows and minimums."""
    with _lock:
        text, cid = _state['text'], _state['id']
        if not text:
            return {'ok': False}
    _bump(status='pricing')
    threading.Thread(target=_work, args=(cid, text, filters), daemon=True).start()
    return {'ok': True}


def _work(cid, text, filters=None):
    from . import db, pricecheck
    con = db.connect()
    try:
        res = pricecheck.check(con, text, progress=lambda part: _partial(cid, part), filters=filters)
        status = 'done'
    except Exception as e:
        res = {'error': f'{type(e).__name__}: {e}', 'trace': traceback.format_exc()[-1500:]}
        status = 'error'
    finally:
        con.close()
    with _lock:
        if _state['id'] != cid:   # a newer item was copied meanwhile
            return
    _bump(status=status, result=res)


def _partial(cid, part):
    """Show what is known so far (poe.ninja is instant; the trade search takes a second or two)."""
    with _lock:
        if _state['id'] != cid:
            return
    _bump(result=part)


def wait(after, timeout=25):
    """Long poll: returns the state once its version is newer than `after` (or after `timeout` seconds)."""
    end = time.time() + timeout
    with _lock:
        while _state['ver'] <= after and time.time() < end:
            _lock.wait(max(0.1, end - time.time()))
        return {k: v for k, v in _state.items() if k != 'text'}


# ---------------- switching the overlay on and off ----------------

def _flag():
    from . import config
    return os.path.join(config.HOME, 'overlay.quit')


def running():
    from . import config, osutil
    try:
        pid = int(open(os.path.join(config.HOME, 'overlay.lock')).read().strip() or 0)
    except (OSError, ValueError):
        return False
    return bool(pid) and osutil.pid_alive(pid)


def options():
    from . import config, osutil
    s = config.settings()
    return {'overlay': bool(s.get('overlay', config.is_dev_copy())),
            'live_trade': bool(s.get('live_trade', config.is_dev_copy())),
            'supported': osutil.IS_WIN, 'running': running()}


def start():
    from . import config, osutil
    if not osutil.IS_WIN or running():
        return
    try:
        os.remove(_flag())
    except OSError:
        pass
    osutil.detached([osutil.background_python(), os.path.join(config.ROOT, 'overlay.pyw')], cwd=config.ROOT)


def stop():
    if running():
        open(_flag(), 'w').close()   # overlay.pyw sees this within a second and closes itself and its window


def set_options(b):
    from . import config
    ch = {k: bool(b[k]) for k in ('overlay', 'live_trade') if k in b}
    config.save_settings(ch)
    if 'overlay' in ch:
        start() if ch['overlay'] else stop()
        time.sleep(1.5)
    return options()


def autostart():
    """Called when the monitor starts."""
    if options()['overlay']:
        start()
