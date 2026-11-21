"""Turn the cached GGG exchange pages + the app DB into one price table for the forecast model.

Inputs (all read-only):
  * <forecast>/cache/raw/<hour>.json.gz   full hourly pages from fetch_history.py (daily samples, all leagues)
  * <data folder>/data/poe2kit.db        exchange_hour (raw hourly markets since 2026-11-06), price (poe.ninja categories)
  * <data folder>/data/repoe/base_items.min.json   id -> name (same map as poe2kit.leaguestart._names)
Price method: poe2kit.leaguestart.prices_from_page with one fix (only markets that traded; see prices_from_page).

Output: <forecast>/cache/prices.db  (sqlite)
  obs(league, hour, item, price_ex, price_div, units, src)    every sample hour
  day(league, day, item, price_div, units, n, src)             canonical daily price (see below)
  league(league, start_hour, kind, last_hour)
  item(item, name, category)
Canonical day price = the 21:00 UTC sample of that league day (the hour the fetch samples every day); if that hour
is missing, the median of the samples that day. day = floor((hour - start_hour) / 86400).
Usage: python -I build_dataset.py <forecast_dir>"""
import gzip, json, os, sqlite3, statistics, sys

ROOT = sys.argv[1]
RAW = os.path.join(ROOT, 'cache', 'raw')
OUT = os.path.join(ROOT, 'cache', 'prices.db')
APPDB = 'file:<data folder>/data/poe2kit.db?mode=ro'
EX = 'Metadata/Items/Currency/CurrencyAddModToRare'
DIV = 'Metadata/Items/Currency/CurrencyModValues'
CHAOS = 'Metadata/Items/Currency/CurrencyRerollRare'
MIN_MARKETS = 50

# Launch hours (UTC). FotV/RoA/FR from the app's ls_league; the older three found by binary search (find_starts.py).
STARTS = json.load(open(os.path.join(ROOT, 'cache', 'league_starts.json'), encoding='utf-8'))


def prices_from_page(mk):
    """Like poe2kit.leaguestart.prices_from_page (volume-weighted pair ratio, priced against Exalted, Divine or Chaos
    and converted at that hour's rates) with one fix: an item is priced only from a market where it actually TRADED
    that hour (volume on both sides), taking the base market with the most units traded. The app's version takes the
    Exalted market first even when it had no trades, and then falls back to the lowest/highest listed ratio, which
    produced fake 100x-4000x jumps on thin items (e.g. Lesser Essence of Sorcery 0.0017 -> 1.0 div in one day).
    Returns item -> (price in Exalted, units traded in the market used), ex_per_div."""
    pair = {}
    for m in mk:
        a, b = m['market_id'].split('|')
        vol = m.get('volume_traded') or {}
        va, vb = vol.get(a) or 0, vol.get(b) or 0
        if va > 0 and vb > 0:
            pair[(a, b)] = (vb / va, va)
            pair[(b, a)] = (va / vb, vb)
    ex_per = {EX: 1.0}
    for base in (DIV, CHAOS):
        if (base, EX) in pair:
            ex_per[base] = pair[(base, EX)][0]
    out = {}
    for it in {a for a, _ in pair}:
        best = None
        for base in (EX, DIV, CHAOS):
            if it != base and (it, base) in pair and base in ex_per:
                rate, units = pair[(it, base)]
                if best is None or units > best[1]:
                    best = (rate * ex_per[base], units)
        if best:
            out[it] = best
    for base, v in ex_per.items():
        if base != EX:
            out[base] = (v, pair[(base, EX)][1])
    return out, ex_per.get(DIV)


def league_kind(lg):
    if '(PL' in lg:
        return 'private'
    if lg == 'Standard':
        return 'standard'
    if lg == 'Hardcore':
        return 'hardcore-standard'
    if lg.startswith('HC '):
        return 'hc-challenge'
    return 'challenge'


def category_of(item_id, name, ninja_cat):
    if name in ninja_cat:
        return ninja_cat[name]
    n, p = (name or '').lower(), item_id.lower()
    rules = [('omen', 'Ritual'), ('essence', 'Essences'), ('soul core', 'SoulCores'), ('rune', 'Runes'),
             ('uncut', 'UncutGems'), ('catalyst', 'Breach'), ('splinter', 'Fragments'), ('liquid', 'Delirium'),
             ('distilled', 'Delirium'), ('simulacrum', 'Delirium'), ('idol', 'Idols'), ('expedition', 'Expedition'),
             ('artifact', 'Expedition'), ('logbook', 'Expedition'), ('preserved', 'Abyss'), ('ancient', 'Abyss'),
             ('talisman', 'Other'), ('breach', 'Breach'), ('fate', 'Ritual')]
    for k, c in rules:
        if k in n:
            return c
    if '/gems/' in p:
        return 'LineageSupportGems' if 'support' in p else 'UncutGems'
    if '/currency/' in p:
        return 'Currency'
    return 'Other'


