"""Alerts the player chooses (the author, 2026-11-21: "make it so it alerts us for different and certain things").

Dashboard only: no pop-ups in game. Each kind can be switched on / off in Settings → Alerts, with its own threshold:

  mine      items in your builds (and your watch list) move           on, 15%
  market    real market moves (not thin-market spikes)               digest (one alert a day), or each, or off
  oracle    the Oracle's calls: a countdown under a day, the omen    on
            changing, a stored patch that hits your items
  patch     patch notes that hit your builds                         on
  news      GGG news                                                 on
  updates   app / data updates, PoB updates, install, saved builds   on

"Real" market move: it held on the last two checks (not one spike), the item trades (volume on the exchange or
listings on poe.ninja items), and it's worth at least the minimum on either side. Muted items never alert.
Both sides of a move are shown in the same unit."""

import json
import time

from . import config, db

DEFAULTS = {
    'mine': {'on': True, 'pct': 15},
    'market': {'mode': 'digest', 'pct': 40, 'min_div': 1, 'min_volume': 50, 'min_listings': 10, 'max_each': 10},
    'oracle': {'on': True},
    'patch': {'on': True},
    'news': {'on': True},
    'updates': {'on': True},
}
KIND_GROUP = {'price-mine': 'mine', 'price-market': 'market', 'digest': 'market', 'oracle': 'oracle', 'patch': 'patch',
              'news': 'news', 'update': 'updates', 'install': 'updates', 'pob': 'updates', 'ggg': 'updates',
              'build': 'updates'}


def settings():
    s = config.settings().get('alerts') or {}
    out = {k: dict(v, **(s.get(k) or {})) for k, v in DEFAULTS.items()}
    out['muted'] = [m for m in (s.get('muted') or []) if isinstance(m, str)][:200]
    return out


def save(b):
    cur = settings()
    for k, v in DEFAULTS.items():
        if isinstance(b.get(k), dict):
            for f, dv in v.items():
                if f in b[k]:
                    x = b[k][f]
                    if isinstance(dv, bool):
                        cur[k][f] = bool(x)
                    elif f == 'mode':
                        cur[k][f] = x if x in ('digest', 'each', 'off') else dv
                    else:
                        try:
                            cur[k][f] = max(0, float(x))
                        except (TypeError, ValueError):
                            pass
    if isinstance(b.get('mute'), str) and b['mute'].strip():
        cur['muted'] = sorted(set(cur['muted']) | {b['mute'].strip()})
    if isinstance(b.get('unmute'), str):
        cur['muted'] = [m for m in cur['muted'] if m != b['unmute']]
    config.save_settings({'alerts': cur})
    return cur


def wanted(kind):
    """Is this kind of alert switched on?"""
    g = KIND_GROUP.get(kind, 'updates')
    s = settings()
    if g == 'market':
        return s['market']['mode'] != 'off'
    return bool(s.get(g, {}).get('on', True))


def pair(old_div, new_div, rt):
    """'1.20 div -> 2.50 div' or '120 ex -> 260 ex': both sides in the same unit."""
    ex = (rt or {}).get('ex_per_div')
    if max(old_div, new_div) >= 1 or not ex:
        f = lambda v: f'{v:,.2f} div' if v < 100 else f'{v:,.0f} div'
    else:
        f = lambda v: f'{v * ex:,.0f} ex' if v * ex >= 10 else f'{v * ex:,.1f} ex'
    return f'{f(old_div)} -> {f(new_div)}'


