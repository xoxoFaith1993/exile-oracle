"""Build Lab: the dashboard's war room for one build. Claude does the thinking through the tools; this module turns a
vault build and its saved plan into what the Lab page draws.

Stage 1, the living roadmap: the levelling route node by node (with the level each is taken at), ascendancy nodes,
gem timing (skills with their supports and level ranges), gear targets by level band, quest point and trial levels.
"""

import re

from . import buildplan, config, route

TAG = re.compile(r'<[a-z]+>\{|\}')


def _plain(text):
    """The Build Planner's markup ("<grey>{Take at level 3}") as plain lines."""
    return [l.strip() for l in TAG.sub('', text or '').splitlines() if l.strip()]


def _gem_name(gid):
    """'Metadata/Items/Gems/SkillGemSpark' -> 'Spark' (PoB's own gem names when known)."""
    buildplan._gem_index()
    n = buildplan._names.get(gid or '')
    if n:
        return ' '.join(w if w in ('of', 'the', 'and', 'on', 'to') else w.upper() if w in ('i', 'ii', 'iii', 'iv', 'v')
                        else w[:1].upper() + w[1:] for w in n.split())
    base = (gid or '').rsplit('/', 1)[-1]
    base = re.sub(r'^(SkillGem|SupportGem)', '', base)
    return re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', base) or gid


def roadmap(con, build_id):
    build_id = int(build_id)
    r = con.execute('SELECT id, label, ascendancy, main_skill, level FROM build WHERE id=?', (build_id,)).fetchone()
    if not r:
        raise ValueError('no such build in the vault')
    st = buildplan.get(con, build_id)
    out = buildplan.export(con, build_id, write=False, route=True)
    doc, rep = out['doc'], out['report']
    skills = []
    for s in doc.get('skills') or []:
        lo, hi = s.get('level_interval') or [1, 100]
        sups = [x if isinstance(x, dict) else {'id': x} for x in s.get('support_skills') or []]   # plain ids too
        skills.append({'id': s.get('id'), 'name': _gem_name(s.get('id')), 'from': lo, 'to': hi, 'note': ' '.join(_plain(s.get('additional_text'))),
                       'supports': [{'id': x.get('id'), 'name': _gem_name(x.get('id')), 'from': (x.get('level_interval') or [lo, hi])[0],
                                     'to': (x.get('level_interval') or [lo, hi])[1]} for x in sups]})
    gear = []
    for g in doc.get('inventory_slots') or []:
        lo, hi = g.get('level_interval') or [1, 100]
        lines = _plain(g.get('additional_text'))
        gear.append({'slot': g.get('inventory_id'), 'from': lo, 'to': hi, 'lines': [l for l in lines if not set(l) <= set('-')]})
    quests = [{'level': q['level'], 'area': q['area'], 'act': q['act'], 'points': q['points'], 'who': q['who']}
              for q in route.quest_reminders() if q.get('points')]
    return {
        'build': {'id': build_id, 'label': r['label'], 'ascendancy': r['ascendancy'], 'main_skill': r['main_skill'],
                  'level': r['level']},
        'reviewed': bool(st.get('levelling_route')),
        'follow': st.get('follow'),
        'tree_version': rep.get('tree_version') or '0_5',
        'start': rep.get('route_start'),
        'route': rep.get('route_nodes') or [],
        'asc': rep.get('asc_nodes') or [],
        'skills': skills,
        'gear': gear,
        'quests': quests,
        'trials': route.TRIAL_LEVELS,
        'points': [route.points_at(l) for l in range(1, 101)],
        'warnings': rep.get('edit_warnings') or [],
    }


# ---------------- stage 2: power curves (Path of Building, background) ----------------

