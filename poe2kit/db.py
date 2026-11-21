"""SQLite database: one file holds price history, exchange digests, builds and alerts."""

import os
import sqlite3
import time

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS http_cache (
    url TEXT PRIMARY KEY,
    etag TEXT,
    last_modified TEXT,
    fetched_at REAL,
    body BLOB
);

-- One row per item per poll: poe.ninja prices (exchange + unique overviews).
CREATE TABLE IF NOT EXISTS price (
    ts REAL NOT NULL,
    league TEXT NOT NULL,
    source TEXT NOT NULL,          -- 'ninja-exchange' or 'ninja-item'
    category TEXT NOT NULL,        -- poe.ninja type, e.g. Currency, UniqueArmours
    item_key TEXT NOT NULL,        -- stable id from the source
    name TEXT NOT NULL,
    value REAL,                    -- in the league's primary currency (see unit)
    unit TEXT,                     -- e.g. 'exalted' / 'divine'
    volume REAL,                   -- traded volume (exchange) when known
    listings INTEGER               -- listing count (items) when known
);
CREATE INDEX IF NOT EXISTS price_item ON price(league, item_key, ts);
CREATE INDEX IF NOT EXISTS price_ts ON price(ts);

-- GGG's official hourly Currency Exchange digests (public API).
CREATE TABLE IF NOT EXISTS exchange_hour (
    hour INTEGER NOT NULL,         -- unix time truncated to the hour
    league TEXT NOT NULL,
    market_id TEXT NOT NULL,
    volume_json TEXT, lowest_stock_json TEXT, highest_stock_json TEXT,
    lowest_ratio_json TEXT, highest_ratio_json TEXT,
    PRIMARY KEY (hour, league, market_id)
);

CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
-- one price per day per unique (the price table keeps only recent snapshots): the league's unique price history,
-- from day 0, for the Oracle (chase uniques like Mageblood and Temporalis move very differently through a league)
CREATE TABLE IF NOT EXISTS unique_daily (
    day TEXT NOT NULL, league TEXT NOT NULL, name TEXT NOT NULL, base TEXT,
    value_div REAL, listings INTEGER, PRIMARY KEY (day, league, name));

