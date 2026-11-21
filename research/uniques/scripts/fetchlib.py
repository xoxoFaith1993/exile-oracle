"""Polite, cached HTTP GET for the unique-history research (public pages only).
Every response is stored under ../cache/<host>/<sha1>.bin plus an index.jsonl line, so reruns never re-hit a site.
Spacing: at least SPACING seconds between live requests (default 2.5 s)."""
import gzip, hashlib, json, os, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(os.path.dirname(HERE), 'cache')
UA = 'exile-oracle-research/1.0 (personal PoE2 price-history study; polite, cached)'
SPACING = 2.5
_last = [0.0]


def _path(url):
    host = url.split('/')[2]
    h = hashlib.sha1(url.encode()).hexdigest()
    d = os.path.join(CACHE, host.replace(':', '_'))
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, h + '.bin')


def get(url, refresh=False, spacing=SPACING, timeout=60, retries=2):
    """Returns (status, bytes). Cached forever (also caches 404s as status 404)."""
    p = _path(url)
    meta = p + '.meta'
    if not refresh and os.path.exists(meta):
        m = json.load(open(meta))
        body = open(p, 'rb').read() if os.path.exists(p) else b''
        return m['status'], body
    for attempt in range(retries + 1):
        wait = spacing - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Encoding': 'gzip'})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
                if r.headers.get('Content-Encoding') == 'gzip':
                    body = gzip.decompress(body)
                status = r.status
                hdrs = dict(r.headers)
        except urllib.error.HTTPError as e:
            status, body = e.code, b''
            hdrs = dict(e.headers or {})
            if status in (429, 503) and attempt < retries:
                ra = e.headers.get('Retry-After')
                time.sleep(min(120, int(ra) if ra and ra.isdigit() else 30))
                continue
        except Exception as e:
            if attempt < retries:
                time.sleep(10)
                continue
            return -1, str(e).encode()
        break
    if status in (200, 404, 410):
        open(p, 'wb').write(body)
        json.dump({'url': url, 'status': status, 'headers': hdrs, 'fetched': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, open(meta, 'w'))
        with open(os.path.join(CACHE, 'index.jsonl'), 'a', encoding='utf-8') as f:
            f.write(json.dumps({'url': url, 'status': status, 'file': os.path.relpath(p, CACHE)}) + '\n')
    return status, body


def get_json(url, **kw):
    s, b = get(url, **kw)
    if s != 200:
        return s, None
    try:
        return s, json.loads(b)
    except Exception:
        return s, None


def headers(url):
    m = _path(url) + '.meta'
    import os as _o
    return json.load(open(m)).get('headers', {}) if _o.path.exists(m) else {}
