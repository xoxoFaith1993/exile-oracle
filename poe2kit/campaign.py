"""Campaign rush guide (R16) and the zone-aware route panel (R21).

Data: datapack/campaign.json (our own research, research/campaign: rush route per act, permanent rewards, trials,
tips, times) + datapack/worldareas.json (the game's own area table: id -> name, act, level, town / map flags).
The game log (Client.txt) names every zone you enter by its area id ("G1_4"); overlay.pyw reads the new lines as
they come and posts the area here, and the route panel long-polls zone_state().

For 1.0 (Acts 5-6, Interludes removed): worldareas.json is regenerated from the game tables on patch day, so new
zones get names and acts automatically; the route steps and rewards come from the research file and are updated
there as the community maps the new acts.
"""

import json
import re
import threading
import time

from . import config

_cache = {}
_lock = threading.Condition()
_zone = {'ver': 0, 'area': None, 'level': None, 'ts': 0, 'hidden': False}
FLASK_LEVELS = [4, 10, 16, 23, 30, 40, 50, 60]          # research/campaign C2, C4 (H)
BOOT_STEPS = [(1, 10), (16, 15), (33, 20), (46, 25)]     # (level, movement speed %) research/campaign C2 (H)
LIFE_TARGETS = {1: 300, 2: 600, 3: 900}                  # end of act, life + ES (M)


def _load(name):
    if name not in _cache:
        p = config.data_file(name)
        if not p:
            raise FileNotFoundError(f'{name} is missing from the data pack')
        _cache[name] = json.load(open(p, encoding='utf-8'))
    return _cache[name]


def data():
    return _load('campaign.json')


def areas():
    return _load('worldareas.json')


def _key(name):
    n = re.sub(r'^the\s+', '', (name or '').strip().lower())
    return re.sub(r'[^a-z]', '', n)


def _by_name():
    if 'by_name' not in _cache:
        m = {}
        for aid, a in areas().items():
            if a.get('IsMapArea') or aid.startswith(('Map', 'Hideout')):
                continue
            m.setdefault(_key(a.get('Name')), []).append(aid)
        _cache['by_name'] = m
    return _cache['by_name']


def _act_no(label):
    m = re.match(r'Act (\d+)', label or '')
    return int(m.group(1)) if m else 6


def steps():
    """The rush route as a flat list: {act, act_no, i, label, note, names, areas}."""
    if 'steps' in _cache:
        return _cache['steps']
    out = []
    names = _by_name()
    for a in data()['acts']:
        for i, s in enumerate(a['rush_route']):
            head, _, rest = s.partition(' (')
            note = rest[:-1] if rest.endswith(')') else rest
            if ' -> ' in head and not note:
                head, _, note = head.partition(' -> ')
                note = 'then ' + note
            head = re.sub(r'^I\d:\s*', '', head)
            parts = [p.strip() for p in re.split(r' / | -> |, ', head) if p.strip()]
            ids = []
            for p in parts:
                p = re.sub(r'\s+first$', '', p)
                ids += names.get(_key(p), [])
                if not names.get(_key(p)) and parts and len(p.split()) == 1:   # "Mawdun Quarry / Mine" -> Mawdun Mine
                    ids += names.get(_key(parts[0].split()[0] + ' ' + p), [])
            out.append({'act': a['act'], 'act_no': _act_no(a['act']), 'i': i, 'of': len(a['rush_route']),
                        'label': head, 'note': note, 'areas': ids})
    _cache['steps'] = out
    return out


def _reward_points(text):
    m = re.search(r'\+(\d+) (?:weapon set )?passive', (text or '').lower())
    return int(m.group(1)) if m else 0


def _reward_spirit(text):
    m = re.search(r'\+(\d+) spirit', (text or '').lower())
    return int(m.group(1)) if m else 0


