"""The Oracle that tells the future (R14): league timeline, countdowns, the daily omen, price forecasts with past
launches, patch prophecy, the farming oracle and chase-unique history.

Everything here is our own research, shipped in the data pack (research/ has the code that built it):
  forecast-model.json   price forecast for 688 exchange items from six PoE 2 launches (poe2kit.forecast)
  league-start.json     the first 72 hours of three launches: plan, sell windows, early buys, fast fallers
  patch-impact.json     276 patches matched to the price moves after them; the rules (poe2kit.patchrules)
  farming.json          div / hour per strategy per league phase, with build requirements
  unique-history.json   chase uniques by league day over five leagues, patterns and rules
Honesty: every call carries its evidence count and confidence; "history, not a promise"; patches override it.
"""

import calendar
import json
import re
import time

from . import config

LAUNCH_1_0 = calendar.timegm((2026, 12, 11, 20, 0, 0))     # 1.0: December 11; launches have been ~20:00 UTC
NOTES_1_0 = calendar.timegm((2026, 12, 4, 20, 0, 0))       # patch notes about a week before (estimate)
FARM_PHASES = [('d0-2', 0, 3), ('week1', 3, 10), ('wk2-3', 10, 25), ('wk4-8', 25, 60), ('late', 60, 10 ** 6)]
_cache = {}


def _load(name):
    if name not in _cache:
        p = config.data_file(name)
        if not p:
            raise FileNotFoundError(f'{name} is missing from the data pack')
        _cache[name] = json.load(open(p, encoding='utf-8'))
    return _cache[name]


def league_day(con, league=None):
    """(league, day as a float or None, league start epoch or None)."""
    from . import ninja, oracle
    league = league or ninja.current_league(con)
    start = oracle.league_start(con, league)
    return league, ((time.time() - start) / 86400 if start else None), start


def farm_phase(day):
    for key, a, b in FARM_PHASES:
        if a <= (day or 0) < b:
            return key
    return 'late'


# ---------------- timeline + countdowns ----------------

def _day_range(text):
    """'Day 0-2: ...' / 'Week 1: ...' / 'By day 7' -> (from, to) days, or None."""
    t = text.lower()
    m = re.match(r'\s*days? (\d+)\s*[-–]\s*(\d+)', t)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.match(r'\s*days? (\d+)\+?', t)
    if m:
        return float(m.group(1)), float(m.group(1)) + 1
    m = re.match(r'\s*weeks? (\d+)\s*[-–]\s*(\d+)', t)
    if m:
        return (int(m.group(1)) - 1) * 7.0, int(m.group(2)) * 7.0
    m = re.match(r'\s*week (\d+)', t)
    if m:
        return (int(m.group(1)) - 1) * 7.0, int(m.group(1)) * 7.0
    return None


def timeline(con=None, league=None):
    """What usually happens when, day 0 -> 70+, with where we are now."""
    from . import oracle
    ev = []
    for b in _load('league-start.json').get('plan_72h', []):
        ev.append({'from': b['from_hour'] / 24, 'to': b['to_hour'] / 24, 'kind': 'plan',
                   'title': f"Hours {b['from_hour']}-{b['to_hour']}", 'text': b['actions'][0] if b.get('actions') else '',
                   'more': b.get('actions', [])[1:], 'why': b.get('why')})
    for s in oracle.data().get('strategies', []):
        ph = next((p for p in oracle.PHASES if p[0] == s.get('phase')), None)
        if ph:
            ev.append({'from': ph[1], 'to': min(ph[2], 77), 'kind': 'market', 'title': ph[0].capitalize(),
                       'text': s['action'], 'why': s.get('why'), 'confidence': s.get('confidence')})
    for r in _load('unique-history.json').get('oracle_rules', []):
        dr = _day_range(r)
        if dr:
            ev.append({'from': dr[0], 'to': dr[1], 'kind': 'uniques', 'title': 'Chase uniques', 'text': r})
    best = _load('farming.json').get('best_by_phase', {})
    for key, a, b in FARM_PHASES:
        if best.get(key):
            top = best[key][0]
            ev.append({'from': a, 'to': min(b, 77), 'kind': 'farm', 'title': 'Best farm',
                       'text': f"{top['name']}: about {top['mid']:g} div/h (range {top['low']:g}-{top['high']:g})"})
    ev.sort(key=lambda e: (e['from'], e['to']))
    out = {'events': ev, 'phases': [{'name': p[0], 'from': p[1], 'to': min(p[2], 77)} for p in oracle.PHASES]}
    if con is not None:
        lg, day, start = league_day(con, league)
        out.update(league=lg, day=round(day, 2) if day is not None else None)
    return out


