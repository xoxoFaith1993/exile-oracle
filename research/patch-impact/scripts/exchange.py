"""GGG's documented public Currency Exchange history (same endpoint and pricing method as poe2kit/ggg_exchange.py and
poe2kit/leaguestart.py): https://web.poecdn.com/api/currency-exchange/poe2/<unix hour>, no login.

- hour pages are cached gzipped in cache/exchange/<hour>.json.gz, Hardcore / SSF / private-league markets dropped;
- if the app DB (<data folder>/data/poe2kit.db, opened read-only) already has ex_price rows for an hour, those are
  used and nothing is fetched;
- 2.5 s between requests.

prices(hour) -> {'league': main league, 'div_ex': Ex per Div, 'items': {metadata_id: (price_div, units)}}"""
import gzip
import json
import os
import sqlite3
import statistics
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'cache', 'exchange')
PCACHE = os.path.join(HERE, 'cache', 'prices')
BASE = 'https://web.poecdn.com/api/currency-exchange/poe2'
UA = {'User-Agent': 'poe2-personal-toolkit/0.3 (patch-impact research)'}
DB = 'file:<data folder>/data/poe2kit.db?mode=ro'
EX = 'Metadata/Items/Currency/CurrencyAddModToRare'
DIV = 'Metadata/Items/Currency/CurrencyModValues'
CHAOS = 'Metadata/Items/Currency/CurrencyRerollRare'
PAUSE = 2.5
_last = [0.0]


def _skip_league(lg):
    l = lg.lower()
    return ('hardcore' in l or l.startswith('hc ') or ' hc' in l or 'ssf' in l or 'solo self' in l
            or '(pl' in l or 'ruthless' in l)


def page(hour):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, f'{hour}.json.gz')
    if os.path.exists(p):
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            return json.load(f)
    wait = PAUSE - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    body = urllib.request.urlopen(urllib.request.Request(f'{BASE}/{hour}', headers=UA), timeout=90).read()
    _last[0] = time.time()
    d = json.loads(body)
    d['markets'] = [m for m in d.get('markets', []) if not _skip_league(m.get('league', ''))]
    with gzip.open(p, 'wt', encoding='utf-8') as f:
        json.dump(d, f, separators=(',', ':'))
    return d


def main_league(markets):
    cnt = {}
    for m in markets:
        cnt[m.get('league', '')] = cnt.get(m.get('league', ''), 0) + 1
    challenge = {k: v for k, v in cnt.items() if k != 'Standard' and v >= 40}
    if challenge:
        return max(challenge, key=challenge.get)
    return 'Standard'


def prices_from_page(d, league):
    """leaguestart.prices_from_page, returning Divine prices."""
    pair = {}
    for m in d.get('markets', []):
        if m.get('league') != league:
            continue
        a, b = m['market_id'].split('|')
        lo, hi, vol = m.get('lowest_ratio') or {}, m.get('highest_ratio') or {}, m.get('volume_traded') or {}
        if vol.get(a) and vol.get(b):
            b_per_a = vol[b] / vol[a]
        else:
            rates = [r[b] / r[a] for r in (lo, hi) if r.get(a) and r.get(b)]
            if not rates:
                continue
            b_per_a = statistics.median(rates)
        pair[(a, b)] = (b_per_a, vol.get(a) or 0)
        pair[(b, a)] = (1 / b_per_a, vol.get(b) or 0)
    ex_per = {EX: 1.0}
    for base in (DIV, CHAOS):
        if (base, EX) in pair:
            ex_per[base] = pair[(base, EX)][0]
    div_ex = ex_per.get(DIV)
    if not div_ex:
        return None, {}
    out = {}
    for it in {a for a, _ in pair}:
        units = sum(u for (x, _), (_, u) in pair.items() if x == it)
        for base in (DIV, EX, CHAOS):   # prefer the Divine market for Divine pricing
            if it != base and (it, base) in pair and base in ex_per:
                rate, _ = pair[(it, base)]
                out[it] = (rate * ex_per[base] / div_ex, units)
                break
    out[EX] = (1 / div_ex, sum(u for (x, _), (_, u) in pair.items() if x == EX))
    out[DIV] = (1.0, sum(u for (x, _), (_, u) in pair.items() if x == DIV))
    return div_ex, out


def _from_db(hour):
    try:
        con = sqlite3.connect(DB, uri=True)
        rows = con.execute('SELECT league, item, price_div, units FROM ex_price WHERE hour=?', (hour,)).fetchall()
        con.close()
    except Exception:
        return None
    if not rows:
        return None
    by = {}
    for lg, it, pd, u in rows:
        if pd and not _skip_league(lg) and lg != 'Standard':
            by.setdefault(lg, {})[it] = (pd, u or 0)
    if not by:
        return None
    lg = max(by, key=lambda k: len(by[k]))
    items = by[lg]
    ex = items.get(EX)
    return {'league': lg, 'div_ex': (1 / ex[0]) if ex else None, 'items': items, 'source': 'app DB ex_price'}


def prices(hour):
    hour = int(hour) // 3600 * 3600
    os.makedirs(PCACHE, exist_ok=True)
    p = os.path.join(PCACHE, f'{hour}.json')
    if os.path.exists(p):
        d = json.load(open(p, encoding='utf-8'))
        d['items'] = {k: tuple(v) for k, v in d['items'].items()}
        return d
    d = _from_db(hour)
    if d is None:
        pg = page(hour)
        lg = main_league(pg.get('markets', []))
        div_ex, items = prices_from_page(pg, lg)
        d = {'league': lg, 'div_ex': div_ex, 'items': items, 'source': 'GGG exchange history'}
    json.dump(d, open(p, 'w', encoding='utf-8'), separators=(',', ':'))
    return d


if __name__ == '__main__':
    import sys
    for h in sys.argv[1:]:
        d = prices(int(h))
        print(h, d['league'], d['div_ex'], len(d['items']), d['source'])


def prices_league(hour, league):
    """Like prices(), but for a named league (used for the cross-league phase control)."""
    hour = int(hour) // 3600 * 3600
    d = os.path.join(HERE, 'cache', 'prices_lg')
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"{league.replace(' ', '_')}_{hour}.json")
    if os.path.exists(p):
        x = json.load(open(p, encoding='utf-8'))
        x['items'] = {k: tuple(v) for k, v in x['items'].items()}
        return x
    out = None
    try:
        con = sqlite3.connect(DB, uri=True)
        rows = con.execute('SELECT item, price_div, units FROM ex_price WHERE hour=? AND league=?', (hour, league)).fetchall()
        con.close()
        if rows:
            items = {it: (pd, u or 0) for it, pd, u in rows if pd}
            ex = items.get(EX)
            out = {'league': league, 'div_ex': (1 / ex[0]) if ex else None, 'items': items, 'source': 'app DB ex_price'}
    except Exception:
        pass
    if out is None:
        pg = page(hour)
        div_ex, items = prices_from_page(pg, league)
        out = {'league': league, 'div_ex': div_ex, 'items': items, 'source': 'GGG exchange history'}
    json.dump(out, open(p, 'w', encoding='utf-8'), separators=(',', ':'))
    return out
