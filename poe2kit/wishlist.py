"""Chase-item wishlist (R25): items the player wants to buy (or sell) at a target price.

Each wish: an item name as poe.ninja / the Currency Exchange call it, a target price (stored in Divines; the player
can type it in ex or div) and a side: "buy" (tell me when it drops to the target) or "sell" (when it rises to it).

Three kinds of news, all on the dashboard only (Alerts page + Home omen, never in game):
  hit       the live price reached the target;
  heading   the price forecast (past launches, poe2kit/forecast.py) puts the target inside next week's likely range;
  patch     the newest stored patch notes, read by the patch prophecy, call a move for the item or its family.
Each one alerts once (a hit again only after the price left the target and came back)."""

import json
import time

from . import db

KEY = 'wishlist'
MAX = 60


def _load(con):
    try:
        w = json.loads(db.kv_get(con, KEY) or '[]')
        return [x for x in w if isinstance(x, dict) and x.get('name')]
    except ValueError:
        return []


def _save(con, w):
    db.kv_set(con, KEY, json.dumps(w[:MAX]))
    con.commit()


def names(con):
    """Lower-case names on the wishlist (the monitor also watches them for big moves)."""
    return {x['name'].lower() for x in _load(con)}


def price_of(con, name, league=None):
    """Newest stored price row for this exact item name (else the best partial match)."""
    from . import ninja
    rows = ninja.latest(con, name, league, 25)
    exact = [r for r in rows if r['name'].lower() == name.lower()]
    return (exact or rows or [None])[0]


def _to_div(con, value, unit, league=None):
    from . import money, ninja
    if unit == 'ex':
        rt = money.rates(con, league or ninja.current_league(con)) or {}
        if not rt.get('ex_per_div'):
            raise ValueError('no Exalted price yet: give the target in div')
        return value / rt['ex_per_div']
    return value


def add(con, name, target, unit='div', side='buy', note=''):
    name = (name or '').strip()
    if not name:
        return {'ok': False, 'error': 'Which item?'}
    try:
        target = float(target)
        if target <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return {'ok': False, 'error': 'The target must be a price above 0.'}
    row = price_of(con, name)
    if row is None:
        return {'ok': False, 'error': f'"{name}" has no price stored. Check the spelling (as on poe.ninja).'}
    try:
        tdiv = _to_div(con, target, unit)
    except ValueError as e:
        return {'ok': False, 'error': str(e)}
    side = 'sell' if side == 'sell' else 'buy'
    w = [x for x in _load(con) if x['name'].lower() != row['name'].lower()]
    w.insert(0, {'name': row['name'], 'target_div': tdiv, 'side': side, 'unit': 'ex' if unit == 'ex' else 'div',
                 'note': (note or '')[:200], 'added': time.time(), 'icon': row['icon']})
    if len(w) > MAX:
        return {'ok': False, 'error': f'The wishlist holds {MAX} items: remove one first.'}
    _save(con, w)
    return {'ok': True, 'name': row['name'], 'target_div': tdiv, 'side': side}


def remove(con, name):
    w = _load(con)
    left = [x for x in w if x['name'].lower() != (name or '').lower()]
    _save(con, left)
    for k in ('hit', 'heading', 'patch'):
        db.kv_set(con, f'wish:{k}:{(name or "").lower()}', '')
    return {'ok': len(left) < len(w)}


def _forecast(con, name, now_div):
    try:
        from . import prophecy
        f = prophecy.forecast_item(con, name, price=now_div)
        h = f.get('horizons') or {}
        return h.get(7) or h.get('7')
    except Exception:
        return None


def _heading(w, h7):
    """Does next week's likely range reach the target? 'likely' (the median does) or 'maybe' (1 in 4 does)."""
    if not h7:
        return None
    t = w['target_div']
    if w['side'] == 'buy':
        return 'likely' if h7['median'] <= t else 'maybe' if h7['p25'] <= t else None
    return 'likely' if h7['median'] >= t else 'maybe' if h7['p75'] >= t else None


def _family(name):
    """'Omen of Light' -> 'omen', 'Essence of Haste' -> 'essence': patch calls often name the family, not the item."""
    return name.split(' of ')[0].strip().lower() if ' of ' in name else None


def _patch_calls(con, w, pp):
    if not pp:
        return []
    n, fam = w['name'].lower(), _family(w['name'])
    out = []
    for e in pp.get('items') or []:
        g = (e.get('item') or '').lower()
        for c in e['calls']:
            if n in (c.get('line') or '').lower() or n in g or (fam and len(fam) >= 4 and fam in g):
                out.append({'group': e['item'], 'direction': c['direction'], 'move_pct': c.get('move_pct'),
                            'confidence': c.get('confidence'), 'line': c.get('line')})
    return out[:3]