def countdowns(con=None, league=None):
    now = time.time()
    out = []
    if now < LAUNCH_1_0:
        if now < NOTES_1_0:
            out.append({'label': '1.0 patch notes (expected)', 'at': NOTES_1_0, 'estimate': True})
        out.append({'label': '1.0 launches', 'at': LAUNCH_1_0})
    if con is not None:
        lg, day, start = league_day(con, league)
        if start and day is not None:
            hour = day * 24
            for b in _load('league-start.json').get('plan_72h', []):
                if b['from_hour'] <= hour < b['to_hour']:
                    out.append({'label': f"this part of the 72-hour plan ends (hours {b['from_hour']}-{b['to_hour']})",
                                'at': start + b['to_hour'] * 3600})
            if hour < 20:
                out.append({'label': 'the Exalted → Divine swap window closes', 'at': start + 20 * 3600})
            from . import oracle
            nxt = next((p for p in oracle.PHASES if p[1] > day), None)
            if nxt:
                out.append({'label': f'{nxt[0]} starts', 'at': start + nxt[1] * 86400})
    for c in out:
        c['in_hours'] = round((c['at'] - now) / 3600, 1)
    out.sort(key=lambda c: c['at'])
    return out


# ---------------- the daily omen ----------------

def omen(con, league=None):
    """Today's strongest call, with its evidence. Before 1.0: what to prepare."""
    from . import oracle
    lg, day, start = league_day(con, league)
    now = time.time()
    if now < LAUNCH_1_0 and (day is None or day > 30):
        days = (LAUNCH_1_0 - now) / 86400
        plan = _load('league-start.json').get('plan_72h', [])
        first = plan[1]['actions'][1] if len(plan) > 1 and len(plan[1].get('actions', [])) > 1 else ''
        return {'kind': 'prepare', 'title': f'1.0 in {days:.0f} days: get ready for hour 3',
                'text': first or 'Plan your first 72 hours on the League start page.',
                'evidence': 'In 3 of 3 launches, Exalted Orbs lost 64-85% against Divines in the first week.',
                'confidence': 'high', 'day': round(day, 1) if day is not None else None, 'league': lg}
    if day is not None and day < 3:
        hour = day * 24
        for b in _load('league-start.json').get('plan_72h', []):
            if b['from_hour'] <= hour < b['to_hour']:
                return {'kind': 'plan', 'title': f"Hour {hour:.0f}: {b['actions'][0]}", 'text': ' '.join(b['actions'][1:3]),
                        'evidence': b.get('why'), 'confidence': 'high', 'day': round(day, 1), 'league': lg}
    adv = oracle.advice(con, lg)
    sells = [x for x in adv.get('items') or [] if 'sell' in (x.get('verdict') or '') and (x.get('change_pct') or 0) < 0]
    if sells:
        x = min(sells, key=lambda x: x.get('change_pct') or 0)
        return {'kind': 'sell', 'title': f"Sell {x['item']} now",
                'text': f"In the last launches it fell about {abs(x['change_pct'])}% over the next week from this point of the league.",
                'evidence': f"{x.get('leagues', 1)} of {len(oracle.data().get('curves_div', {}).get(x['item'], {})) or 3} launches",
                'confidence': 'medium' if (x.get('leagues') or 1) >= 2 else 'low', 'day': adv.get('day'), 'league': lg, 'item': x['item']}
    do = (adv.get('do_now') or [None])[0]
    if do:
        return {'kind': 'market', 'title': do['action'].split(':')[0].split('.')[0], 'text': do['action'],
                'evidence': do.get('why'), 'confidence': do.get('confidence'), 'day': adv.get('day'), 'league': lg}
    return {'kind': 'none', 'title': 'The Oracle is quiet today', 'text': adv.get('note') or '', 'day': adv.get('day'), 'league': lg}


