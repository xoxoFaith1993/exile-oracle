"""Step 4: aggregate the measured cases into rules, write ../patch-impact.json and the MEASURED block of ../rules.py.
Inputs: cache/forum/patches_raw.json, cache/events.json, cache/measured.json, cache/ninja_measured.json,
        cache/wiki/versions_cargo.json, cache/steam/steam_news.json, cache/reviewed.json (hand review, optional)
Usage: python -I build_outputs.py"""
import datetime as dt
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import rules  # noqa: E402

C = os.path.join(HERE, 'cache')
WINDOWS = ('h24', 'h72', 'd7')
SIGN = {'up': 1, 'down': -1}


def load(name, default=None):
    p = os.path.join(C, name)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else default


def version_of(title):
    m = re.search(r'(\d+\.\d+\.\d+)\.?([a-z])?', title)
    return (m.group(1) + (m.group(2) or '')) if m else None


def q(v, p):
    v = sorted(v)
    if not v:
        return None
    k = (len(v) - 1) * p
    f = int(k)
    return v[f] + (v[min(f + 1, len(v) - 1)] - v[f]) * (k - f)


def expected_sign(rule_id, line_text):
    r = next(x for x in rules.RULES if x['id'] == rule_id)
    if r['direction'] in SIGN:
        return SIGN[r['direction']]
    if r['direction'] == 'by_direction':
        d = rules.direction_of(line_text)
        return 1 if d == 'buff' else -1 if d == 'nerf' else 0
    return 0


