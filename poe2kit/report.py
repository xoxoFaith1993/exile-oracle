"""Report an issue / send a suggestion: the player's words (plus, for issues, a short scrubbed doctor summary) go to
the developer through the same Firebase database as Hunt Tracker and CrateMatch.

Each copy signs in anonymously (no account, nothing for the player to do) and may only ADD reports under its own id;
only the developer can read them. Limits from the database rules: t, v (<=20 chars), name (<=40), text (1..3000),
setup {key: string <=200 or number/bool}. Reports are tagged setup.app = "Exile Oracle" and setup.kind."""

import json
import os
import platform
import re
import time
import urllib.request

from . import config

DB_URL = 'https://hunt-tracker-leaderboard-default-rtdb.firebaseio.com'
API_KEY = 'AIzaSyAH_iRkVse016gT0tGuh1e0rrOxUvP2q0M'   # Firebase web API key: public by design, the rules guard the data
TEXT_LIMIT = 3000
COOLDOWN = 60   # seconds between two reports from one copy


def _post(url, body):
    req = urllib.request.Request(url, method='POST', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json', 'User-Agent': config.user_agent()})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read() or b'null')


def _sign_in():
    """Anonymous sign-in: a random id kept in the settings (no account). -> (token, uid)"""
    s = config.settings()
    if s.get('report_refresh'):
        try:
            r = _post(f'https://securetoken.googleapis.com/v1/token?key={API_KEY}',
                      {'grant_type': 'refresh_token', 'refresh_token': s['report_refresh']})
            return r['id_token'], r['user_id']
        except Exception:
            pass   # expired or revoked: make a new id
    r = _post(f'https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}', {'returnSecureToken': True})
    config.save_settings({'report_refresh': r['refreshToken']})
    return r['idToken'], r['localId']


def scrub(text):
    """Remove what could identify the player: their Windows user folder, emails, the PoE account tag."""
    home = os.path.expanduser('~')
    text = text.replace(home, '~').replace(home.replace('\\', '/'), '~')
    text = re.sub(r'(?i)\b[\w.+-]+@[\w-]+\.[\w.]+\b', '<email>', text)
    text = re.sub(r'\b[\w-]{3,}#\d{4}\b', '<account>', text)
    return text


def doctor_summary():
    """A few short lines from the doctor (problems first), scrubbed."""
    from . import doctor
    try:
        r = doctor.run()
    except Exception as e:
        return f'doctor failed: {type(e).__name__}'
    lines = []
    for c in r.get('checks') or []:
        ok = c.get('ok')
        detail = re.sub(r'toolkit plans:.*', 'toolkit plans: (names left out)', str(c.get('detail') or ''))   # build names
        lines.append(('ok   ' if ok else 'FAIL ') + f"{c.get('part')}: {detail[:140]}")
    lines.sort(key=lambda l: not l.startswith('FAIL'))
    return scrub('\n'.join(lines))


def _clip(v, n=200):
    if isinstance(v, (int, float, bool)) or v is None:
        return v
    v = str(v)
    return v if len(v) <= n else v[:n - 1] + '…'


def preview(kind, message='', attach=True):
    text = message.strip()
    if kind == 'issue' and attach:
        ctx = doctor_summary()
        room = TEXT_LIMIT - len(text) - 40
        if room > 100:
            text += '\n\n--- added automatically ---\n' + (ctx if len(ctx) <= room else ctx[:room - 1] + '…')
    return text[:TEXT_LIMIT]


def send(kind, message, name='', attach=True):
    kind = 'suggestion' if kind == 'suggestion' else 'issue'
    if not (message or '').strip():
        raise ValueError('Type what happened (or your idea) first.')
    last = config.settings().get('report_last') or 0
    if time.time() - last < COOLDOWN:
        raise ValueError('You just sent one: wait a minute before the next.')
    token, uid = _sign_in()
    setup = {'app': config.APP_NAME, 'kind': kind, 'os': f'{platform.system()} {platform.release()}',
             'python': platform.python_version()}
    body = {'t': int(time.time()), 'v': config.VERSION[:20],
            'name': _clip(f'{config.APP_NAME}: {name}' if name else config.APP_NAME, 40),
            'text': preview(kind, message, attach),
            'setup': {k: _clip(v) for k, v in setup.items() if v not in (None, '')}}
    _post(f'{DB_URL}/issues/{uid}.json?auth={token}', body)
    config.save_settings({'report_last': time.time()})
    return {'ok': True, 'kind': kind}
