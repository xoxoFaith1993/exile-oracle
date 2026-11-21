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


def connect():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    con = sqlite3.connect(config.DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    con.executescript(SCHEMA)
    cols = {r[1] for r in con.execute('PRAGMA table_info(price)')}
    if 'base' not in cols:  # uniques can share a name across bases (e.g. Runemastered vs plain)
        con.execute('ALTER TABLE price ADD COLUMN base TEXT')
        con.commit()
    if 'icon' not in cols:  # item picture URL (GGG's image CDN, via poe.ninja)
        con.execute('ALTER TABLE price ADD COLUMN icon TEXT')
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