CURVE_LEVELS = [5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
UTILITY = ('warp', 'blink', 'remnants', 'curse', 'weakness', 'temporal', 'despair', 'presence', 'aura', 'herald',
           'armour', 'consecrate', 'blasphemy', 'ward', 'shield', 'leap', 'dash', 'conductivity', 'flammability',
           'hypothermia', 'vulnerability', 'enfeeble', 'cast on', 'sacrifice', 'barrier')
_jobs = {}   # build_id -> {'status', 'done', 'total', 'error'}


def _key(build_id, st):
    import hashlib
    import json
    return 'lab:curves:%d:%s' % (int(build_id), hashlib.sha1(json.dumps(st.get('edits') or {}, sort_keys=True).encode()).hexdigest()[:10])


def curves_state(con, build_id):
    """Saved curves for this build (and its current edits), or the running job's progress."""
    import json
    from . import db
    st = buildplan.get(con, build_id)
    saved = db.kv_get(con, _key(build_id, st))
    job = _jobs.get(int(build_id))
    if job and job['status'] == 'running':
        return dict(job, points=None)
    if saved:
        return dict(json.loads(saved), status='done')
    return dict(job or {}, status=(job or {}).get('status') or 'none')


def start_curves(build_id):
    """Run the curves in a background thread (about a minute); poll curves_state."""
    import threading
    build_id = int(build_id)
    if (_jobs.get(build_id) or {}).get('status') == 'running':
        return _jobs[build_id]
    _jobs[build_id] = {'status': 'running', 'done': 0, 'total': len(CURVE_LEVELS) + 1}
    threading.Thread(target=_run_curves, args=(build_id,), daemon=True).start()
    return _jobs[build_id]


def _run_curves(build_id):
    import json
    import time
    from . import db, pob, stagecheck, vault
    job = _jobs[build_id]
    try:
        con = db.connect()
        rm = roadmap(con, build_id)
        st = buildplan.get(con, build_id)
        code = con.execute('SELECT pob_code FROM build WHERE id=?', (build_id,)).fetchone()['pob_code']
        xml, _w = buildplan.apply_edits(vault.decode(code), st.get('edits'))
        points = []
        for L in CURVE_LEVELS:
            best = None
            active = [s for s in rm['skills'] if s['from'] <= L <= s['to'] and s.get('id')
                      and not any(u in s['name'].lower() for u in UTILITY)]
            for s in active[:4]:
                sups = tuple(x['id'] for x in s['supports'] if x.get('id') and x['from'] <= L <= x['to'])
                try:
                    r = stagecheck.check(xml, L, s['id'], sups)
                except Exception:
                    continue
                if best is None or (r.get('dps') or 0) > (best.get('dps') or 0):
                    best = dict(r, skill=s['name'])
            if best is None:   # nothing to test: still record life / mana from a bare run
                try:
                    best = dict(stagecheck.check(xml, L, '', ()), skill=None)
                except Exception:
                    best = {'level': L}
            points.append({'level': L, 'skill': best.get('skill'), 'dps': best.get('dps') or 0,
                           'life': best.get('life') or 0, 'es': best.get('es') or 0, 'mana': best.get('mana') or 0,
                           'ehp': best.get('ehp')})
            job['done'] += 1
        geared = None
        try:   # the finished build with its own gear: where the curve is heading
            res = pob.calc(xml, use_cache=True)
            k = pob.key_stats(res)
            geared = {'level': rm['build']['level'], 'skill': res.get('main_skill'),
                      'dps': k.get('DPS (combined)') or k.get('DPS (main skill)') or 0, 'life': k.get('life') or 0,
                      'es': k.get('energy shield') or 0, 'ehp': k.get('effective HP')}
        except Exception:
            pass
        job['done'] += 1
        out = {'points': points, 'geared': geared, 'ts': time.time(), 'note':
               'Path of Building, no gear: the route\'s passives by each level and the best levelling skill then. '
               'Gear only adds, so these are floors.'}
        db.kv_set(con, _key(build_id, st), json.dumps(out))
        job['status'] = 'done'
    except Exception as e:
        job.update(status='error', error=f'{type(e).__name__}: {e}')


# ---------------- stage 3: what-if bench (suggestion cards measured by Path of Building) ----------------

STATS = ['DPS (combined)', 'DPS (main skill)', 'effective HP', 'life', 'energy shield', 'mana', 'spirit',
         'max hit: physical', 'max hit: fire', 'max hit: cold', 'max hit: lightning', 'max hit: chaos',
         'fire res', 'cold res', 'lightning res', 'chaos res', 'movement speed x']


def _cards_key(build_id):
    return 'lab:cards:%d' % int(build_id)


def cards(con, build_id):
    import json
    from . import db
    return json.loads(db.kv_get(con, _cards_key(build_id)) or '[]')


def _save_cards(con, build_id, cs):
    import json
    from . import db
    db.kv_set(con, _cards_key(build_id), json.dumps(cs[-40:]))


def measure(con, build_id, change):
    """change: {"item": {"slot", "item_text"}} and/or {"edits": {add_passives, remove_passives, swap_gems}}.
    Before = the build with its saved plan edits; after = that plus the change. Returns the stat deltas."""
    from . import pob, vault
    r = con.execute('SELECT pob_code FROM build WHERE id=?', (int(build_id),)).fetchone()
    if not r:
        raise ValueError('no such build in the vault')
    cur = buildplan.get(con, build_id).get('edits') or {}
    base = vault.decode(r['pob_code'])
    before_xml, _ = buildplan.apply_edits(base, cur)
    warnings = []
    after_xml = before_xml
    if change.get('edits'):
        merged = {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v) for k, v in cur.items()}
        for k, v in change['edits'].items():
            if isinstance(v, list):
                merged[k] = list(dict.fromkeys((merged.get(k) or []) + v))
            elif isinstance(v, dict):
                merged.setdefault(k, {}).update(v)
        after_xml, warnings = buildplan.apply_edits(base, merged)
    if change.get('item'):
        it = change['item']
        after_xml = pob.swap_item(after_xml, it['slot'], it['item_text'])
    a = pob.calc(before_xml, use_cache=True)
    b = pob.calc(after_xml, use_cache=True, main_group=a.get('main_group'))
    sa, sb = pob.key_stats(a), pob.key_stats(b)
    delta = {}
    for k in STATS:
        if k in sa or k in sb:
            x, y = sa.get(k) or 0, sb.get(k) or 0
            if x != y:
                delta[k] = {'before': x, 'after': y, 'pct': round((y / x - 1) * 100, 1) if x else None}
    return {'delta': delta, 'main_skill': b.get('main_skill'), 'warnings': warnings + (b.get('warnings') or [])[:3]}


