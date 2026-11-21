"""Polite HTTP: descriptive User-Agent, ETag/Last-Modified caching, minimum poll interval,
GGG rate-limit headers and Retry-After respected. Only documented public endpoints go through here."""

import gzip
import json
import time
import urllib.error
import urllib.request

from . import config, db

ALLOWED_HOSTS = ('poe.ninja', 'web.poecdn.com', 'www.pathofexile.com')


class NetError(Exception):
    pass


def get_json(url, con=None, min_age_minutes=None, timeout=30):
    """Return parsed JSON for url. Serves the cached copy if it's younger than min_age_minutes,
    otherwise does a conditional request (304 -> cached copy)."""
    host = url.split('/')[2]
    if host not in ALLOWED_HOSTS:
        raise NetError(f'{host} is not an allowed source')
    own = con is None
    con = con or db.connect()
    try:
        if min_age_minutes is None:
            min_age_minutes = config.settings()['poll_minutes']
        row = con.execute('SELECT * FROM http_cache WHERE url=?', (url,)).fetchone()
        if row and row['body'] is not None and time.time() - row['fetched_at'] < min_age_minutes * 60:
            return json.loads(row['body'])

        req = urllib.request.Request(url, headers={
            'User-Agent': config.user_agent(),
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip',
        })
        if row:
            if row['etag']:
                req.add_header('If-None-Match', row['etag'])
            if row['last_modified']:
                req.add_header('If-Modified-Since', row['last_modified'])
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
                if r.headers.get('Content-Encoding') == 'gzip':
                    body = gzip.decompress(body)
                etag, lm = r.headers.get('ETag'), r.headers.get('Last-Modified')
        except urllib.error.HTTPError as e:
            if e.code == 304 and row:
                con.execute('UPDATE http_cache SET fetched_at=? WHERE url=?', (time.time(), url))
                con.commit()
                return json.loads(row['body'])
            if e.code == 429:
                wait = e.headers.get('Retry-After', '?')
                db.kv_set(con, f'backoff:{host}', time.time() + float(wait if wait != '?' else 60))
                raise NetError(f'rate limited by {host}; retry after {wait}s') from None
            raise NetError(f'{url} -> HTTP {e.code}') from None
        except urllib.error.URLError as e:
            raise NetError(f'{url} -> {e.reason}') from None

        con.execute('INSERT INTO http_cache(url, etag, last_modified, fetched_at, body) VALUES(?,?,?,?,?) '
                    'ON CONFLICT(url) DO UPDATE SET etag=excluded.etag, last_modified=excluded.last_modified, '
                    'fetched_at=excluded.fetched_at, body=excluded.body',
                    (url, etag, lm, time.time(), body))
        con.commit()
        return json.loads(body)
    finally:
        if own:
            con.close()


def backed_off(con, host):
    until = db.kv_get(con, f'backoff:{host}')
    return until is not None and float(until) > time.time()
