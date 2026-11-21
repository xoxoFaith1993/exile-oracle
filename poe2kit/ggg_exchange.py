"""GGG's official, public Currency Exchange history (documented 'Public API', no login).
GET https://web.poecdn.com/api/currency-exchange/poe2[/<id>] -> hourly digests, oldest first.
We walk forward from where we stopped; when next_change_id == the id we sent, we're at the live edge
and must wait for the next hour."""

import json
import time

from . import db, net

BASE = 'https://web.poecdn.com/api/currency-exchange/poe2'
# Start near the 1.0-era instead of Dec 2024, unless told otherwise (history may be pruned by GGG anyway).
DEFAULT_START = int(time.time()) // 3600 * 3600 - 14 * 24 * 3600


def sync(con, max_pages=48, start=None):
    """Fetch up to max_pages hourly digests. Returns (pages, markets_stored, at_live_edge)."""
    cursor = db.kv_get(con, 'ggg_exchange_cursor')
    cursor = int(cursor) if cursor else (start or DEFAULT_START)
    pages = stored = 0
    live = False
    while pages < max_pages:
        # Each hour is immutable once published: cache it for a long time.
        try:
            d = net.get_json(f'{BASE}/{cursor}', con, min_age_minutes=60 * 24 * 365)
        except Exception as e:
            if '404' in str(e):   # this hour isn't published yet: we're up to date, not failing
                live = True
                break
            raise
        pages += 1
        rows = []
        for m in d.get('markets', []):
            rows.append((cursor, m.get('league', ''), m['market_id'],
                         json.dumps(m.get('volume_traded')), json.dumps(m.get('lowest_stock')),
                         json.dumps(m.get('highest_stock')), json.dumps(m.get('lowest_ratio')),
                         json.dumps(m.get('highest_ratio'))))
        con.executemany('INSERT OR REPLACE INTO exchange_hour VALUES(?,?,?,?,?,?,?,?)', rows)
        stored += len(rows)
        # The rows are stored above; don't keep a second copy of the raw page in the HTTP cache.
        con.execute('DELETE FROM http_cache WHERE url=?', (f'{BASE}/{cursor}',))
        nxt = int(d.get('next_change_id', cursor))
        if nxt == cursor:
            live = True
            # The live-edge response must not be cached for a year; drop it so next hour refetches.
            con.execute('DELETE FROM http_cache WHERE url=?', (f'{BASE}/{cursor}',))
            break
        cursor = nxt
        db.kv_set(con, 'ggg_exchange_cursor', cursor)
        time.sleep(1.0)  # gentle
    con.commit()
    return pages, stored, live