def rewards():
    """Permanent rewards with a stable key, the zone they're in and what they give."""
    if 'rewards' in _cache:
        return _cache['rewards']
    names = _by_name()
    out = []
    for n, r in enumerate(data()['permanent_rewards']):
        zone = r.get('where', '').split(':', 1)[0].strip()
        out.append(dict(r, key=f'r{n}', zone=zone, areas=names.get(_key(zone), []),
                        points=_reward_points(r.get('reward')), spirit=_reward_spirit(r.get('reward'))))
    _cache['rewards'] = out
    return out


def done(con):
    from . import db
    try:
        return set(json.loads(db.kv_get(con, 'campaign:done') or '[]'))
    except ValueError:
        return set()


def set_done(con, key, on):
    from . import db
    d = done(con)
    (d.add if on else d.discard)(key)
    db.kv_set(con, 'campaign:done', json.dumps(sorted(d)))
    return sorted(d)


def guide(con=None):
    """Everything the Campaign page shows."""
    d = data()
    dn = done(con) if con is not None else set()
    rw = [dict(r, done=r['key'] in dn) for r in rewards()]
    tot = d.get('permanent_reward_totals', {})
    got_pts = sum(r['points'] for r in rw if r['done'])
    got_sp = sum(r['spirit'] for r in rw if r['done'])
    clean = lambda xs: [{k: v for k, v in x.items() if k not in ('sources', 'source', 'url')} for x in xs or []]
    acts = []
    for a in d['acts']:
        acts.append({'act': a['act'], 'levels': a.get('levels'), 'minutes': a.get('typical_minutes'),
                     'route': [s for s in steps() if s['act'] == a['act']],
                     'skip': clean(a.get('skip')), 'keep': clean(a.get('do_not_skip')), 'tips': clean(a.get('tips'))})
    return {'meta': {k: v for k, v in d['meta'].items() if k in ('researched', 'game_version', 'next_version')},
            'acts': acts, 'rewards': rw,
            'progress': {'points': got_pts, 'points_total': tot.get('passive_points', 24),
                         'spirit': got_sp, 'spirit_total': tot.get('spirit', 100),
                         'done': sum(1 for r in rw if r['done']), 'of': len(rw)},
            'totals': tot, 'trials': clean(d.get('ascendancy_trials')),
            'times': clean((d.get('totals_minutes') or {}).get('sourced')),
            'mistakes': clean(d.get('mistakes')), 'tips': clean(d.get('general_tips')),
            'rush_vs_full': {k: v for k, v in (d.get('rush_vs_full_clear') or {}).items() if k != 'sources'},
            'watch': clean(d.get('v1_watchlist')),
            'breakpoints': {'flasks': FLASK_LEVELS, 'boots': BOOT_STEPS, 'life': LIFE_TARGETS},
            'zone': zone_card(con)}


# ---------------- where you are now (R21) ----------------

def kind_of(aid):
    a = areas().get(aid or '') or {}
    if not aid:
        return 'none'
    if 'hideout' in aid.lower() or 'Hideout' in (a.get('Name') or ''):
        return 'hideout'
    if a.get('IsMapArea') or aid.startswith('Map'):
        return 'map'
    if a.get('IsTown'):
        return 'town'
    if re.match(r'^G\d', aid):
        return 'campaign'
    return 'other'


def set_zone(aid, level=None):
    with _lock:
        if aid == _zone['area']:
            return _zone['ver']
        if kind_of(_zone['area']) == 'campaign':
            _zone['last_campaign'] = _zone['area']
        _zone.update(area=aid, level=level, ts=time.time(), ver=_zone['ver'] + 1)
        _lock.notify_all()
        return _zone['ver']


def toggle_hidden():
    with _lock:
        _zone['hidden'] = not _zone['hidden']
        _zone['ver'] += 1
        _lock.notify_all()
        return _zone['hidden']


def _last_zone_from_log(con):
    try:
        r = con.execute("SELECT a, b FROM log_event WHERE kind='zone' ORDER BY ts DESC LIMIT 1").fetchone()
        return (r[0], r[1]) if r else (None, None)
    except Exception:
        return (None, None)