def main():
    app = sqlite3.connect(APPDB, uri=True)
    names = {k: v.get('name') for k, v in json.load(
        open('<data folder>/data/repoe/base_items.min.json', encoding='utf-8')).items() if v.get('name')}
    ninja_cat = {}
    for n, c in app.execute("SELECT name, category FROM price WHERE source='ninja-exchange' GROUP BY name, category"):
        ninja_cat.setdefault(n, c)
    if os.path.exists(OUT):
        os.remove(OUT)
    db = sqlite3.connect(OUT)
    db.executescript('''
      CREATE TABLE obs (league TEXT, hour INTEGER, item TEXT, price_ex REAL, price_div REAL, units REAL, src TEXT,
                        PRIMARY KEY (league, hour, item));
      CREATE TABLE day (league TEXT, day INTEGER, item TEXT, price_div REAL, units REAL, n INTEGER, src TEXT,
                        PRIMARY KEY (league, day, item));
      CREATE TABLE league (league TEXT PRIMARY KEY, start_hour INTEGER, kind TEXT, last_hour INTEGER);
      CREATE TABLE item (item TEXT PRIMARY KEY, name TEXT, category TEXT);''')
    # 1. fetched pages
    files = sorted(f for f in os.listdir(RAW) if f.endswith('.json.gz'))
    first_seen = {}
    for i, f in enumerate(files):
        h = int(f.split('.')[0])
        with gzip.open(os.path.join(RAW, f), 'rt', encoding='utf-8') as fh:
            d = json.load(fh)
        by = {}
        for m in d.get('markets', []):
            by.setdefault(m.get('league', ''), []).append(m)
        rows = []
        for lg, mk in by.items():
            if len(mk) < MIN_MARKETS:
                continue
            first_seen.setdefault(lg, h)
            pr, dx = prices_from_page(mk)
            if not dx:
                continue
            for it, (p, u) in pr.items():
                rows.append((lg, h, it, p, p / dx, u, 'fetch'))
        db.executemany('INSERT OR REPLACE INTO obs VALUES (?,?,?,?,?,?,?)', rows)
        if i % 100 == 0:
            print('pages', i, len(files), flush=True)
    # 2. app DB exchange_hour (raw hourly markets since 2026-11-06), priced with the same fixed method. (ls_price is
    #    not used: it holds app-method prices, and the 21:00 sample of launch days 0-21 is fetched anyway.)
    hours = [r[0] for r in app.execute('SELECT DISTINCT hour FROM exchange_hour ORDER BY hour')]
    for h in hours:
        by = {}
        for lg, mid, vj in app.execute('SELECT league, market_id, volume_json FROM exchange_hour WHERE hour=?', (h,)):
            if '(PL' in lg:
                continue
            by.setdefault(lg, []).append({'market_id': mid, 'volume_traded': json.loads(vj or 'null')})
        rows = []
        for lg, mk in by.items():
            if len(mk) < MIN_MARKETS:
                continue
            pr, dx = prices_from_page(mk)
            if dx:
                rows += [(lg, h, it, p, p / dx, u, 'app_hour') for it, (p, u) in pr.items()]
        db.executemany('INSERT OR IGNORE INTO obs VALUES (?,?,?,?,?,?,?)', rows)
    db.commit()
    # 3. leagues and start hours
    for lg, last in db.execute('SELECT league, MAX(hour) FROM obs GROUP BY league').fetchall():
        st = STARTS.get(lg) or first_seen.get(lg)
        db.execute('INSERT INTO league VALUES (?,?,?,?)', (lg, st, league_kind(lg), last))
    # 4. canonical day prices
    leagues = dict(db.execute('SELECT league, start_hour FROM league'))
    for lg, st in leagues.items():
        if st is None:
            continue
        acc = {}
        for h, it, p, u, src in db.execute('SELECT hour, item, price_div, units, src FROM obs WHERE league=? AND hour>=?',
                                           (lg, st)):
            dd = (h - st) // 86400
            acc.setdefault((dd, it), []).append((h % 86400 == 75600, p, u, src))
        rows = []
        for (dd, it), xs in acc.items():
            main = [x for x in xs if x[0]]
            use = main or xs
            p = statistics.median(x[1] for x in use)
            u = statistics.median(x[2] or 0 for x in use)
            rows.append((lg, dd, it, p, u, len(use), use[0][3]))
        db.executemany('INSERT INTO day VALUES (?,?,?,?,?,?,?)', rows)
    items = [r[0] for r in db.execute('SELECT DISTINCT item FROM obs')]
    db.executemany('INSERT INTO item VALUES (?,?,?)',
                   [(it, names.get(it, it.split('/')[-1]), category_of(it, names.get(it, ''), ninja_cat)) for it in items])
    db.commit()
    for r in db.execute('SELECT l.league, l.kind, l.start_hour, COUNT(DISTINCT d.day), COUNT(DISTINCT d.item) '
                        'FROM league l LEFT JOIN day d USING(league) GROUP BY l.league ORDER BY l.start_hour'):
        print(r)


if __name__ == '__main__':
    main()