def status(con, league=None, with_forecast=True):
    """Every wish with its live price, distance to the target, the forecast's view and patch calls."""
    from . import money, ninja, prophecy
    league = league or ninja.current_league(con)
    rt = money.rates(con, league)
    try:
        pp = prophecy.latest_patch_prophecy(con)
    except Exception:
        pp = None
    out = []
    for w in _load(con):
        r = price_of(con, w['name'], league)
        now = r['value'] if r else None
        e = dict(w, price_div=now, price=money.fmt(now, rt) if now else None, target=money.fmt(w['target_div'], rt),
                 as_of=r['ts'] if r else None)
        if now:
            e['away_pct'] = round((w['target_div'] / now - 1) * 100, 1)
            e['hit'] = now <= w['target_div'] if w['side'] == 'buy' else now >= w['target_div']
        h7 = _forecast(con, w['name'], now) if with_forecast and now else None
        if h7:
            e['week'] = {'low': money.fmt(h7['p25'], rt), 'mid': money.fmt(h7['median'], rt), 'high': money.fmt(h7['p75'], rt),
                         'change_pct': h7.get('change_pct')}
            e['heading'] = None if e.get('hit') else _heading(w, h7)
        e['patch'] = _patch_calls(con, w, pp)
        e['patch_title'] = pp.get('title') if pp and e['patch'] else None
        out.append(e)
    return {'league': league, 'items': out, 'max': MAX,
            'note': 'Prices from poe.ninja (uniques: the cheapest roll). "Heading there": the price forecast from past '
                    'launches puts your target inside next week\'s likely range (a range, not a promise).'}


def check(con, alert):
    """Run with the monitor's price job: alert once per hit / forecast / patch call."""
    st = status(con)
    for e in st['items']:
        k = e['name'].lower()
        verb = 'dropped to' if e['side'] == 'buy' else 'rose to'
        if e.get('hit'):
            if db.kv_get(con, f'wish:hit:{k}') != '1':
                db.kv_set(con, f'wish:hit:{k}', '1')
                alert(con, 'wish', f"{e['name']} {verb} your target: {e['price']}",
                      f"Your wishlist target is {e['target']} ({'buy' if e['side'] == 'buy' else 'sell'}). "
                      'Check the trade site or exchange before you act: prices move.')
        else:
            db.kv_set(con, f'wish:hit:{k}', '')
        if e.get('heading'):
            day = time.strftime('%Y-%W')
            if db.kv_get(con, f'wish:heading:{k}') != day:   # at most once a week per item
                db.kv_set(con, f'wish:heading:{k}', day)
                w = e['week']
                alert(con, 'wish', f"{e['name']} may reach your target this week" if e['heading'] == 'maybe'
                      else f"{e['name']} is heading to your target",
                      f"Now {e['price']}, target {e['target']}. Next week's likely range from past launches: "
                      f"{w['low']} to {w['high']} (middle {w['mid']}).")
        for c in e.get('patch') or []:
            tag = f"{e.get('patch_title')}|{c['group']}"
            if db.kv_get(con, f'wish:patch:{k}') != tag:
                db.kv_set(con, f'wish:patch:{k}', tag)
                mv = f" about {c['move_pct']:+.0f}%" if isinstance(c.get('move_pct'), (int, float)) else ''
                alert(con, 'wish', f"Patch call for {e['name']}: {c['direction']}{mv}",
                      f"{e.get('patch_title') or 'The latest patch notes'}: \"{(c.get('line') or '')[:200]}\" "
                      f"({c['group']}, confidence {c.get('confidence') or '?'}). From the patch prophecy.")
            break
    con.commit()
    return len(st['items'])


def omen(con):
    """For the Home omen: the strongest wishlist news right now, or None."""
    try:
        st = status(con)
    except Exception:
        return None
    hits = [e for e in st['items'] if e.get('hit')]
    if hits:
        e = hits[0]
        return {'kind': 'wish', 'title': f"{'Buy' if e['side'] == 'buy' else 'Sell'} {e['name']}: it's at your target",
                'text': f"Now {e['price']}, your target {e['target']}.",
                'evidence': 'From your wishlist (Wishlist page). Check the trade site or exchange first.', 'confidence': 'high',
                'item': e['name']}
    near = [e for e in st['items'] if e.get('heading') == 'likely']
    if near:
        e = near[0]
        return {'kind': 'wish', 'title': f"{e['name']} is heading to your target",
                'text': f"Now {e['price']}, target {e['target']}; next week likely {e['week']['low']} to {e['week']['high']}.",
                'evidence': 'Price forecast from past launches (a range, not a promise).', 'confidence': 'medium',
                'item': e['name']}
    return None