def market_moves(con, league, rt, mine):
    """Moves over the last day that pass the noise filters. Returns (mine_moves, market_moves) lists of dicts."""
    s = settings()
    latest = con.execute('SELECT MAX(ts) FROM price WHERE league=?', (league,)).fetchone()[0]
    if not latest:
        return [], []
    day = con.execute('SELECT MAX(ts) FROM price WHERE league=? AND ts<=?', (league, latest - 20 * 3600)).fetchone()[0]
    mid = con.execute('SELECT MAX(ts) FROM price WHERE league=? AND ts<=?', (league, latest - 2 * 3600)).fetchone()[0]
    if not day:
        return [], []
    q = ('SELECT item_key, name, value, volume, listings FROM price WHERE league=? AND ts=?')
    now = {r['item_key']: r for r in con.execute(q, (league, latest))}
    then = {r['item_key']: r for r in con.execute(q, (league, day))}
    before = {r['item_key']: r for r in con.execute(q, (league, mid))} if mid and mid > day else {}
    muted = {m.lower() for m in s['muted']}
    mm, mk = [], []
    for k, n in now.items():
        o = then.get(k)
        if not o or not o['value'] or not n['value']:
            continue
        name = n['name']
        base = name.split(' (')[0].split(' [')[0]
        if base.lower() in muted:
            continue
        pct = (n['value'] / o['value'] - 1) * 100
        b = before.get(k)
        held = b is None or not b['value'] or ((b['value'] / o['value'] - 1) * 100) * pct > 0 and \
            abs((b['value'] / o['value'] - 1) * 100) >= abs(pct) * 0.5   # 2 h ago it had already moved most of the way
        trades = (n['volume'] or 0) >= s['market']['min_volume'] or (n['listings'] or 0) >= s['market']['min_listings']
        row = {'name': name, 'pct': pct, 'old': o['value'], 'new': n['value'], 'held': held,
               'volume': n['volume'], 'listings': n['listings'], 'text': pair(o['value'], n['value'], rt)}
        if base.lower() in mine:
            if abs(pct) >= s['mine']['pct'] and held:
                mm.append(row)
        elif held and trades and max(o['value'], n['value']) >= s['market']['min_div'] and abs(pct) >= s['market']['pct']:
            mk.append(row)
    mk.sort(key=lambda r: -abs(r['pct']))
    return mm, mk


def why(r):
    bits = ['held for 2+ hours' if r['held'] else '']
    if r.get('volume'):
        bits.append(f"{r['volume']:,.0f} traded")
    elif r.get('listings'):
        bits.append(f"{r['listings']} listed")
    return ', '.join(b for b in bits if b)


def run(con, alert, league, rt, mine):
    """The price part of the monitor's alert job."""
    s = settings()
    mm, mk = market_moves(con, league, rt, mine)
    if s['mine']['on']:
        for r in mm:
            alert(con, 'price-mine', f"{r['name']} {'up' if r['pct'] > 0 else 'down'} {abs(r['pct']):.0f}% in a day",
                  f"{r['text']} · in your builds / watch list · {why(r)}")
    mode = s['market']['mode']
    if mode == 'each':
        for r in mk[:int(s['market']['max_each'])]:
            alert(con, 'price-market', f"{r['name']} {'up' if r['pct'] > 0 else 'down'} {abs(r['pct']):.0f}% in a day",
                  f"{r['text']} · {why(r)}")
    elif mode == 'digest' and mk:
        today = time.strftime('%Y-%m-%d')
        if db.kv_get(con, 'alerts:digest_day') != today and time.localtime().tm_hour >= 9:
            db.kv_set(con, 'alerts:digest_day', today)
            lines = [f"{r['name']} {'+' if r['pct'] > 0 else ''}{r['pct']:.0f}% ({r['text']})" for r in mk[:10]]
            alert(con, 'digest', f"Today's market: {len(mk)} real move{'s' if len(mk) != 1 else ''}",
                  '\n'.join(lines) + ('\n…and more on the Economy page' if len(mk) > 10 else ''))


def oracle_run(con, alert):
    """The Oracle's calls: a countdown under a day, and a new daily omen."""
    if not settings()['oracle']['on']:
        return
    try:
        from . import prophecy
        for c in prophecy.countdowns(con):
            if 0 < c['in_hours'] <= 24:
                alert(con, 'oracle', f"In {c['in_hours']:.0f} h: {c['label']}", 'From the Oracle (Prophecy page).')
        o = prophecy.omen(con)
        key = (o.get('title') or '')[:120]
        if key and db.kv_get(con, 'alerts:omen') != key:
            db.kv_set(con, 'alerts:omen', key)
            alert(con, 'oracle', f"New omen: {o['title']}", ' '.join(x for x in (o.get('text'), o.get('evidence')) if x)[:400])
    except Exception:
        pass
