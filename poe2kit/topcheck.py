"""Top 1% check: is the author's character in the top 1% of the league (by default, of his ascendancy) on
progress (level), power (DPS, effective HP) and wealth (gear value)?

Benchmarks come from poe.ninja's public builds pages, read in a browser ON REQUEST only (never on a timer,
never through poe.ninja's builds API):
- a list page gives the total number of characters ("Found 3,345 characters") and the top 100 rows for one
  sort (level / dps / ehp). Top 1% = rank ceil(total / 100); for an ascendancy under 10,000 characters that
  rank is inside the top 100, so the cutoff is exact. For the whole league it isn't (the top 100 is shown
  for context).
- a character page gives its item icons; icon file names match poe.ninja's price data, so uniques, runes and
  unique jewels are priced the same way as the author's own gear (rares are left out on both sides).
His own numbers come from headless Path of Building (pob.stats_for) and cost.slot_values."""

import json
import math
import re
import statistics
import time

from . import cost, db, money, ninja, pob

# Run in the poe.ninja list page (browser pane) to read it. Returns a small JSON blob.
LIST_JS = r"""(() => {
  const num = s => { const m = (s || '').replace(/,/g, '').trim().match(/^(-?\d+(?:\.\d+)?)\s*([kmb]?)$/i);
    return m ? +m[1] * ({k: 1e3, m: 1e6, b: 1e9}[m[2].toLowerCase()] || 1) : null; };
  const found = +((document.querySelector('main').innerText.match(/Found ([\d,]+) characters/) || [])[1] || '0').replace(/,/g, '');
  const q = new URLSearchParams(location.search), sort = q.get('sort') || 'level';
  const col = {level: 1, ehp: 4, dps: 5}[sort] || 1;
  const rows = [...document.querySelectorAll('main tbody tr')].map(r => {
    const td = [...r.querySelectorAll('td')].map(t => t.innerText.split('\n')[0].trim());
    const a = r.querySelector('a');
    return {name: td[0].slice(0, 24), v: num(td[col]), path: a ? (a.getAttribute('href').split('#')[0].split('/character/')[1] || '') : ''};
  });
  return JSON.stringify({league: location.pathname.split('/')[3], scope: q.get('class') || 'All', sort, total: found,
    vals: rows.map(r => r.v), top: rows.slice(0, 5).map(r => [r.name, r.v]),
    paths: sort === 'level' && q.get('class') ? rows.slice(0, Math.ceil(found / 100)).map(r => r.path) : []});
})()"""

# Run on a poe.ninja character page. Returns name, level and item icon file names.
CHAR_JS = r"""(() => {
  const t = document.querySelector('article').innerText;
  const lv = (t.match(/Level (\d+) ([^\n]+)/) || []);
  const icons = [...document.querySelectorAll('article img')].map(i => (i.src || '').split('/').pop()).filter(s => /\.png$/i.test(s));
  return JSON.stringify({name: decodeURIComponent(location.pathname.split('/').pop()), level: +lv[1] || null,
                         ascendancy: (lv[2] || '').trim(), league: location.pathname.split('/')[3], icons});
})()"""

METRICS = ('level', 'dps', 'ehp')
_MULT = {'k': 1e3, 'm': 1e6, 'b': 1e9}


def _num(s):
    s = (s or '').strip().replace(',', '')
    m = re.fullmatch(r'(-?\d+(?:\.\d+)?)\s*([kKmMbB]?)', s)
    if not m:
        return None
    return float(m.group(1)) * _MULT.get(m.group(2).lower(), 1)


def _seed_from_datapack(con):
    """A fresh install has no benchmarks (refreshing them needs Claude): load the ones shipped with the app."""
    if con.execute('SELECT 1 FROM bench LIMIT 1').fetchone():
        return
    from . import config
    p = config.data_file('benchmarks.json')
    if not p:
        return
    d = json.load(open(p, encoding='utf-8'))
    con.executemany('INSERT INTO bench VALUES (?,?,?,?,?,?)',
                    [(r['ts'], r['league'], r['scope'], r['metric'], r['total'], r['rows']) for r in d.get('lists', [])])
    con.executemany('INSERT OR REPLACE INTO bench_char VALUES (?,?,?,?,?,?)',
                    [(r['ts'], r['league'], r['scope'], r['name'], r['level'], r['icons']) for r in d.get('chars', [])])
    con.commit()


def _setup(con):
    con.execute('CREATE TABLE IF NOT EXISTS bench (ts REAL, league TEXT, scope TEXT, metric TEXT, total INTEGER, '
                'rows TEXT)')
    con.execute('CREATE TABLE IF NOT EXISTS bench_char (ts REAL, league TEXT, scope TEXT, name TEXT, level INTEGER, '
                'icons TEXT, PRIMARY KEY (league, scope, name))')
    _seed_from_datapack(con)


def _league_name(slug, con):
    """'forbiddenrites' -> 'Forbidden Rites' (the league names the price table uses)."""
    for (lg,) in con.execute('SELECT DISTINCT league FROM price').fetchall():
        if lg and lg.replace(' ', '').lower() == (slug or '').replace(' ', '').lower():
            return lg
    return slug