def zone_state(after=-1, timeout=25, con=None):
    """Long poll for the route panel: returns once the zone changed past `after`."""
    end = time.time() + timeout
    with _lock:
        while _zone['ver'] <= after and time.time() < end:
            _lock.wait(max(0.1, end - time.time()))
        z = dict(_zone)
    try:
        from . import overlaysrv
        key = overlaysrv.price_keys().get('route')
    except Exception:
        key = None
    return dict(zone_card(con, z), ver=z['ver'], hidden=z['hidden'], key=key)


def zone_card(con=None, z=None):
    """What to do in the zone you're in: the route step, next stops, rewards here, trial, level tips, progress."""
    z = z or dict(_zone)
    aid, lvl = z.get('area'), z.get('level')
    if not aid and con is not None:
        aid, lvl = _last_zone_from_log(con)
    kind = kind_of(aid)
    a = areas().get(aid or '') or {}
    card = {'area': {'id': aid, 'name': a.get('Name') or aid, 'act': a.get('Act'), 'level': int(lvl or a.get('AreaLevel') or 0)},
            'kind': kind, 'show': kind in ('campaign', 'town')}
    if not card['show']:
        return card
    st = steps()
    here = next((s for s in st if aid in s['areas']), None)
    if not here and kind == 'town' and z.get('last_campaign'):   # back in town: carry on from the zone you left
        here = next((s for s in st if z['last_campaign'] in s['areas']), None)
    if not here:   # a side zone or a town: the first step of its act not yet behind you, by area level
        act_steps = [s for s in st if s['act_no'] == (a.get('Act') or 0)]
        lv = a.get('AreaLevel') or 0
        later = [s for s in act_steps if any((areas().get(x) or {}).get('AreaLevel', 0) >= lv for x in s['areas'])]
        here = (later or act_steps or [None])[0]
        card['off_route'] = kind != 'town'
    if here:
        k = st.index(here)
        card['step'] = here
        card['next'] = [{'label': s['label'], 'note': s['note'], 'act': s['act']} for s in st[k + 1:k + 3]]
        card['act'] = here['act']
        card['progress'] = f"{here['act']} · stop {here['i'] + 1} of {here['of']}"
    dn = done(con) if con is not None else set()
    card['rewards'] = [{'key': r['key'], 'reward': r['reward'], 'where': r['where'], 'required': r.get('required'),
                        'done': r['key'] in dn} for r in rewards() if aid in r['areas']]
    pts = sum(r['points'] for r in rewards() if r['key'] in dn)
    card['points'] = {'got': pts, 'of': data().get('permanent_reward_totals', {}).get('passive_points', 24)}
    name = (a.get('Name') or '').lower()
    card['trial'] = next(({'trial': t['trial'], 'points': t['points'], 'key': t.get('key'), 'timing': t.get('timing')}
                          for t in data().get('ascendancy_trials', []) if _key(t['trial'].split('(')[0]) and
                          _key(t['trial'].split('(')[0]) in _key(name)), None)
    tips = []
    lv = card['area']['level']
    fl = next((f for f in FLASK_LEVELS if f >= lv), None)
    if fl and fl - lv <= 3:
        tips.append(f'Flask upgrade due at level {fl}')
    bt = next((b for b in BOOT_STEPS if b[0] > lv), None)
    if bt and bt[0] - lv <= 4:
        tips.append(f'Boots with {bt[1]}% movement speed from about level {bt[0]}')
    act = card.get('act') or ''
    for x in data()['acts']:
        if x['act'] == act:
            tips += [t['text'] for t in (x.get('tips') or [])[:2]]
            card['keep'] = [t['text'] for t in (x.get('do_not_skip') or [])][:4]
    card['tips'] = tips[:4]
    return card

# ---------------- the panel's size (the page reports it; overlay.pyw fits the window) ----------------

_size = {'ver': 0}


def set_size(b):
    keep = {k: float(b[k]) for k in ('need', 'innerH', 'innerW', 'dpr') if isinstance(b.get(k), (int, float))}
    if keep and any(_size.get(k) != v for k, v in keep.items()):
        _size.update(keep)
        _size['ver'] += 1
    return {'ok': True}


def size():
    return dict(_size)