-- Build Vault: every build snapshot, kept forever.
CREATE TABLE IF NOT EXISTS build (
    id INTEGER PRIMARY KEY,
    added REAL NOT NULL,
    label TEXT NOT NULL,           -- e.g. character name or guide name
    owner TEXT,                    -- 'me' or a player/guide source
    league TEXT,
    class TEXT, ascendancy TEXT, level INTEGER,
    main_skill TEXT,
    stats_json TEXT,               -- PlayerStat values PoB saved
    pob_code TEXT NOT NULL,
    source_url TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS alert (
    id INTEGER PRIMARY KEY,
    ts REAL NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT,
    seen INTEGER DEFAULT 0
);
"""


DAMAGED = ('file is not a database', 'malformed', 'disk image', 'file is encrypted')


def connect():
    """Open the database. A damaged file is moved aside (never deleted), a fresh one is started and the player's own
    data comes back from the newest daily backup (fail-safe, the author 2026-11-21)."""
    try:
        return _connect()
    except sqlite3.DatabaseError as e:
        if not any(d in str(e).lower() for d in DAMAGED):
            raise
        return _recover(e)


def _connect():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    con = sqlite3.connect(config.DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    try:
        con.execute('PRAGMA journal_mode=WAL')
        con.executescript(SCHEMA)
    except sqlite3.DatabaseError:
        con.close()   # Windows: a file that's still open can't be moved aside
        raise
    cols = {r[1] for r in con.execute('PRAGMA table_info(price)')}
    if 'base' not in cols:  # uniques can share a name across bases (e.g. Runemastered vs plain)
        con.execute('ALTER TABLE price ADD COLUMN base TEXT')
        con.commit()
    if 'icon' not in cols:  # item picture URL (GGG's image CDN, via poe.ninja)
        con.execute('ALTER TABLE price ADD COLUMN icon TEXT')
        con.commit()
    return con


# ---------------- the player's own data: a small daily backup + recovery ----------------
# Prices, exchange history and caches re-download by themselves; these don't: builds (and their tuning / plans /
# Lab cards, in kv), the wishlist and wanted items, alert choices, play-session events, Top 1% benchmarks.
ESSENTIAL_TABLES = ('build', 'log_event', 'bench_char')
VOLATILE_KV = ('snap-sig', 'rates:', 'monitor_', 'offline:', 'backoff:', 'last_snapshot', 'ggg_exchange_cursor',
               'ex_price_hour', 'charlist_cache', 'install_state')
BACKUPS = os.path.join(config.HOME, 'backups')


def backup_essentials(con, keep=7):
    """Write backups/essentials-YYYY-MM-DD.json (tens of KB) and keep the last `keep`. Returns its path."""
    import json
    os.makedirs(BACKUPS, exist_ok=True)
    out = {'made': time.time(), 'version': getattr(config, 'VERSION', '?'), 'tables': {}, 'kv': {}}
    for t in ESSENTIAL_TABLES:
        try:
            cur = con.execute(f'SELECT * FROM {t}')
            cols = [d[0] for d in cur.description]
            out['tables'][t] = {'cols': cols, 'rows': [list(r) for r in cur]}
        except sqlite3.Error:
            pass
    for k, v in con.execute('SELECT k, v FROM kv'):
        if not k.startswith(VOLATILE_KV):
            out['kv'][k] = v
    path = os.path.join(BACKUPS, time.strftime('essentials-%Y-%m-%d.json'))
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(out, f, default=str)
    os.replace(tmp, path)
    for old in sorted(f for f in os.listdir(BACKUPS) if f.startswith('essentials-'))[:-keep]:
        try:
            os.remove(os.path.join(BACKUPS, old))
        except OSError:
            pass
    return path


def restore_essentials(con, path):
    import json
    d = json.load(open(path, encoding='utf-8'))
    n = 0
    for t, data in (d.get('tables') or {}).items():
        if t not in ESSENTIAL_TABLES:
            continue
        have = {r[1] for r in con.execute(f'PRAGMA table_info({t})')}
        cols = [c for c in data['cols'] if c in have]
        idx = [data['cols'].index(c) for c in cols]
        for row in data['rows']:
            con.execute(f"INSERT OR REPLACE INTO {t}({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
                        [row[i] for i in idx])
            n += 1
    for k, v in (d.get('kv') or {}).items():
        con.execute('INSERT OR REPLACE INTO kv(k, v) VALUES(?,?)', (k, v))
    con.commit()
    return n


def _recover(err):
    stamp = time.strftime('%Y%m%d-%H%M%S')
    moved = config.DB_PATH + f'.damaged-{stamp}'
    for ext in ('', '-wal', '-shm'):
        try:
            if os.path.exists(config.DB_PATH + ext):
                os.replace(config.DB_PATH + ext, moved + ext)
        except OSError:
            pass
    con = _connect()
    backups = sorted(f for f in os.listdir(BACKUPS) if f.startswith('essentials-') and f.endswith('.json')) \
        if os.path.isdir(BACKUPS) else []
    restored = None
    for f in reversed(backups):   # newest first; a damaged backup is skipped
        try:
            n = restore_essentials(con, os.path.join(BACKUPS, f))
            restored = (f, n)
            break
        except Exception:
            continue
    msg = (f'Your Exile Oracle data file was damaged ({err}). It was moved aside, not deleted: {moved}. A fresh one was '
           'started; prices and history download again by themselves. ' +
           (f'Your builds, wishlist and choices came back from the backup of {restored[0][11:21]}.' if restored else
            'There was no backup yet, so builds need importing again (Builds page, or your character).'))
    con.execute('INSERT INTO alert(ts, kind, title, detail) VALUES(?,?,?,?)', (time.time(), 'install',
                'Your data file was repaired', msg))
    kv_set(con, 'recovered', msg)
    con.commit()
    return con


def kv_get(con, k, default=None):
    r = con.execute('SELECT v FROM kv WHERE k=?', (k,)).fetchone()
    return r['v'] if r else default


def kv_set(con, k, v):
    con.execute('INSERT INTO kv(k, v) VALUES(?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v', (k, str(v)))
    con.commit()


def now():
    return time.time()