def save_list(con, blob):
    """blob = LIST_JS output (dict or JSON text): one sort of one list page."""
    d = json.loads(blob) if isinstance(blob, str) else blob
    _setup(con)
    metric = {'dps': 'dps', 'ehp': 'ehp'}.get(d.get('sort'), 'level')
    league = _league_name(d['league'], con)
    scope = (d.get('scope') or 'All').replace('+', ' ')
    data = {'vals': d['vals'], 'top': d.get('top', []), 'paths': d.get('paths', [])}
    con.execute('INSERT INTO bench VALUES (?,?,?,?,?,?)', (time.time(), league, scope, metric, int(d['total']),
                                                            json.dumps(data)))
    con.commit()
    return {'saved': f'{scope} by {metric}', 'league': league, 'total': d['total'], 'values': len(d['vals']),
            'top1_paths': len(data['paths'])}


def save_char(con, blob, scope=None):
    d = json.loads(blob) if isinstance(blob, str) else blob
    _setup(con)
    league = _league_name(d['league'], con)
    con.execute('INSERT OR REPLACE INTO bench_char VALUES (?,?,?,?,?,?)',
                (time.time(), league, scope or d.get('ascendancy') or 'All', d['name'], d.get('level'),
                 json.dumps(d['icons'])))
    con.commit()
    return {'saved': d['name'], 'gear_value': gear_value_from_icons(con, d['icons'], league)}


def _icon_prices(con, league):
    """icon file name -> (item name, value in div); icons shared by different items are dropped."""
    rows = con.execute(
        """SELECT p.name, p.icon, p.value, p.listings, p.volume FROM price p JOIN (SELECT item_key, category,
           MAX(ts) m FROM price WHERE league=? GROUP BY item_key, category) x ON p.item_key=x.item_key AND
           p.category=x.category AND p.ts=x.m WHERE p.league=? AND p.value > 0""", (league, league)).fetchall()
    icon_of, low = {}, {}
    for r in rows:
        if not ((r['listings'] or 0) >= 5 or (r['volume'] or 0) > 0):
            continue  # troll listings (e.g. a 41M-div Winter's Bite)
        name = r['name']
        low[name] = min(low.get(name, r['value']), r['value'])  # variants (Runemastered etc.): cheapest
        if r['icon']:
            icon_of.setdefault(r['icon'].split('?')[0].split('/')[-1], set()).add(name)
    return {f: (next(iter(ns)), low[next(iter(ns))]) for f, ns in icon_of.items() if len(ns) == 1}


def gear_value_from_icons(con, icons, league):
    idx = _icon_prices(con, league)
    parts = [idx[f] for f in icons if f in idx]
    return {'value_div': round(sum(v for _, v in parts), 2),
            'parts': sorted(({'item': n, 'value_div': round(v, 3)} for n, v in parts), key=lambda x: -x['value_div'])}


def _latest(con, league, scope, metric):
    r = con.execute('SELECT * FROM bench WHERE league=? AND scope=? AND metric=? ORDER BY ts DESC LIMIT 1',
                    (league, scope, metric)).fetchone()
    return dict(r, data=json.loads(r['rows'])) if r else None


def _place(value, snap, metric):
    """Cutoff for the top 1% and where value lands."""
    vals = sorted((v for v in snap['data']['vals'] if v is not None), reverse=True)
    total = snap['total']
    k = max(1, math.ceil(total / 100))
    cutoff = vals[k - 1] if k <= len(vals) else None
    out = {'total': total, 'top1_rank': k, 'top1_cutoff': cutoff, 'exact': cutoff is not None,
           'top100_cutoff': vals[-1] if vals else None, 'best': vals[0] if vals else None,
           'median_top100': statistics.median(vals) if vals else None}
    if value is None:
        return out
    if vals and value >= vals[-1]:
        rank = 1 + sum(1 for v in vals if v > value)
        out.update(rank=rank, top_pct=round(rank / total * 100, 2))
    else:
        out.update(rank=None, top_pct=None, note=f'outside the top {len(vals)} shown')
    if cutoff is not None:
        out['in_top1'] = value >= cutoff
        out['gap_x'] = round(cutoff / value, 2) if value and value < cutoff else None
    return out


def status(con, league=None):
    _setup(con)
    rows = con.execute('SELECT league, scope, metric, total, MAX(ts) ts FROM bench GROUP BY league, scope, metric '
                       'ORDER BY ts DESC').fetchall()
    chars = con.execute('SELECT league, scope, COUNT(*) n, MAX(ts) ts FROM bench_char GROUP BY league, scope').fetchall()
    return {'lists': [dict(r) for r in rows], 'characters': [dict(r) for r in chars]}


