"""Step 3b: unique items. poe.ninja's public ECONOMY API only (never builds / character / profile endpoints):
  /poe2/api/economy/stash/current/item/overview?league=L&type=T  (current listing prices, ids)
  /poe2/api/economy/stash/current/item/history?league=L&type=T&id=N  (daily values, 'daysAgo', priced in Divine)
History exists only for leagues poe.ninja still lists (2026-11-21: Runes of Aldur, Forbidden Rites).
3 s between requests, everything cached in cache/ninja/.

For every patch line in those leagues that names a unique (rules.uniques_named) or classifies as a unique change,
measure the unique's Divine value 1 day before the post vs +1 / +3 / +7 days, against the median of a fixed
random control basket of 40 uniques from the same league (same days).
Usage: python -I ninja_uniques.py   -> cache/ninja_measured.json"""
import datetime as dt
import json
import os
import random
import statistics
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import rules  # noqa: E402

C = os.path.join(HERE, 'cache')
N = os.path.join(C, 'ninja')
BASE = 'https://poe.ninja/poe2/api/economy/stash/current/item'
UA = {'User-Agent': 'poe2-personal-toolkit/0.3 (economy research)'}
TYPES = ['UniqueWeapons', 'UniqueArmours', 'UniqueAccessories', 'UniqueFlasks', 'UniqueCharms', 'UniqueJewels',
         'UniqueSanctumRelics', 'UniqueTablets']
LEAGUES = {'Runes of Aldur': (1780095600, 1788562800), 'Forbidden Rites': (1788562800, 1797000000)}
_last = [0.0]


def get(url, path):
    if os.path.exists(path):
        return json.load(open(path, encoding='utf-8'))
    w = 3 - (time.time() - _last[0])
    if w > 0:
        time.sleep(w)
    body = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
    _last[0] = time.time()
    d = json.loads(body)
    json.dump(d, open(path, 'w', encoding='utf-8'))
    return d


def overview(league, t):
    q = urllib.parse.urlencode({'league': league, 'type': t})
    return get(f'{BASE}/overview?{q}', os.path.join(N, f'ov_{league.replace(" ", "_")}_{t}.json'))


def history(league, t, iid):
    q = urllib.parse.urlencode({'league': league, 'type': t, 'id': iid})
    return get(f'{BASE}/history?{q}', os.path.join(N, f'h_{league.replace(" ", "_")}_{t}_{iid}.json'))


def fetched_day():
    """poe.ninja 'daysAgo' is relative to when we fetched (the cache files' date)."""
    p = os.path.join(N, 'fetched_utc.txt')
    if not os.path.exists(p):
        open(p, 'w').write(dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d'))
    return dt.datetime.strptime(open(p).read().strip(), '%Y-%m-%d').date()


def series(h, today):
    """history -> {date: value} (uncorrupted, cheapest-roll listing value as poe.ninja reports it)."""
    return {today - dt.timedelta(days=x['daysAgo']): x['value'] for x in h if x.get('value')}


def at(s, d, tol=1):
    for k in [0] + [j for i in range(1, tol + 1) for j in (-i, i)]:
        v = s.get(d + dt.timedelta(days=k))
        if v:
            return v
    return None


def main():
    os.makedirs(N, exist_ok=True)
    today = fetched_day()
    import measure
    events = []
    for p in json.load(open(os.path.join(C, 'forum', 'patches_raw.json'), encoding='utf-8')):
        events.append({'title': p['title'], 'date_utc': p['date_utc'], 'h0': measure.hour_of(p['date_utc']) - 3600,
                       'content_update': measure.is_content_update(p['title']), 'lines': p['lines']})
    out = []
    for lg, (a, b) in LEAGUES.items():
        idx = {}
        for t in TYPES:
            try:
                ov = overview(lg, t)
            except Exception as e:
                print('overview ERR', lg, t, e)
                continue
            for l in ov.get('lines', []):
                # one id per unique name: the most-listed variant
                k = l['name']
                if k not in idx or (l.get('listingCount') or 0) > idx[k][2]:
                    idx[k] = (t, l['id'], l.get('listingCount') or 0, l.get('primaryValue'))
        rnd = random.Random(11)
        liquid = sorted(k for k, v in idx.items() if v[2] >= 20 and (v[3] or 0) >= 0.05)
        control = rnd.sample(liquid, min(40, len(liquid)))
        ctrl_series = {}
        for k in control:
            t, iid, _, _ = idx[k]
            try:
                ctrl_series[k] = series(history(lg, t, iid), today)
            except Exception as e:
                print('hist ERR', k, e)
        for ev in events:
            h0 = ev['h0']
            if not (a <= h0 < b) or ev['content_update']:
                continue
            d0 = dt.datetime.fromtimestamp(h0, dt.timezone.utc).date()
            for l in ev['lines']:
                names = rules.uniques_named(l['text'])
                if not names:
                    continue
                direction = rules.direction_of(l['text'])
                for u in names[:4]:
                    if u not in idx:
                        continue
                    t, iid, cnt, _ = idx[u]
                    try:
                        s = series(history(lg, t, iid), today)
                    except Exception as e:
                        print('hist ERR', u, e)
                        continue
                    base = at(s, d0 - dt.timedelta(days=1))
                    if not base:
                        continue
                    row = {'post': ev['title'], 'date_utc': ev['date_utc'], 'league': lg, 'unique': u,
                           'line': l['text'], 'direction': direction, 'base_div': base, 'listings_now': cnt}
                    for w, dd in (('d1', 1), ('d3', 3), ('d7', 7)):
                        v = at(s, d0 + dt.timedelta(days=dd))
                        if not v:
                            continue
                        cs = []
                        for k, cser in ctrl_series.items():
                            c0, c1 = at(cser, d0 - dt.timedelta(days=1)), at(cser, d0 + dt.timedelta(days=dd))
                            if c0 and c1:
                                cs.append(c1 / c0 - 1)
                        drift = statistics.median(cs) if len(cs) >= 8 else 0.0
                        row[w] = {'raw': round((v / base - 1) * 100, 1), 'drift': round(drift * 100, 1),
                                  'abnormal': round(((v / base) / (1 + drift) - 1) * 100, 1), 'n_control': len(cs)}
                    out.append(row)
    json.dump(out, open(os.path.join(C, 'ninja_measured.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print(len(out), 'unique cases')


if __name__ == '__main__':
    main()