def suggest(con, build_id, title, change, why='', cost_div=None, source='oracle'):
    """Add a suggestion card and measure it now (a few seconds of Path of Building)."""
    import time
    cs = cards(con, build_id)
    card = {'id': int(time.time() * 1000), 'ts': time.time(), 'title': title, 'why': why, 'change': change,
            'cost_div': cost_div, 'source': source}
    try:
        card['result'] = measure(con, build_id, change)
    except Exception as e:
        card['error'] = f'{type(e).__name__}: {e}'
    cs.append(card)
    _save_cards(con, build_id, cs)
    return card


def retest(con, build_id, card_id):
    import time
    cs = cards(con, build_id)
    for c in cs:
        if c['id'] == int(card_id):
            try:
                c['result'] = measure(con, build_id, c['change'])
                c.pop('error', None)
            except Exception as e:
                c['error'] = f'{type(e).__name__}: {e}'
            c['retested'] = time.time()
            _save_cards(con, build_id, cs)
            return c
    raise ValueError('no such card')


def remove_card(con, build_id, card_id):
    cs = [c for c in cards(con, build_id) if c['id'] != int(card_id)]
    _save_cards(con, build_id, cs)
    return {'ok': True, 'left': len(cs)}


# ---------------- stage 4: upgrade ranking (the upgrade finder, shown on the Lab) ----------------