def check(con, build_id, league=None, scope=None):
    _setup(con)
    s = pob.stats_for(con, int(build_id))
    st = s['stats']
    best_skill = max(s.get('skills') or [{'skill': s.get('main_skill'), 'dps': 0}], key=lambda x: x['dps'] or 0)
    mine = {'level': s.get('level'),
            'dps': max(best_skill['dps'] or 0, st.get('DPS (combined)') or 0) or None,
            'ehp': st.get('effective HP'), 'life': st.get('life'), 'es': st.get('energy shield')}
    brow = con.execute('SELECT league, ascendancy FROM build WHERE id=?', (int(build_id),)).fetchone()
    # which benchmark league: the one asked for, else the newest saved
    if not league:
        r = con.execute('SELECT league FROM bench ORDER BY ts DESC LIMIT 1').fetchone()
        league = r['league'] if r else ninja.current_league(con)
    scope = scope or s.get('ascendancy') or 'All'
    out = {'build': s['build'], 'build_id': int(build_id), 'ascendancy': s.get('ascendancy'), 'league': league,
           'your_build_league': brow['league'] if brow else None, 'scope': scope, 'yours': mine,
           'best_skill': best_skill.get('skill'), 'axes': {}, 'missing': []}
    for metric in METRICS:
        snap = _latest(con, league, scope, metric)
        allsnap = _latest(con, league, 'All', metric)
        if not snap:
            out['missing'].append(f'{scope} by {metric}')
            continue
        p = _place(mine[metric], snap, metric)
        p['as_of'] = snap['ts']
        p['top5'] = [{'name': n, 'value': v} for n, v in snap['data']['top']]
        if allsnap:
            a = _place(mine[metric], allsnap, metric)
            p['league'] = {k: a.get(k) for k in ('total', 'rank', 'top100_cutoff', 'best', 'note')}
        out['axes'][metric] = p
    # wealth: your priced gear vs top-1% characters sampled
    sv = cost.slot_values(con, int(build_id), league=league)
    my_gear = round((sv['total_div'] or 0) - (sv['gems_div'] or 0), 2)
    samples = con.execute('SELECT name, level, icons FROM bench_char WHERE league=? AND scope=?',
                          (league, scope)).fetchall()
    vals = []
    for c in samples:
        g = gear_value_from_icons(con, json.loads(c['icons']), league)
        vals.append({'name': c['name'], 'level': c['level'], 'value_div': g['value_div'],
                     'top_items': g['parts'][:3]})
    vals.sort(key=lambda x: -x['value_div'])
    w = {'yours_div': my_gear, 'sample': vals, 'rares_unpriced': sv['rares_unpriced']}
    if vals:
        v = [x['value_div'] for x in vals]
        w.update(median_div=round(statistics.median(v), 2), low_div=min(v), high_div=max(v),
                 in_top1=my_gear >= statistics.median(v),
                 gap_div=round(statistics.median(v) - my_gear, 2) if my_gear < statistics.median(v) else 0)
    else:
        out['missing'].append('top-1% characters for wealth')
    out['axes']['wealth'] = w
    rt = money.rates(con, league)
    if w.get('median_div') is not None:
        w['median'] = money.fmt(w['median_div'], rt)
    w['yours'] = money.fmt(my_gear, rt)
    # verdict + what closes each gap
    passed = [m for m, p in out['axes'].items() if p.get('in_top1')]
    checked = [m for m, p in out['axes'].items() if 'in_top1' in p]
    out['score'] = f'{len(passed)} of {len(checked)}'
    todo = []
    a = out['axes']
    if 'level' in a and a['level'].get('in_top1') is False:
        todo.append('Level: top 1%% starts at level %d. Farm the top mechanic on the Farming tab in high-tier maps; '
                    'XP is the slowest axis, start early.' % a['level']['top1_cutoff'])
    if 'dps' in a and a['dps'].get('in_top1') is False:
        todo.append('DPS: %.1f× short of the top-1%% cutoff. Run the upgrade finder (DPS per divine) and compare '
                    'with a top %s.' % (a['dps']['gap_x'], scope))
    if 'ehp' in a and a['ehp'].get('in_top1') is False:
        todo.append('Effective HP: %.1f× short. Look at the defence column in the upgrade finder, and compare '
                    'how the top %ss defend themselves.' % (a['ehp']['gap_x'], scope))
    if w.get('in_top1') is False:
        todo.append(f"Gear value: about {money.fmt(w['gap_div'], rt)} below the typical top-1% {scope}. "
                    'Farm and craft-to-sell before buying.')
    out['next_steps'] = todo
    out['notes'] = ['poe.ninja only tracks public ladder characters, so its top 1% is already the very top of the '
                    'player base: a stricter bar than "top 1% of everyone".',
                    "DPS: yours is Path of Building's number for your best skill; poe.ninja's is its own PoB run of "
                    'their main skill. Close, not identical.',
                    'Wealth counts uniques, runes and unique jewels on both sides; rares are left out on both.']
    if out['your_build_league'] and out['your_build_league'] != league:
        out['notes'].insert(0, f"Your build is from {out['your_build_league']}; the benchmark is {league}. "
                               'In 1.0 both will be the same league.')
    return out