# ---------------- price forecast with past launches ----------------

def forecast_item(con, item, league=None, day=None, price=None):
    from . import forecast, oracle
    if item.strip().lower() == 'divine orb':
        return {'item': item, 'error': 'Prices here are counted in Divine Orbs, so a Divine is always 1: pick another item (Exalted Orb shows the Divine against Exalts).', 'past': {}}
    lg, now_day, _ = league_day(con, league)
    day = now_day if day is None else float(day)
    live, chg7 = oracle._live(con, lg, item)
    price = price if price is not None else live
    past = oracle.data().get('curves_div', {}).get(item) or {}
    out = {'item': item, 'league': lg, 'day': round(day, 1) if day is not None else None, 'price_div': price,
           'change_7d_pct': chg7, 'past': {k: {int(d): v for d, v in c.items()} for k, c in past.items()}}
    try:
        out['typical'] = forecast._oracle().typical_path(item)
    except Exception:
        out['typical'] = {}
    if price and day is not None:
        try:
            f = forecast.forecast(item, day, price, chg7)
            out.update(horizons=f.get('horizons'), confidence=f.get('confidence'), basis=f.get('basis'),
                       notes=f.get('notes'), category=f.get('category'))
        except Exception as e:
            out['error'] = f'no forecast: {e}'
    else:
        out['error'] = 'no live price or league day yet'
    try:
        bt = forecast._oracle().m.get('backtest', {}).get('per_horizon', {})
    except Exception:
        bt = {}
    out['honesty'] = {h: {'range_holds_pct': round(100 * b.get('coverage_80', 0)),
                          'direction_right_pct': round(100 * b.get('direction_hit_rate_when_model_calls_10pct_move', 0))}
                      for h, b in bt.items()}
    return out


def forecast_items():
    from . import forecast, oracle
    try:
        names = sorted(set(forecast._oracle().m.get('items', {})) | set(oracle.data().get('curves_div', {})))
    except Exception:
        names = sorted(oracle.data().get('curves_div', {}))
    return names


# ---------------- patch prophecy ----------------

def patch_prophecy(text, con=None):
    """Patch notes in, expected price moves out (grouped by item), with the evidence behind each rule."""
    from . import patchrules
    day = None
    if con is not None:
        _, day, _ = league_day(con)
    lines = patchrules.classify_notes(text or '', league_day=day)
    items = {}
    for ln in lines:
        for h in ln['hits']:
            if h.get('direction') in (None, '') or h.get('class') == 'skill' and h.get('direction') not in ('buff', 'nerf'):
                continue
            g = h.get('affected_group') or '?'
            if 'unclear' in g and h.get('confidence') != 'high':   # no named item or mechanic: too vague to call
                continue
            e = items.setdefault(g, {'item': g, 'calls': []})
            e['calls'].append({'line': ln['line'], 'section': ln['section'], 'rule': h['rule'], 'direction': h['direction'],
                               'move_pct': h.get('expected_move_pct'), 'window': h.get('window'),
                               'confidence': h.get('confidence'), 'cases': h.get('n_cases'),
                               'spread': h.get('spread'), 'second_order': h.get('second_order')})
    rank = {'high': 0, 'medium': 1, 'low': 2}
    out = sorted(items.values(), key=lambda e: (min(rank.get(c['confidence'], 3) for c in e['calls']),
                                               -max(abs(c['move_pct'] or 0) for c in e['calls'])))
    return {'items': out, 'lines_read': len(text.splitlines()) if text else 0, 'lines_hit': len([l for l in lines if l['hits']]),
            'checklist': _load('patch-impact.json').get('reading_checklist', [])[:8]}