def main():
    posts = load('forum/patches_raw.json', [])
    measured = {e['thread']: e for e in load('measured.json', [])}
    events = {e['thread']: e for e in load('events.json', [])}
    ninja = load('ninja_measured.json', [])
    reviewed = load('reviewed.json', {})          # {"thread|line-start": {"keep": bool, "note": str, ...}}
    wiki = {}
    for r in (load('wiki/versions_cargo.json', {}) or {}).get('cargoquery', []):
        t = r['title']
        wiki[t['version']] = t.get('release date', '')[:10]
    steam = {}
    for it in (load('steam/steam_news.json', {}) or {}).get('appnews', {}).get('newsitems', []):
        v = version_of(it['title'])
        if v and ('patch' in it['title'].lower() or 'hotfix' in it['title'].lower() or 'content update' in it['title'].lower()):
            steam.setdefault(v, dt.datetime.fromtimestamp(it['date'], dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))

    # ---------------- patches ----------------
    out_patches, cases = [], []
    for p in posts:
        ev = events.get(p['thread'], {})
        me = measured.get(p['thread'])
        mlines = {l['text']: l for l in (me or {}).get('lines', [])}
        lines = []
        for l in ev.get('lines', []):
            ml = mlines.get(l['text'], {})
            hits = l['hits']
            key = f"{p['thread']}|{l['text'][:60]}"
            rv = reviewed.get(key, {})
            entry = {'text': l['text'], 'section': l['section'],
                     'class': hits[0]['class'] if hits else None,
                     'rules': [h['rule'] for h in hits],
                     'direction': hits[0]['direction'] if hits else None,
                     'affected': [h['affected_group'] for h in hits][:3],
                     'affected_items': [i['name'] for i in ml.get('items', [])][:10],
                     'affected_how': l.get('how'), 'n_items': ml.get('n_items_total', len(l.get('ids', [])))}
            m = ml.get('measured')
            if m:
                entry['measured'] = {w: m.get(w) for w in ('h24', 'h72', 'd7') if m.get(w)}
                entry['measured']['pre7'] = m.get('pre7')
                entry['measured']['basis'] = 'sourced: GGG exchange history, abnormal = vs same-group drift'
            else:
                entry['measured'] = None
            if rv:
                entry['review'] = rv
            lines.append(entry)
            if m and not rv.get('exclude'):
                for h in hits:
                    if h['class'] in ('skill', 'unique', 'ascendancy'):
                        continue   # these move uniques / gems, not exchange items (see unique_cases_poe_ninja)
                    cases.append({'thread': p['thread'], 'post': p['title'], 'date_utc': p['date_utc'],
                                  'league': me.get('league'), 'league_day': me.get('league_day'),
                                  'rule': h['rule'], 'class': h['class'], 'how': l.get('how'),
                                  'sign': expected_sign(h['rule'], l['text']), 'text': l['text'],
                                  'ids': tuple(sorted(l.get('ids', []))), 'm': m, 'items': ml.get('items', [])[:5],
                                  'noise': me.get('noise', {}), 'review': rv})
        v = version_of(p['title'])
        out_patches.append({'version': v, 'title': p['title'], 'date_utc': p['date_utc'],
                            'posted_forum_pacific': p['posted_pacific'], 'url': p['url'],
                            'wiki_release_date': wiki.get(v) if v else None,
                            'steam_post_utc': steam.get(v) if v and ('hotfix' not in p['title'].lower()) else None,
                            'league_day': ev.get('league_day'), 'content_update': ev.get('content_update', False),
                            'n_lines_total': len(p['lines']), 'measured': bool(me),
                            'lines': lines})

    # one case per (post, rule, item set): repeated sub-lines of one change don't count twice
    seen, uniq = set(), []
    for c in cases:
        k = (c['thread'], c['rule'], c['ids'])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(c)
    cases = uniq

    # ---------------- noise floor ----------------
    noise = {}
    for w in WINDOWS:
        v = [e['noise'][w]['median_abs_abnormal'] for e in measured.values() if w in e.get('noise', {})]
        noise[w] = round(statistics.median(v), 1) if v else None

    # ---------------- rules ----------------
    groups = {}
    for c in cases:
        prec = 'named item' if c['how'] == 'named' else 'item family' if c['how'] == 'family' else 'mechanic outputs'
        groups.setdefault((c['rule'], prec), []).append(c)
        groups.setdefault((c['rule'], 'all'), []).append(c)
    out_rules, measured_block = [], {}
    rule_meta = {r['id']: r for r in rules.RULES}
    for (rid, prec), cs in sorted(groups.items()):
        r = rule_meta[rid]
        stats = {}
        for w in WINDOWS:
            vals = [(c['m'][w]['median_abnormal'], c) for c in cs if c['m'].get(w)]
            if not vals:
                continue
            v = [x for x, _ in vals]
            signs = [c['sign'] for _, c in vals]
            nz = noise.get(w) or 0
            directional = any(s != 0 for s in signs)
            if directional:
                agree = [x * s > 0 for x, s in zip(v, signs) if s != 0]
                beyond = [x * s > 0 and bool(c['m'][w].get('beyond_noise')) for (x, c), s in zip(vals, signs) if s != 0]
                hit = sum(agree) / len(agree) if agree else None
                hit_beyond = sum(beyond) / len(beyond) if beyond else None
            else:
                hit = hit_beyond = None
            pvs = [(c['m'][w]['median_phase_abnormal'], c['sign']) for _, c in vals
                   if c['m'][w].get('median_phase_abnormal') is not None]
            pv = [x for x, _ in pvs]
            pvs = [(x, sg) for x, sg in pvs if sg != 0]
            share_beyond = sum(1 for _, c in vals if c['m'][w].get('beyond_noise')) / len(vals)
            stats[w] = {'share_beyond_placebo_p90': round(share_beyond, 2),'n': len(v), 'median': round(statistics.median(v), 1),
                        'p25': round(q(v, .25), 1), 'p75': round(q(v, .75), 1),
                        'median_abs': round(statistics.median(abs(x) for x in v), 1),
                        'hit_rate': round(hit, 2) if hit is not None else None,
                        'hit_rate_beyond_noise': round(hit_beyond, 2) if hit_beyond is not None else None,
                        'phase_n': len(pv), 'phase_median': round(statistics.median(pv), 1) if pv else None,
                        'phase_hit_rate': round(sum(1 for x, sg in pvs if x * sg > 0) / len(pvs), 2) if pvs else None,
                        'pre7_median': round(statistics.median([c['m']['pre7']['median_abnormal'] for _, c in vals if c['m'].get('pre7')] or [0]), 1)}
        if not stats:
            continue
        # headline window: the longest window with >= 3 cases, else the one with most cases
        best = next((w for w in ('d7', 'h72', 'h24') if stats.get(w, {}).get('n', 0) >= 3), max(stats, key=lambda w: stats[w]['n']))
        s = stats[best]
        n = s['n']
        hr = s['hit_rate']
        nz = noise.get(best) or 0
        hb = s['hit_rate_beyond_noise'] or 0
        if r['direction'] in ('volatile',):
            conf = 'medium' if n >= 8 and s['share_beyond_placebo_p90'] >= 0.5 else 'low'
        elif hr is None:
            conf = 'low'
        elif n >= 8 and hr >= 0.7 and hb >= 0.5:
            conf = 'high'
        elif n >= 4 and hr >= 0.6 and hb >= 0.3:
            conf = 'medium'
        else:
            conf = 'low'
        ph = s.get('phase_hit_rate')
        if ph is not None and s['phase_n'] >= 3 and ph < 0.5:
            conf = {'high': 'medium', 'medium': 'low'}.get(conf, conf)   # the move did not survive the phase control
        ex = sorted(cs, key=lambda c: -abs((c['m'].get(best) or {}).get('median_abnormal', 0)))
        examples = [{'post': c['post'], 'date_utc': c['date_utc'], 'line': c['text'][:220],
                     'items': [i['name'] for i in c['items']][:4],
                     'abnormal_pct': {w: (c['m'].get(w) or {}).get('median_abnormal') for w in WINDOWS},
                     'phase_abnormal_pct': {w: (c['m'].get(w) or {}).get('median_phase_abnormal') for w in ('h72', 'd7')},
                     'raw_pct': {w: (c['m'].get(w) or {}).get('median_raw') for w in WINDOWS}} for c in ex[:5]]
        trig = r['re'] if r['re'] != '(?!)' else 'line names a league mechanic + reward words, no specific rule hit'
        entry = {'rule': rid, 'trigger_pattern': trig, 'class': r['class'], 'precision': prec,
                 'expected_direction': r['direction'], 'affected_group': prec if prec != 'all' else 'any',
                 'typical_move_pct': s['median'], 'window': best, 'n_cases': n,
                 'spread': {'p25': s['p25'], 'p75': s['p75']}, 'hit_rate': hr,
                 'hit_rate_beyond_noise': s['hit_rate_beyond_noise'], 'confidence': conf,
                 'phase_adjusted_move_pct': s.get('phase_median'), 'phase_n': s.get('phase_n'),
                 'phase_hit_rate': s.get('phase_hit_rate'),
                 'by_window': stats, 'noise_floor_pct': nz, 'basis': 'sourced (measured)',
                 'examples': examples}
        out_rules.append(entry)
        if prec == 'all':
            measured_block[rid] = {'typical_move_pct': s['median'], 'window': best, 'n_cases': n,
                                   'spread': [s['p25'], s['p75']], 'confidence': conf, 'hit_rate': hr,
                                   'phase_adjusted_move_pct': s.get('phase_median'), 'phase_n': s.get('phase_n')}
    json.dump({'cases': [{k: v for k, v in c.items() if k != 'ids'} for c in cases], 'noise': noise},
              open(os.path.join(C, 'cases.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)

    # unique items (poe.ninja daily history)
    uniq_cases = []
    for u in ninja:
        uniq_cases.append({k: u.get(k) for k in ('post', 'date_utc', 'league', 'unique', 'line', 'direction', 'base_div', 'd1', 'd3', 'd7')})

    cur_rows, cur_block = curated_rules()
    for k, v in cur_block.items():          # hand-reviewed numbers win over the automated ones
        measured_block[k] = v
    for e in out_rules:
        e['precision'] = 'automated classifier: ' + e['precision']
    doc = load('static_sections.json', {})
    out = {
        'generated': '2026-11-21', 'title': 'Exile Oracle: patch -> price impact dataset (PoE 2 0.1-0.5.5h)',
        'method': doc.get('method'), 'noise_floor_pct': noise,
        'patches': out_patches,
        'rules': cur_rows + out_rules,
        'unique_cases_poe_ninja': uniq_cases,
        'reading_checklist': doc.get('reading_checklist', []),
        'sources': doc.get('sources', []),
        'not_verified': doc.get('not_verified', []),
    }
    json.dump(out, open(os.path.join(ROOT, 'patch-impact.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)

    # MEASURED block in rules.py
    rp = os.path.join(ROOT, 'rules.py')
    s = open(rp, encoding='utf-8').read()
    a, b = s.index('# --- BEGIN MEASURED'), s.index('# --- END MEASURED ---')
    block = ('# --- BEGIN MEASURED (generated by scripts/build_outputs.py; do not edit by hand) ---\n'
             'MEASURED = ' + json.dumps(measured_block, indent=4).replace('null', 'None') + '\n')
    s = s[:a] + block + s[b:]
    open(rp, 'w', encoding='utf-8').write(s)
    for e in cur_rows:
        print(f"CURATED {e['rule']:20} n={e['n_cases']:2} {e['window']} move {e['typical_move_pct']:+.1f}% hit {e['hit_rate']} beyond {e['hit_rate_beyond_placebo']} phase {e['phase_hit_rate']} {e['confidence']}")
    print(len(out_patches), 'posts,', len(cases), 'cases,', len(out_rules), 'rule rows; noise', noise)
    for e in out_rules:
        if e['precision'] == 'all':
            print(f"{e['rule']:24} n={e['n_cases']:3} {e['window']} med {e['typical_move_pct']:+6.1f}% "
                  f"IQR [{e['spread']['p25']:+.0f},{e['spread']['p75']:+.0f}] hit {e['hit_rate']} hb {e['hit_rate_beyond_noise']} ph {e['phase_adjusted_move_pct']}/{e['phase_n']}/{e['phase_hit_rate']} {e['confidence']}")


# ---------------- hand-reviewed (curated) cases -> the primary rulebook ----------------
FAMILIES = {
    'supply_up_named': {'rules': ['drop_source_added', 'drop_rate_up'], 'expect': 'down',
                        'trigger': "'now (also) drops / has a chance to drop / always drops', 'increased the drop rate', 'X% more', 'more common' + a named exchange item",
                        'affected': 'the named item(s)', 'class': 'drop_source / drop_rate'},
    'supply_down_named': {'rules': ['drop_source_removed', 'drop_rate_down'], 'expect': 'up',
                          'trigger': "'no longer drops', 'lowered the drop rate', 'rarer' + a named exchange item",
                          'affected': 'the named item(s)', 'class': 'drop_source / drop_rate'},
    'farm_nerf_outputs': {'rules': ['farm_nerf', 'exploit_fix'], 'expect': 'up',
                          'trigger': "diminishing returns, caps, 'reduced the rewards/number of chests', exploit/infinite/duplicate fixes on a farm",
                          'affected': "the farm's outputs (e.g. temple -> Vaal currency + soul cores; Ritual -> omens)", 'class': 'farm / exploit_fix'},
    'farm_buff_outputs': {'rules': ['farm_buff'], 'expect': 'down',
                          'trigger': "'greatly improved', 'doubled the runs', 'increased item rarity per depth' for a mechanic",
                          'affected': "the mechanic's outputs", 'class': 'farm'},
    'entry_item': {'rules': ['farm_buff_entry', 'farm_nerf_entry'], 'expect': 'by case',
                   'trigger': "a change to how rewarding a mechanic is, read for its ENTRY item (Logbook, Simulacrum, Breachstone)",
                   'affected': 'the entry item (up if the farm got better, down if worse)', 'class': 'league_mechanic'},
    'crafting_use': {'rules': ['crafting_use_removed', 'crafting_new_use'], 'expect': 'by case',
                     'trigger': "'can no longer be applied to', 'can once again be applied to', new uses",
                     'affected': 'the crafting item', 'class': 'crafting'},
    'socketable_stats': {'rules': ['socketable_change', 'socketable_limit'], 'expect': 'by case',
                         'trigger': "soul core / rune stat changes ('now grants X (previously Y)', 'now has a Limit of 1')",
                         'affected': 'that soul core / rune', 'class': 'crafting (socketable)'},
}
# sub-families: the same cases split by shock size / league timing
FAMILIES['supply_up_named:big'] = dict(FAMILIES['supply_up_named'], key_suffix=':big',
                                       pred=lambda c: rules.magnitude(c['line'] or '', c['rule']) == 'big',
                                       trigger="new source ('now has a chance to drop', 'always drops') or a stated >=50% / 'significantly' increase, named item")
FAMILIES['supply_up_named:small'] = dict(FAMILIES['supply_up_named'], key_suffix=':small',
                                         pred=lambda c: rules.magnitude(c['line'] or '', c['rule']) == 'small',
                                         trigger="plain 'increased the drop rate' / redistribution of drop weight, no size stated")
FAMILIES['farm_nerf_outputs:early'] = dict(FAMILIES['farm_nerf_outputs'], key_suffix=':early',
                                           pred=lambda c: (c['league_day'] or 0) < 15,
                                           trigger='farm nerf / exploit fix in league days 0-14')
FAMILIES['farm_nerf_outputs:mid_late'] = dict(FAMILIES['farm_nerf_outputs'], key_suffix=':mid_late',
                                              pred=lambda c: (c['league_day'] or 0) >= 15,
                                              trigger='farm nerf / exploit fix from league day 15 on')


def _actual_spread(s, expect, rid):
    """p25/p75 of the actual signed move (negative = falls), from the expected-direction quartiles."""
    lo, hi = s['p25_expected_dir'], s['p75_expected_dir']
    down = expect == 'down' or (expect == 'by case' and rid in ('crafting_use_removed',))
    return [-hi, -lo] if down else [lo, hi]


def curated_rules():
    cm = load('curated_measured.json', [])
    rows, block = [], {}
    for fam, f in FAMILIES.items():
        cs = [c for c in cm if c['rule'] in f['rules'] and c['windows'] and f.get('pred', lambda c: True)(c)]
        if not cs:
            continue
        stats = {}
        for w in ('h24', 'h72', 'd7'):
            v = [(c['windows'][w], c) for c in cs if w in c['windows']]
            if not v:
                continue
            sgn = [1 if c['expect'] == 'up' else -1 for _, c in v]
            ab = [x['median_abnormal'] for x, _ in v]
            best = [x['median_phase_abnormal'] if x.get('median_phase_abnormal') is not None else x['median_abnormal'] for x, _ in v]
            ph = [(x['median_phase_abnormal'], s) for (x, _), s in zip(v, sgn) if x.get('median_phase_abnormal') is not None]
            signed = [a * s for a, s in zip(best, sgn)]          # + = moved the expected way
            stats[w] = {'n': len(v),
                        'median_move_pct': round(statistics.median(best), 1),
                        'median_move_in_expected_direction_pct': round(statistics.median(signed), 1),
                        'p25_expected_dir': round(q(signed, .25), 1), 'p75_expected_dir': round(q(signed, .75), 1),
                        'hit_rate': round(sum(1 for x in signed if x > 0) / len(signed), 2),
                        'hit_rate_beyond_placebo': round(sum(1 for (x, _), s in zip(v, sgn) if x['median_abnormal'] * s > 0 and x['beyond_noise']) / len(v), 2),
                        'group_adjusted_median_pct': round(statistics.median(ab), 1),
                        'phase_n': len(ph),
                        'phase_hit_rate': round(sum(1 for x, s in ph if x * s > 0) / len(ph), 2) if ph else None}
        # headline window: where the move agreed most often with the expectation (all windows stay in by_window)
        okw = [w for w in ('h24', 'h72', 'd7') if stats.get(w, {}).get('n', 0) >= 3] or list(stats)
        wbest = max(okw, key=lambda w: (stats[w]['hit_rate'], stats[w]['phase_hit_rate'] or 0, stats[w]['n'], w == 'h72'))
        s = stats[wbest]
        n, hr, hb = s['n'], s['hit_rate'], s['hit_rate_beyond_placebo']
        ph = s['phase_hit_rate']
        if n >= 10 and hr >= 0.7 and (ph is None or ph >= 0.6) and hb >= 0.3:
            conf = 'high'
        elif n >= 4 and hr >= 0.6 and (ph is None or ph >= 0.5):
            conf = 'medium'
        else:
            conf = 'low'
        signed_move = s['median_move_in_expected_direction_pct']
        typical = signed_move if f['expect'] == 'up' else -signed_move if f['expect'] == 'down' else signed_move
        ex = []
        for c in sorted(cs, key=lambda c: -abs((c['windows'].get(wbest) or {}).get('median_abnormal', 0))):
            ex.append({'case': c['id'], 'post': c['post'], 'date_utc': c['date_utc'], 'league': c['league'],
                       'league_day': c['league_day'], 'line': (c['line'] or '')[:220], 'expect': c['expect'],
                       'items': c['items_spec'][:6],
                       'group_adjusted_pct': {w: c['windows'][w]['median_abnormal'] for w in ('h24', 'h72', 'd7') if w in c['windows']},
                       'phase_adjusted_pct': {w: c['windows'][w]['median_phase_abnormal'] for w in ('h72', 'd7') if w in c['windows']},
                       'raw_pct': {w: c['windows'][w]['median_raw'] for w in ('h24', 'h72', 'd7') if w in c['windows']},
                       'url': c['url']})
        rows.append({'rule': fam, 'trigger_pattern': f['trigger'], 'class': f['class'], 'affected_group': f['affected'],
                     'expected_direction': f['expect'], 'typical_move_pct': typical,
                     'typical_move_note': ('signed: negative = price falls' if f['expect'] in ('up', 'down')
                                           else 'in the EXPECTED direction of each case (+ = moved as predicted)'),
                     'window': wbest, 'n_cases': n,
                     'spread': {'p25': s['p25_expected_dir'], 'p75': s['p75_expected_dir'], 'note': 'in expected direction'},
                     'hit_rate': hr, 'hit_rate_beyond_placebo': hb, 'phase_hit_rate': ph, 'confidence': conf,
                     'by_window': stats, 'basis': 'sourced: hand-reviewed lines, GGG exchange history (measured)',
                     'precision': 'hand-reviewed', 'examples': ex})
        for rid in f['rules']:
            if rid in ('farm_buff_entry', 'farm_nerf_entry', 'socketable_limit'):
                continue
            mv = typical if f['expect'] in ('up', 'down') else (signed_move if rid in ('crafting_new_use', 'socketable_change') else -signed_move)
            block[rid + f.get('key_suffix', '')] = {'typical_move_pct': mv, 'window': wbest, 'n_cases': n,
                          'spread': _actual_spread(s, f['expect'], rid),
                          'phase_hit_rate': ph,
                          'confidence': conf, 'hit_rate': hr, 'source': 'hand-reviewed family ' + fam}
    return rows, block


if __name__ == '__main__':
    main()