def upgrades(con, build_id, budget_div=10):
    """Uniques that fit the budget, ranked; plus a 'path': the best value pick per slot in order, with the running
    cost and the projected DPS (upgrades multiplied together: a rough projection, PoB tests each one alone)."""
    from . import upgrades as up
    r = up.find(con, build_id=int(build_id), budget_div=budget_div, top=6)
    seen, rows = set(), []
    for x in (r.get('best_value_damage_upgrades') or []) + (r.get('biggest_damage_upgrades') or []):
        k = (x.get('slot'), x.get('item'))
        if k not in seen:
            seen.add(k)
            rows.append(x)
    path, used, cost, mult = [], set(), 0.0, 1.0
    for x in sorted([x for x in rows if (x.get('dps_pct') or 0) > 0 and not x.get('loses_res_cap')],
                    key=lambda x: -(x.get('dps_pct_per_div') or 0)):
        if x['slot'] in used:
            continue
        used.add(x['slot'])
        cost += x.get('price_div') or 0
        mult *= 1 + (x.get('dps_pct') or 0) / 100
        path.append({'slot': x['slot'], 'item': x['item'], 'price_div': x.get('price_div') or 0, 'dps_pct': x['dps_pct'],
                     'cost_so_far': round(cost, 2), 'dps_after': round((r.get('baseline') or {}).get('dps', 0) * mult)})
    return {'baseline': r.get('baseline'), 'budget_div': budget_div, 'considered': r.get('uniques_considered'),
            'rows': rows, 'path': path, 'notes': r.get('notes') or []}


# ---------------- stage 5: defence sheet ----------------

RES_CAP = 75


