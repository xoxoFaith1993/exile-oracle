"""Hand-reviewed cases (cache/curated.json): lines I read and judged as clear supply / demand changes, with the exact
exchange items they touch and the expected direction. Same measurement as measure.py (2-hour base, h24/h72/d7,
same-group drift control, matched-size placebo) plus the cross-league phase control (same item, same league-day
window in two other leagues).
Usage: python -I measure_curated.py fetch   -> fetches any missing hours (2.5 s apart)
       python -I measure_curated.py         -> cache/curated_measured.json"""
import json
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import exchange  # noqa: E402
import measure as M  # noqa: E402

C = M.C


def ids_for(spec, meta, exclude=()):
    out = set()
    for s in spec:
        if s.startswith('GROUP:'):
            g = s[6:]
            out |= {k for k, v in meta.items() if v['group'] == g}
        elif s.startswith('PREFIX:'):
            pre, suf = s[7:].split('|')
            out |= {k for k, v in meta.items() if v['name'].startswith(pre) and v['name'].endswith(suf)}
        else:
            out |= {k for k, v in meta.items() if v['name'] == s}
    ex = {k for k, v in meta.items() if v['name'] in exclude}
    return sorted(out - ex)


def load():
    cur = json.load(open(os.path.join(C, 'curated.json'), encoding='utf-8'))
    posts = {p['thread']: p for p in json.load(open(os.path.join(C, 'forum', 'patches_raw.json'), encoding='utf-8'))}
    return cur, posts


def hours_needed():
    cur, posts = load()
    main, phase = set(), set()
    for c in cur:
        p = posts[c['thread']]
        h0 = M.hour_of(p['date_utc']) - 3600
        for o in M.OFFS.values():
            main.add(h0 + o * 3600)
        main.add(h0 - 3600)
        _, hs = M.phase_hours({'h0': h0})
        phase |= {(lg, h) for _, lg, h in hs}
    return sorted(h for h in main if h <= M.LAST_HOUR), sorted(phase)


def fetch():
    main, phase = hours_needed()
    for h in main:
        if not os.path.exists(os.path.join(C, 'prices', f'{h}.json')):
            print('main', h, flush=True)
            exchange.prices(h)
    for lg, h in phase:
        if not os.path.exists(os.path.join(C, 'prices_lg', f"{lg.replace(' ', '_')}_{h}.json")):
            print('phase', lg, h, flush=True)
            try:
                exchange.prices_league(h, lg)
            except Exception as e:
                print('ERR', lg, h, e, flush=True)


def run():
    cur, posts = load()
    meta, _ = M.load_meta()
    rnd = random.Random(5)
    out = []
    for c in cur:
        p = posts[c['thread']]
        line = next((l['text'] for l in p['lines'] if l['text'].startswith(c['match']) or c['match'] in l['text']), None)
        h0 = M.hour_of(p['date_utc']) - 3600
        lg0 = M._league(h0)
        ids = ids_for(c['items'], meta, c.get('exclude_items', ()))
        sign = 1 if c['expect'] == 'up' else -1
        res = {'id': c['id'], 'thread': c['thread'], 'post': p['title'], 'url': p['url'], 'date_utc': p['date_utc'],
               'league': lg0, 'league_day': M.league_day(h0), 'rule': c['rule'], 'expect': c['expect'],
               'line': line, 'line_found': bool(line), 'items_spec': c['items'], 'note': c.get('note'), 'windows': {}}
        lgp, hs = M.phase_hours({'h0': h0})
        by = {}
        for w, comp, h in hs:
            by.setdefault(comp, {})[w] = h
        per_item = {}
        for w, o in M.OFFS.items():
            if w == 'base':
                continue
            a, b = (h0 + o * 3600, h0) if o < 0 else (h0, h0 + o * 3600)
            if M._league(a) != lg0 or M._league(b) != lg0:
                continue
            u = M._universe(a, b)
            pool = [k for k in u if k not in ids]
            if len(pool) < 20:
                continue
            mk = statistics.median(u[k] for k in pool)
            rows = []
            for it in ids:
                if it == M.DIV:
                    ch = M._chg(a, b, it)
                    if ch is None:
                        continue
                    drift, dk = 0.0, 'none (Div in Ex)'
                else:
                    if it not in u:
                        continue
                    ch = u[it]
                    g = meta[it]['group']
                    peers = [u[k] for k in pool if meta.get(k, {}).get('group') == g]
                    drift, dk = (statistics.median(peers), 'group') if len(peers) >= 4 else (mk, 'market')
                ab = (1 + ch) / (1 + drift) - 1
                r = {'name': meta[it]['name'], 'raw': round(ch * 100, 1), 'drift': round(drift * 100, 1),
                     'drift_kind': dk, 'abnormal': round(ab * 100, 1)}
                if w in ('h72', 'd7') and it != M.DIV:
                    cs = []
                    for comp, hh in by.items():
                        if 'base' in hh and w in hh:
                            x0, x1 = M._plg(comp, hh['base'], it), M._plg(comp, hh[w], it)
                            cmk = M.comp_market(comp, hh['base'], hh[w])
                            if x0 and x1 and cmk is not None:
                                # difference in differences: item vs the same item in the other league, net of
                                # how each league's whole market moved over those hours
                                cs.append(((1 + ch) / (x1 / x0)) / ((1 + mk) / (1 + cmk)) - 1)
                    if cs:
                        r['phase_abnormal'] = round(statistics.median(cs) * 100, 1)
                        r['phase_leagues'] = len(cs)
                rows.append(r)
            if not rows:
                continue
            v = [r['abnormal'] for r in rows]
            med = statistics.median(v)
            k = min(len(v), len(pool))
            sims = sorted(abs(statistics.median(((1 + u[x]) / (1 + mk) - 1) * 100 for x in rnd.sample(pool, k)))
                          for _ in range(300))
            p90 = sims[int(0.9 * len(sims))]
            pv = [r['phase_abnormal'] for r in rows if 'phase_abnormal' in r]
            res['windows'][w] = {'n_items': len(rows), 'median_raw': round(statistics.median(r['raw'] for r in rows), 1),
                                 'median_abnormal': round(med, 1), 'placebo_p90_abs': round(p90, 1),
                                 'beyond_noise': abs(med) > p90, 'agrees': med * sign > 0 if w != 'pre7' else None,
                                 'median_phase_abnormal': round(statistics.median(pv), 1) if pv else None,
                                 'n_phase': len(pv)}
            per_item[w] = sorted(rows, key=lambda r: r['name'])
        top = {}
        for w, rows in per_item.items():
            for r in rows:
                top.setdefault(r['name'], {})[w] = {k: r[k] for k in ('raw', 'abnormal', 'phase_abnormal') if k in r}
        res['items'] = dict(list(top.items())[:15])
        res['n_items_total'] = len(top)
        out.append(res)
        w = res['windows']
        print(c['id'], p['title'][:18], f"d{res['league_day']}", c['rule'][:18], c['expect'], len(top), '|',
              ' '.join(f"{k}:{v['median_abnormal']:+.0f}{'*' if v['beyond_noise'] else ''}/ph{v['median_phase_abnormal']}" for k, v in w.items()),
              '' if line else 'LINE NOT FOUND')
    json.dump(out, open(os.path.join(C, 'curated_measured.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'fetch':
        fetch()
    else:
        run()
