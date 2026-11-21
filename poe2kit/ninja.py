"""poe.ninja economy API (the public, allowed part only: economy overviews).
Docs: https://poe.ninja/docs/api. Builds/profiles endpoints are closed to third parties; never call them."""

import hashlib
import json
import time
import urllib.parse

from . import config, db, net

BASE = 'https://poe.ninja/poe2/api/economy'

EXCHANGE_TYPES = ['Currency', 'Fragments', 'Abyss', 'UncutGems', 'LineageSupportGems', 'Essences',
                  'SoulCores', 'Idols', 'Runes', 'Ritual', 'Expedition', 'Delirium', 'Breach', 'Verisium']
ITEM_TYPES = ['UniqueWeapons', 'UniqueArmours', 'UniqueAccessories', 'UniqueFlasks', 'UniqueCharms',
              'UniqueJewels', 'UniqueSanctumRelics', 'UniqueTablets', 'PrecursorTablets']


def leagues(con=None, fresh=False):
    """poe.ninja's PoE 2 leagues, newest first. Re-read every 6 hours, or every hour around a game update / 1.0
    (fresh=True from patch mode), so a new league is followed soon after it opens."""
    return net.get_json(f'{BASE}/leagues', con, min_age_minutes=0 if fresh else 360)


def current_league(con=None):
    chosen = config.settings().get('league')
    if chosen:
        return chosen
    try:
        ls = leagues(con)
    except net.NetError:   # offline on a fresh install: the newest league we have prices for, else Standard
        ls = []
        own = con is None
        c = con or db.connect()
        try:
            r = c.execute('SELECT league FROM price ORDER BY ts DESC LIMIT 1').fetchone()
            if r:
                return r[0]
        except Exception:
            pass
        finally:
            if own:
                c.close()
    return ls[0]['id'] if ls else 'Standard'


def _url(kind, league, type_):
    q = urllib.parse.urlencode({'league': league, 'type': type_})
    path = 'exchange/current/overview' if kind == 'exchange' else 'stash/current/item/overview'
    return f'{BASE}/{path}?{q}'


def exchange(league, type_, con=None):
    return net.get_json(_url('exchange', league, type_), con)


def items(league, type_, con=None):
    return net.get_json(_url('item', league, type_), con)


def snapshot(con, league=None, types=None):
    """Fetch every category (cached/conditional) and store one price row per item.
    Returns {category: rows_stored}. Skips categories whose data hasn't changed since last snapshot."""
    league = league or current_league(con)
    ts = db.now()
    out = {}
    for t in (types or EXCHANGE_TYPES + ITEM_TYPES):
        is_ex = t in EXCHANGE_TYPES
        try:
            d = exchange(league, t, con) if is_ex else items(league, t, con)
        except net.NetError as e:
            out[t] = f'error: {e}'
            continue
        sig = hashlib.sha1(json.dumps(d.get('lines', []), sort_keys=True).encode()).hexdigest()
        key = f'snap-sig:{league}:{t}'
        if db.kv_get(con, key) == sig:
            out[t] = 'unchanged'
            continue
        rows = []
        if is_ex:
            core = d.get('core', {})
            unit = core.get('primary', '')
            if core.get('rates'):
                db.kv_set(con, f'rates:{league}', json.dumps({'primary': unit, **core['rates']}))
            names = {i['id']: i['name'] for i in d.get('items', []) + core.get('items', [])}
            icons = {i['id']: ('https://web.poecdn.com' + i['image']) if (i.get('image') or '').startswith('/') else i.get('image')
                     for i in d.get('items', []) + core.get('items', [])}
            for ln in d.get('lines', []):
                rows.append((ts, league, 'ninja-exchange', t, ln['id'], names.get(ln['id'], ln['id']),
                             ln.get('primaryValue'), unit, ln.get('volumePrimaryValue'), None, None, icons.get(ln['id'])))
        else:
            unit = (d.get('core') or {}).get('primary', 'divine')
            for ln in d.get('lines', []):
                key_id = str(ln.get('detailsId') or ln.get('itemId') or ln.get('id'))
                name = ln.get('name', '?')
                if ln.get('variant'):
                    name += f' ({ln["variant"]})'
                if ln.get('corrupted'):
                    key_id += ':corrupted'
                    name += ' [corrupted]'
                rows.append((ts, league, 'ninja-item', t, key_id, name, ln.get('primaryValue'), unit,
                             None, ln.get('listingCount'), ln.get('baseType'), ln.get('icon')))
        con.executemany('INSERT INTO price(ts, league, source, category, item_key, name, value, unit, volume, '
                        'listings, base, icon) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', rows)
        db.kv_set(con, key, sig)
        out[t] = len(rows)
    con.commit()
    db.kv_set(con, 'last_snapshot', ts)
    return out


def latest(con, query, league=None, limit=15):
    """Search the newest stored price for items whose name contains query."""
    league = league or current_league(con)
    return con.execute(
        """SELECT p.name, p.base, p.icon, p.category, p.value, p.unit, p.volume, p.listings, p.ts FROM price p
           JOIN (SELECT item_key, MAX(ts) mts FROM price WHERE league=? AND name LIKE ? GROUP BY item_key) m
             ON p.item_key=m.item_key AND p.ts=m.mts
           WHERE p.league=? ORDER BY p.value DESC LIMIT ?""",
        (league, f'%{query}%', league, limit)).fetchall()


_ROLLDEP = {'t': 0, 'v': {}}


def roll_dependent(con):
    """Uniques whose poe.ninja entry lists many possible rolls (e.g. Prism of Belief: any of ~200 skills at +1..+3).
    poe.ninja gives ONE price for them, which is the cheapest/junk roll, so the toolkit flags that price as a floor."""
    import json as _json
    if time.time() - _ROLLDEP['t'] < 600:
        return _ROLLDEP['v']
    out = {}
    for r in con.execute("SELECT body FROM http_cache WHERE url LIKE '%stash/current/item/overview%'"):
        try:
            d = _json.loads(r['body'])
        except Exception:
            continue
        for ln in d.get('lines', []):
            n = sum(1 for m in (ln.get('explicitModifiers') or []) if m.get('optional'))
            if n >= 4:
                out[ln['name']] = n
    _ROLLDEP.update(t=time.time(), v=out)
    return out