def latest_patch_prophecy(con, gid=None):
    """Stored patch notes (the app's patch-notes sync), newest first, run through the rules."""
    from . import patchnotes
    lst = patchnotes.listing(con)
    if not lst:
        return None
    r = patchnotes.get(con, gid or lst[0]['gid'])
    text = '\n'.join(x.get('text') or '' for x in r.get('all') or [])
    out = patch_prophecy(text, con)
    out.update(title=r.get('title'), gid=r.get('gid'), date=r.get('date'),
               others=[{'gid': x['gid'], 'title': x['title']} for x in lst[:10]])
    return out


# ---------------- farming oracle ----------------

def farm_oracle(con, build_id=None, day=None):
    """Strategies for now and the next phase, each checked against the build's PoB damage and toughness."""
    f = _load('farming.json')
    if day is None:
        _, day, _ = league_day(con)
    key = farm_phase(day)
    nxt = next((k for k, a, b in FARM_PHASES if a > (day or 0)), None)
    stats = {}
    if build_id:
        try:
            from . import lab
            stats = lab.defence(con, build_id)['stats']
        except Exception:
            stats = {}
    dps = stats.get('DPS (combined)') or stats.get('DPS (main skill)')
    ehp = stats.get('effective HP')

    def rows(k):
        out = []
        for s in f['strategies']:
            r = (s.get('div_per_hour') or {}).get(k)
            if not r:
                continue
            req = s.get('requirements') or {}
            ok = None
            if dps is not None and ehp is not None:
                ok = dps >= (req.get('dps_min') or 0) and ehp >= (req.get('ehp_min') or 0)
            out.append({'name': s['name'], 'mechanic': s.get('mechanic'), 'low': r.get('low'), 'mid': r.get('mid'),
                        'high': r.get('high'), 'dps_min': req.get('dps_min'), 'ehp_min': req.get('ehp_min'),
                        'needs': req.get('notes'), 'fits': ok, 'confidence': s.get('confidence'),
                        'label': s.get('div_per_hour_label') or s.get('number_label'), 'nerfs': s.get('nerfs'),
                        'caveat': s.get('caveat')})
        out.sort(key=lambda x: (x['fits'] is False, -(x['mid'] or 0)))
        return out
    return {'day': round(day, 1) if day is not None else None, 'phase': key,
            'phase_name': f['phases'].get(key), 'next_phase': nxt and f['phases'].get(nxt),
            'build': {'id': build_id, 'dps': dps, 'ehp': ehp} if build_id else None,
            'now': rows(key), 'next': rows(nxt) if nxt else [], 'caveats': f.get('caveats', [])[:4]}


# ---------------- chase uniques ----------------

def unique_history(name=None):
    u = _load('unique-history.json')
    if not name:
        return {'uniques': sorted(u['uniques']), 'rules': u.get('oracle_rules', []), 'patterns': u.get('patterns', []),
                'leagues': u.get('meta', {}).get('leagues'), 'mageblood_vs_temporalis': u.get('mageblood_vs_temporalis')}
    e = u['uniques'].get(name)
    if not e:
        return {'error': f'no history for {name}'}
    series = {lg: {int(d): v for d, v in c.items()} for lg, c in (e.get('leagues') or {}).items()}
    return {'name': name, 'base': e.get('base'), 'leagues': series,
            'patterns': [p for p in u.get('patterns', []) if name.split(' [')[0] in (p.get('uniques') or [])],
            'rules': u.get('oracle_rules', [])}
