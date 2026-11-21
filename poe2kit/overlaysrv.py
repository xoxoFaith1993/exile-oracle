"""The monitor's side of the price-check overlay: overlay.pyw posts the item text the author copied in game, this prices
it on a worker thread, and the overlay page (dashboard/overlay.html) long-polls for the result."""

import os
import threading
import time
import traceback

_lock = threading.Condition()
_state = {'ver': 0, 'id': 0, 'ts': 0, 'status': 'idle', 'result': None, 'text': '', 'view': 'item'}


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
    _bump(id=cid, ts=time.time(), status='pricing', result=None, text=text, view='item')
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


# ---------------- "Ask the Oracle" (the popup's button) ----------------

INBOX = 'claude_inbox'


def send_to_claude():
    """Save the item on screen (its text, price check and listings) for Claude to read with poe2_from_overlay.
    Returns the short question the popup copies to the clipboard."""
    import json
    from . import db
    with _lock:
        text, res = _state['text'], _state['result'] or {}
    if not text or not res.get('item'):
        return {'ok': False, 'error': 'nothing priced yet'}
    t = res.get('trade') or {}
    entry = {'ts': time.time(), 'item_text': text, 'item': res.get('item'), 'league': res.get('league'),
             'headline': res.get('headline'), 'ninja': {k: (res.get('ninja') or {}).get(k) for k in
                                                       ('div', 'change_pct', 'listings', 'volume', 'roll_dependent')}
             if res.get('ninja') else None,
             'trade': {'total': t.get('total'), 'low_div': t.get('low_div'), 'median_div': t.get('median_div'),
                       'listings': [{k: p.get(k) for k in ('amount', 'currency', 'div', 'ilvl', 'listed')}
                                    for p in (t.get('prices') or [])],
                       'searched_for': t.get('filters')} if t.get('state') == 'done' else {'state': t.get('state')},
             'craft_estimate': res.get('estimate'), 'notes': res.get('notes'), 'trade_url': res.get('url'),
             'ex_per_div': res.get('ex_per_div')}
    con = db.connect()
    try:
        try:
            inbox = json.loads(db.kv_get(con, INBOX, '[]') or '[]')
        except ValueError:
            inbox = []
        inbox = [entry] + inbox[:19]
        db.kv_set(con, INBOX, json.dumps(inbox))
    finally:
        con.close()
    it = res['item']
    name = it.get('name') or it.get('base') or 'an item'
    base = f" ({it['base']})" if it.get('base') and it.get('base') != it.get('name') else ''
    prompt = (f"I just sent {name}{base} from my PoE 2 price check overlay. Read it with poe2_from_overlay and tell "
              "me what to do with it: keep, sell (for how much), craft on it, or use it in my build?")
    return {'ok': True, 'prompt': prompt}


def inbox(limit=5, clear=False):
    import json
    from . import db
    con = db.connect()
    try:
        try:
            items = json.loads(db.kv_get(con, INBOX, '[]') or '[]')
        except ValueError:
            items = []
        if clear:
            db.kv_set(con, INBOX, '[]')
        return items[:max(1, int(limit or 5))]
    finally:
        con.close()


# ---------------- popup size (the page measures itself; overlay.pyw fits the window to it) ----------------

_size = {'ver': 0}


def set_size(b):
    keep = {k: float(b[k]) for k in ('need', 'outerH', 'outerW', 'innerH', 'innerW', 'dpr') if isinstance(b.get(k), (int, float))}
    if keep and any(_size.get(k) != v for k, v in keep.items()):
        _size.update(keep)
        _size['ver'] += 1
    return {'ok': True}


def size():
    return dict(_size)


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


CHAT_DEFAULTS = [   # Exiled Exchange 2's defaults: one chat command per key press (Enter, the text, Enter)
    {'text': '/hideout', 'key': 'F5'}, {'text': '/exit', 'key': 'F9'}, {'text': '@last ty', 'key': ''},
    {'text': '/invite @last', 'key': ''}, {'text': '/tradewith @last', 'key': ''}, {'text': '/hideout @last', 'key': ''}]
DEFAULTS = {'listing': 'securable', 'search_range_pct': 10, 'quick_close_px': 150, 'popup_position': 'centre',
            'overlay_on_copy': False, 'chat_commands': CHAT_DEFAULTS, 'ask_claude_target': 'app'}
KEY_RX = __import__('re').compile(r'^((Ctrl|Alt|Shift)\+){0,3}(F([1-9]|1[0-2])|[A-Z0-9])$')


def clean_commands(cmds):
    """Keep valid rows: text up to 120 characters on one line, key like F5 / Ctrl+F1 / Alt+H (or none)."""
    out = []
    for c in (cmds or [])[:20]:
        text = ' '.join(str((c or {}).get('text') or '').split())[:120]
        key = str((c or {}).get('key') or '').replace(' ', '')
        parts = [p.capitalize() if p.lower() in ('ctrl', 'alt', 'shift') else p.upper() for p in key.split('+')] if key else []
        key = '+'.join(parts)
        if not text:
            continue
        out.append({'text': text, 'key': key if KEY_RX.match(key) else ''})
    return out


HOTKEYS = {'quick': 'Ctrl+D', 'detailed': 'Ctrl+Alt+D', 'settings': 'Ctrl+Shift+D'}


def options():
    from . import config, osutil
    s = config.settings()
    out = {'overlay': bool(s.get('overlay', False)),
           'live_trade': bool(s.get('live_trade', False)),
           'supported': osutil.IS_WIN, 'running': running(), 'hotkeys': HOTKEYS}
    out.update({k: s.get(k, v) for k, v in DEFAULTS.items()})
    return out


def open_settings():
    """Ctrl+Shift+D in game: the popup shows the overlay settings."""
    _bump(view='settings')
    return {'ok': True}


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
    ch = {k: bool(b[k]) for k in ('overlay', 'live_trade', 'overlay_on_copy') if k in b}
    if b.get('listing') in ('securable', 'online'):
        ch['listing'] = b['listing']
    if b.get('ask_claude_target') in ('app', 'code'):
        ch['ask_claude_target'] = b['ask_claude_target']
    if b.get('popup_position') in ('centre', 'mouse'):
        ch['popup_position'] = b['popup_position']
    if isinstance(b.get('chat_commands'), list):
        ch['chat_commands'] = clean_commands(b['chat_commands'])
    for k, lo, hi in (('search_range_pct', 0, 50), ('quick_close_px', 50, 800)):
        if k in b:
            try:
                ch[k] = int(max(lo, min(hi, float(b[k]))))
            except (TypeError, ValueError):
                pass
    config.save_settings(ch)
    if 'overlay' in ch:
        start() if ch['overlay'] else stop()
        time.sleep(1.5)
    return options()


def autostart():
    """Called when the monitor starts."""
    if options()['overlay']:
        start()
