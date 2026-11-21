"""Session tracker: reads PoE 2's own log file (logs\\Client.txt) on this PC. No GGG API, no screen reading, nothing
sent anywhere; the same file trade and map-timer tools have always read.

Lines it understands (English client; patterns match what PoE Overlay II uses):
  Generating level 79 area "MapCrypt" with seed 123     -> you entered a zone (instance identified by its seed)
  : Name (Witch) is now level 93                         -> level-up
  : Name has been slain.                                 -> death
  : AFK mode is now ON. / OFF                            -> away from keyboard
  ***** LOG FILE OPENING *****                           -> the game was started
From those it builds sessions (time in maps / hideout / town / campaign / trials), map runs (one per instance seed,
re-entries through portals count as the same map) and campaign time per act."""

import json
import os
import re
import time

from . import config, db

TS = re.compile(r'^(\d{4})/(\d\d)/(\d\d) (\d\d):(\d\d):(\d\d)')
PAT = [
    ('zone', re.compile(r'Generating level (\d+) area "([^"]+)" with seed (\d+)')),
    ('levelup', re.compile(r': (.+) \((.+)\) is now level (\d+)')),
    ('slain', re.compile(r': (.+) has been slain\.')),
    ('afk_on', re.compile(r': AFK mode is now ON')),
    ('afk_off', re.compile(r': AFK mode is now OFF')),
    ('start', re.compile(r'\*\*\*\*\* LOG FILE OPENING \*\*\*\*\*')),
]
GAP = 20 * 60          # a pause this long starts a new session
SEG_CAP = 15 * 60      # one zone visit counts at most this long (AFK without the AFK flag)
FIRST_READ_MAX = 50 * 1024 * 1024  # on the very first read of a huge log, start this far from the end


def log_path():
    p = config.settings().get('client_log')
    if p and os.path.exists(p):
        return p
    return config.client_log()


def _setup(con):
    con.execute('CREATE TABLE IF NOT EXISTS log_event (ts REAL, kind TEXT, a TEXT, b TEXT, c TEXT)')
    con.execute('CREATE INDEX IF NOT EXISTS log_event_ts ON log_event(ts)')


def _ts(line):
    m = TS.match(line)
    if not m:
        return None
    return time.mktime(tuple(int(x) for x in m.groups()) + (0, 0, -1))


def parse_line(line):
    ts = _ts(line)
    if ts is None:
        return None
    for kind, rx in PAT:
        m = rx.search(line)
        if m:
            g = m.groups()
            if kind == 'zone':
                return (ts, kind, g[1], g[0], g[2])        # area id, area level, seed
            if kind == 'levelup':
                return (ts, kind, g[0], g[1], g[2])        # player, class, level
            if kind == 'slain':
                return (ts, kind, g[0], None, None)
            return (ts, kind, None, None, None)
    return None


def sync(con, path=None):
    """Read new lines since last time. Returns how many events were stored."""
    _setup(con)
    path = path or log_path()
    if not path:
        return 0
    size = os.path.getsize(path)
    pos = int(db.kv_get(con, 'clientlog_pos', '-1') or -1)
    if pos < 0:
        pos = max(0, size - FIRST_READ_MAX)
    if pos > size:          # log was cleared or rotated
        pos = 0
    rows = []
    with open(path, 'rb') as f:
        f.seek(pos)
        data = f.read()
    end = data.rfind(b'\n') + 1 if data else 0   # only complete lines
    for raw in data[:end].split(b'\n'):
        ev = parse_line(raw.decode('utf-8', 'replace'))
        if ev:
            rows.append(ev)
    con.executemany('INSERT INTO log_event VALUES (?,?,?,?,?)', rows)
    db.kv_set(con, 'clientlog_pos', str(pos + end))
    con.commit()
    return len(rows)


# ---------------- areas ----------------

_AREAS = {}


def areas():
    if not _AREAS:
        f = config.newest_gamefiles(os.path.join('tables', 'worldareas.json')) or config.data_file('worldareas.json')
        if f:
            d = json.load(open(f, encoding='utf-8'))
            for r in (d.values() if isinstance(d, dict) else d):
                _AREAS[r['Id']] = r
    return _AREAS


def classify(area_id):
    a = areas().get(area_id, {})
    i = area_id or ''
    name = a.get('Name') or i
    act = a.get('Act')
    if a.get('IsTown'):
        kind = 'town'
    elif 'Hideout' in i and not i.startswith('Map'):
        kind = 'hideout'
    elif any(k in i for k in ('Sanctum', 'Ultimatum', 'Trial')):
        kind = 'trial'
    elif i.startswith('Map') or act == 10:
        kind = 'map'
    elif act and act <= 6:
        kind = 'campaign'
    else:
        kind = 'other'
    if act and act <= 4:
        act_name = f'Act {act}'
    elif act == 6:
        m = re.match(r'P(\d)_', i)
        act_name = f'Interlude {m.group(1)}' if m else 'Interludes'
    else:
        act_name = None
    return {'name': name, 'kind': kind, 'act': act_name}


# ---------------- sessions ----------------