def defence(con, build_id):
    """The geared build's defences from Path of Building, with the gaps flagged."""
    from . import pob, vault
    r = con.execute('SELECT pob_code FROM build WHERE id=?', (int(build_id),)).fetchone()
    if not r:
        raise ValueError('no such build in the vault')
    xml, _ = buildplan.apply_edits(vault.decode(r['pob_code']), buildplan.get(con, build_id).get('edits'))
    res = pob.calc(xml, use_cache=True)
    k = pob.key_stats(res)
    hits = {t: k.get(f'max hit: {t}') for t in ('physical', 'fire', 'cold', 'lightning', 'chaos')}
    hits = {t: v for t, v in hits.items() if v is not None}
    flags = []
    for t in ('fire', 'cold', 'lightning'):
        v = k.get(f'{t} res')
        if v is not None and v < RES_CAP:
            flags.append({'level': 'bad', 'text': f'{t.title()} resistance {v:g}% is under the {RES_CAP}% cap'})
    ch = k.get('chaos res')
    if ch is not None and ch < 0:
        flags.append({'level': 'warn', 'text': f'Chaos resistance is negative ({ch:g}%)'})
    if hits:
        lo_t = min(hits, key=hits.get)
        others = sorted(v for t, v in hits.items() if t != lo_t)
        if others and hits[lo_t] < 0.5 * others[len(others) // 2]:
            flags.append({'level': 'warn', 'text': f'Your weakest hit is {lo_t} ({hits[lo_t]:,.0f}): under half of the others'})
    return {'main_skill': res.get('main_skill'), 'level': res.get('level'), 'stats': k, 'max_hits': hits, 'flags': flags,
            'warnings': (res.get('warnings') or [])[:3]}


# ---------------- stage 7: history ----------------

def _char_name(label):
    return re.split(r' \(| - ', label or '', 1)[0].strip()


def history(con, build_id):
    """The character behind this build over time: every vault snapshot of it (Path of Building numbers, cached) and
    the level-ups the game log saw. Grows as the player re-imports and plays."""
    from . import pob, vault
    b = con.execute('SELECT label, owner FROM build WHERE id=?', (int(build_id),)).fetchone()
    if not b:
        raise ValueError('no such build in the vault')
    st = buildplan.get(con, build_id)
    name = st.get('follow') or _char_name(b['label'])
    snaps = []
    for r in con.execute('SELECT id, label, level, added, pob_code FROM build ORDER BY added'):
        if _char_name(r['label']).lower() != name.lower():
            continue
        try:
            k = pob.key_stats(pob.calc(vault.decode(r['pob_code']), use_cache=True))
        except Exception:
            k = {}
        snaps.append({'id': r['id'], 'label': r['label'], 'level': r['level'], 'ts': r['added'],
                      'dps': k.get('DPS (combined)') or k.get('DPS (main skill)'), 'ehp': k.get('effective HP'),
                      'life': k.get('life'), 'es': k.get('energy shield')})
    for a, b2 in zip(snaps, snaps[1:]):   # what changed between two snapshots, in words
        notes = []
        for key, label in (('dps', 'DPS'), ('ehp', 'EHP')):
            x, y = a.get(key), b2.get(key)
            if x and y and abs(y / x - 1) >= 0.05:
                notes.append(f"{label} {'+' if y > x else ''}{(y / x - 1) * 100:.0f}%")
        if (b2.get('level') or 0) > (a.get('level') or 0):
            notes.append(f"level {a['level']} → {b2['level']}")
        b2['change'] = ', '.join(notes)
    levels = [{'ts': t, 'level': int(c)} for t, a2, c in
              con.execute("SELECT ts, a, c FROM log_event WHERE kind='levelup' ORDER BY ts")
              if (a2 or '').lower() == name.lower() and str(c).isdigit()]
    return {'character': name, 'snapshots': snaps, 'levels': levels}


# ---------------- stage 6: boss readiness (researched thresholds, datapack/boss-readiness.json) ----------------

STAT_OF = {'dps': lambda k: k.get('DPS (combined)') or k.get('DPS (main skill)'), 'effective_hp': lambda k: k.get('effective HP'),
           'life_es': lambda k: (k.get('life') or 0) + (k.get('energy shield') or 0)}
for _t in ('physical', 'fire', 'cold', 'lightning', 'chaos'):
    STAT_OF[f'max_hit_{_t}'] = (lambda t: lambda k: k.get(f'max hit: {t}'))(_t)
for _t in ('fire', 'cold', 'lightning', 'chaos'):
    STAT_OF[f'{_t}_res'] = (lambda t: lambda k: k.get(f'{t} res'))(_t)


def readiness(con, build_id):
    """Per boss: ready / risky / not yet, from Path of Building's numbers against researched thresholds."""
    import json
    from . import config
    p = config.data_file('boss-readiness.json')
    if not p:
        raise FileNotFoundError('boss-readiness.json is missing from the data pack')
    data = json.load(open(p, encoding='utf-8'))
    d = defence(con, build_id)
    k = d['stats']
    rank = {'ready': 0, 'risky': 1, 'not yet': 2, 'unknown': -1}
    bosses = []
    for b in data['bosses']:
        checks = []
        for c in b['checks']:
            f = STAT_OF.get(c['stat'])
            v = f(k) if f else None
            if v is None:
                state = 'unknown'
            elif v >= c['min']:
                state = 'ready'
            elif v >= (c.get('risky_below') if c.get('risky_below') is not None else c['min']):
                state = 'risky'
            else:
                state = 'not yet'
            checks.append({'stat': c['stat'], 'value': v, 'min': c['min'], 'risky_below': c.get('risky_below'),
                           'unit': c.get('unit'), 'why': c.get('why'), 'confidence': c.get('confidence'),
                           'estimated': 'estimat' in (c.get('source') or '').lower() or c.get('confidence') == 'low',
                           'state': state})
        worst = max((rank[c['state']] for c in checks), default=-1)
        bosses.append({'name': b['name'], 'tier': b['tier'], 'unlock': b.get('unlock'),
                       'hits': b.get('dangerous_hits') or [], 'state': {v: s for s, v in rank.items()}.get(worst, 'unknown'),
                       'checks': checks})
    return {'version_note': data.get('version_note'), 'level': d.get('level'), 'main_skill': d.get('main_skill'),
            'bosses': bosses, 'sources': data.get('sources') or []}