def _segments(events):
    """zone events -> visits with durations; session breaks on game start or long gaps."""
    sessions, cur = [], None
    afk_since = None
    for i, (ts, kind, a, b, c) in enumerate(events):
        if kind == 'start' or cur is None or ts - cur['last'] > GAP:
            if cur and cur['visits']:
                sessions.append(cur)
            cur = {'start': ts, 'last': ts, 'visits': [], 'levelups': [], 'deaths': [], 'afk': 0.0}
        cur['last'] = ts
        if kind == 'zone':
            if cur['visits']:
                v = cur['visits'][-1]
                v['secs'] = min(ts - v['ts'], SEG_CAP)
            info = classify(a)
            cur['visits'].append({'ts': ts, 'id': a, 'level': int(b or 0), 'seed': c, 'secs': 0, **info})
        elif kind == 'levelup':
            cur['levelups'].append({'ts': ts, 'player': a, 'class': b, 'level': int(c)})
        elif kind == 'slain':
            cur['deaths'].append({'ts': ts, 'player': a, 'zone': cur['visits'][-1]['name'] if cur['visits'] else None})
        elif kind == 'afk_on':
            afk_since = ts
        elif kind == 'afk_off' and afk_since:
            cur['afk'] += ts - afk_since
            afk_since = None
    if cur and cur['visits']:
        sessions.append(cur)
    for s in sessions:  # the last zone of a session lasts until the session's last logged line
        v = s['visits'][-1]
        if not v['secs']:
            v['secs'] = min(max(0, s['last'] - v['ts']), SEG_CAP)
    return sessions


def _summarise(s, me=None):
    by = {}
    for v in s['visits']:
        by[v['kind']] = by.get(v['kind'], 0) + v['secs']
    runs = {}
    for v in s['visits']:
        if v['kind'] == 'map':
            r = runs.setdefault(v['seed'], {'name': v['name'], 'level': v['level'], 'start': v['ts'], 'secs': 0,
                                            'entries': 0, 'deaths': 0})
            r['secs'] += v['secs']
            r['entries'] += 1
    for d in s['deaths']:
        if me and d['player'] not in me:
            continue
        for r in runs.values():
            if r['start'] <= d['ts'] <= r['start'] + r['secs'] + 3600 and d['zone'] == r['name']:
                r['deaths'] += 1
                break
    maps = sorted(runs.values(), key=lambda r: r['start'])
    acts = {}
    for v in s['visits']:
        if v['act'] and v['kind'] in ('campaign', 'town', 'trial'):
            k = 'world' if v['kind'] == 'campaign' else v['kind']
            acts.setdefault(v['act'], {})[k] = acts.setdefault(v['act'], {}).get(k, 0) + v['secs']
    dur = s['last'] - s['start']
    mapping = by.get('map', 0)
    done = [m for m in maps if m['secs'] >= 30]
    deaths = [d for d in s['deaths'] if not me or d['player'] in me]
    chars = sorted({l['player'] for l in s['levelups']} | {d['player'] for d in deaths})
    return {
        'start': s['start'], 'end': s['last'], 'minutes': round(dur / 60, 1), 'afk_minutes': round(s['afk'] / 60, 1),
        'time_by_kind_min': {k: round(v / 60, 1) for k, v in sorted(by.items(), key=lambda x: -x[1])},
        'maps_run': len(done), 'avg_map_min': round(sum(m['secs'] for m in done) / len(done) / 60, 1) if done else None,
        'maps_per_hour': round(len(done) / (dur / 3600), 1) if dur > 600 and done else None,
        'mapping_share_pct': round(mapping / dur * 100) if dur else 0,
        'deaths': len(deaths), 'levelups': s['levelups'], 'characters': chars,
        'maps': [{'name': m['name'], 'level': m['level'], 'start': m['start'], 'minutes': round(m['secs'] / 60, 1),
                  'portals': m['entries'] - 1, 'deaths': m['deaths']} for m in maps],
        'acts': {a: {k: round(v / 60, 1) for k, v in t.items()} for a, t in acts.items()},
        'zones': len(s['visits']),
    }


def _my_names(con):
    names = set()
    try:
        for r in con.execute("SELECT label FROM build WHERE owner='me'"):
            names.add(r['label'].split(' ')[0])
    except Exception:
        pass
    return names or None


def sessions(con, limit=20):
    _setup(con)
    ev = con.execute('SELECT ts, kind, a, b, c FROM log_event ORDER BY ts, rowid').fetchall()
    me = _my_names(con)
    out = [_summarise(s, me) for s in _segments([tuple(r) for r in ev])]
    out.reverse()
    path = log_path()
    totals = {}
    for s in out:
        for k, v in s['time_by_kind_min'].items():
            totals[k] = round(totals.get(k, 0) + v, 1)
    return {'log': path, 'found_log': bool(path), 'events': len(ev), 'sessions': out[:limit],
            'all_time_by_kind_min': totals,
            'notes': ['Read from the game\'s own log file (Client.txt) on this PC; nothing goes to GGG.',
                      'A map run = one map instance (portals back in count as the same run).',
                      'A single zone visit counts at most 15 minutes, so idling in town does not inflate it; a new '
                      'session starts after a 20-minute gap or when the game is restarted.']}
