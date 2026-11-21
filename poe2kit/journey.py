"""League plan (Level 2 refine, session 2; the author 2026-11-21: "league start to mid game to end game to min max ...
a tool to help people, not fully guide them and hold their hand").

Six stages, each with a goal, "ready to move on" checks, what to do and what to farm:
  1 League start (before you play)   2 Campaign   3 Early maps (tiers 1-10)   4 Red maps (tiers 15-16)
  5 Juicing and pinnacle bosses      6 Min-max (the top 1%)
The checks are measured on the player's build by Path of Building (life, energy shield, effective HP, the biggest
hit per damage type, resistances, DPS) against researched thresholds; every check names its source and how sure
it is (datapack/boss-readiness.json, datapack/farming.json, poe2kit/campaign.py). Nothing is invented here: a
stage without data says so. It is a map with checkpoints, not a script: the player decides.

Fail-safe: every part is measured separately; a part that can't be measured (no Path of Building yet, no build,
no data) is marked "not measured" with what to do, and the rest of the plan still shows. Without a build it is a
plan "from scratch": the goals of every stage and how to pick a build."""

import json

from . import config, db

STAGES = ('start', 'campaign', 'early', 'red', 'endgame', 'minmax')
NAMES = {'start': 'League start (before you play)', 'campaign': 'Campaign (level 1 to about 65)',
         'early': 'Early maps (tiers 1-10)', 'red': 'Red maps (tiers 15-16)',
         'endgame': 'Juicing and pinnacle bosses', 'minmax': 'Min-max (the top 1%)'}
GLOSSARY = {
    'effective HP': "Path of Building's estimate of how much damage you can take before dying, after your "
                    'resistances, armour, evasion and so on. Bigger is safer.',
    'biggest hit': 'The largest single hit of one damage type you survive from full life (Path of Building\'s '
                   '"max hit"). One-shots happen when a monster hits harder than this.',
    'resistance cap': 'Fire, cold and lightning resistance stop at 75% (more with "maximum resistance"). '
                      'Maps and bosses are balanced around being capped; every 1% under costs about 4% more damage taken.',
    'DPS': "Damage per second against one target, from Path of Building with your current gear and skills.",
    'red maps': 'Waystone tiers 15 and 16, the hardest regular maps (their icons are red).',
    'juicing': 'Making maps harder for more loot: waystone modifiers, tablets, atlas passives.',
    'pinnacle bosses': 'The hardest endgame bosses (Arbiters, Xesht, Kulemak, Atziri ...).',
}
_cache = {}


def _data(name):
    if name not in _cache:
        p = config.data_file(name)
        _cache[name] = json.load(open(p, encoding='utf-8')) if p else None
    return _cache[name]


def _src(general_check):
    """Source + how sure, from boss-readiness.json's general rules."""
    br = _data('boss-readiness.json') or {}
    for g in br.get('general') or []:
        if g.get('check', '').startswith(general_check):
            s = g.get('source') or ''
            return s.split(' <')[0][:120], g.get('why', '')
    return None, None


def _chk(what, need, have, ok, close=None, source=None, sure='researched', why=None, unit='', gate=True):
    """gate=False: advice only, it doesn't decide the next checkpoint."""
    if have is None:
        state = 'unknown'
    elif ok:
        state = 'ok'
    elif close:
        state = 'close'
    else:
        state = 'no'
    if isinstance(have, float):
        have = round(have) if abs(have) >= 100 else round(have, 1)
    return {'what': what, 'need': need, 'have': have, 'unit': unit, 'state': state, 'source': source,
            'sure': sure, 'why': why, 'gate': gate}


def _measure(con, build_id):
    """Path of Building numbers for the build, or (None, plain reason)."""
    from . import lab, pob, safety
    try:
        d = lab.defence(con, build_id)
        s = pob.stats_for(con, int(build_id))
    except Exception as e:
        return None, safety.explain(e)['error']
    k = d['stats']
    best = max([x.get('dps') or 0 for x in s.get('skills') or []] + [k.get('DPS (combined)') or 0])
    res = {t: k.get(f'{t} res') for t in ('fire', 'cold', 'lightning', 'chaos')}
    return {'level': d.get('level') or s.get('level'), 'main_skill': d.get('main_skill') or s.get('main_skill'),
            'dps': best or None, 'life': k.get('life'), 'es': k.get('energy shield'),
            'life_es': (k.get('life') or 0) + (k.get('energy shield') or 0) or None, 'ehp': k.get('effective HP'),
            'res': res, 'hits': d.get('max_hits') or {}, 'spirit': k.get('spirit'),
            'move': k.get('movement speed x')}, None


def _farms(m, budget_div=None):
    """Farming strategies this build can run now / is closest to, from datapack/farming.json requirements."""
    f = _data('farming.json')
    if not f:
        return [], []
    can, next_ = [], []
    for s in f.get('strategies') or []:
        r = s.get('requirements') or {}
        dps_min, ehp_min = r.get('dps_min') or 0, r.get('ehp_min') or 0
        if not dps_min and not ehp_min:
            continue   # crafting / flipping: not a character goal
        val = (s.get('div_per_hour') or {})
        mid = next((v.get('mid') for k, v in val.items() if v and v.get('mid') is not None and k in ('wk2-3', 'week1')), None)
        row = {'name': s['name'], 'dps_min': dps_min, 'ehp_min': ehp_min, 'div_per_hour_mid': mid,
               'label': r.get('label') or 'estimate', 'notes': r.get('notes'), 'earliest': s.get('earliest_phase')}
        if m and m.get('dps') is not None and m.get('ehp') is not None:
            gap = max(dps_min / m['dps'] if m['dps'] else 9, ehp_min / m['ehp'] if m['ehp'] else 9)
            if gap <= 1:
                can.append(row)
            else:
                next_.append(dict(row, gap=round(gap, 2)))
    can.sort(key=lambda r: -(r['div_per_hour_mid'] or 0))
    next_.sort(key=lambda r: r['gap'])
    return can[:6], next_[:4]


def plan(con, build_id=None, class_name=None, ascendancy=None, budget_div=None, scratch=False):
    """The whole plan. build_id: a vault build (default: the active character). Without a build: from scratch."""
    from . import campaign, chars, vault
    prof = config.profile()
    out = {'theory': [], 'glossary': GLOSSARY, 'experience': config.experience()}
    if build_id is None and not scratch:
        try:
            a = next((x for x in chars.characters(con)['characters'] if x['active']), None)
            build_id = a['id'] if a else None
        except Exception:
            build_id = None
    b = con.execute('SELECT id, label, class, ascendancy, level, main_skill FROM build WHERE id=?',
                    (int(build_id),)).fetchone() if build_id else None
    if build_id and not b:
        raise ValueError('That build is not in the vault (it may have been deleted): pick another one.')
    out['build'] = dict(b) if b else None
    out['class'] = (b['class'] if b else None) or class_name or prof.get('class')
    out['ascendancy'] = (b['ascendancy'] if b else None) or ascendancy or prof.get('ascendancy')
    m, why_not = (_measure(con, b['id']) if b else (None, None))
    out['measured'] = m
    out['not_measured'] = why_not if b else 'No build yet: this is the plan from scratch. Pick a build to measure it.'
    lvl = (m or {}).get('level') or (b['level'] if b else None)

    # ---- the checks, with sources ----
    res_src, res_why = _src('fire_res')
    camp_src, _ = _src('campaign resistances')
    red_src, red_why = _src('life_es for red maps')
    hit_src, hit_why = _src('max hit per type')
    dps_src, dps_why = _src('dps for T15')
    boss_src, _ = _src('dps for pinnacle')
    bl_src, _ = _src('life_es for pinnacle')
    r = (m or {}).get('res') or {}
    ele = [r.get(t) for t in ('fire', 'cold', 'lightning')]
    ele_min = min(ele) if all(v is not None for v in ele) else None
    hits = (m or {}).get('hits') or {}
    low_hit = min(hits.values()) if hits else None
    low_hit_t = min(hits, key=hits.get) if hits else None
    life_es, dps, ehp = (m or {}).get('life_es'), (m or {}).get('dps'), (m or {}).get('ehp')

    stages = {}
    # 1. league start
    st = {'goal': 'Know what you will play and how you will level it, and what to sell or keep on day 1.', 'checks': [],
          'do': [], 'pages': ['league', 'cpactsp', 'prophecy']}
    st['checks'].append(_chk('A build to aim for', 'one in your vault (paste a PoB code, a pobb.in link, save one '
                             'from poe.ninja, or import your character)', b['label'] if b else None, bool(b), sure='-'))
    reviewed = None
    if b:
        try:
            from . import buildplan
            reviewed = bool(buildplan.get(con, b['id']).get('levelling_route'))
        except Exception:
            reviewed = None
    st['checks'].append(_chk('Levelling route reviewed', 'the passive order checked so life and resistances come '
                             'early enough', ('yes' if reviewed else 'not yet') if reviewed is not None else None,
                             bool(reviewed), sure='rule of thumb until reviewed'))
    st['do'] = ['Class and ascendancy chain: skills by level, campaign rewards, ascendancy nodes, cheap levelling '
                'uniques (League start page, or ask the Oracle).',
                'Review the levelling route, then send it to the in-game Build Planner.',
                'Day 1: what to sell straight away and what to keep (League start playbook, from the last launches).']
    stages['start'] = st

    # 2. campaign
    try:
        rw = campaign.rewards()
        got = campaign.done(con)
        n_done, n_all = sum(1 for x in rw if x['key'] in got), len(rw)
    except Exception:
        n_done = n_all = None
    st = {'goal': 'Reach the endgame (about level 65) with every permanent reward: passive points, spirit, '
                  'resistances, life.', 'checks': [], 'pages': ['campaign', 'cpactsp', 'cprewardsp', 'cptipsp']}
    st['checks'].append(_chk('Character level', 'about 65 to start maps', lvl, (lvl or 0) >= 65, (lvl or 0) >= 55,
                             sure='rule of thumb'))
    st['checks'].append(_chk('Permanent rewards ticked', 'all of them (Rewards page)',
                             f'{n_done} of {n_all}' if n_all else None, n_all is not None and n_done >= n_all,
                             n_all is not None and n_done >= n_all * 0.8,
                             sure='your checklist (tick them as you go)', gate=False))
    if (lvl or 0) < 65:
        st['checks'].append(_chk('Elemental resistances while levelling', 'at least 30%', ele_min,
                                 ele_min is not None and ele_min >= 30, unit='%', source=camp_src))
    st['do'] = ['Follow the route act by act; take every reward on the Rewards page (the route panel in game shows '
                'the next one).', 'Do the ascendancy trials when the Rewards page says (about level 22, 38-40, 60+).',
                'Flask upgrades at levels 4, 10, 16, 23, 30, 40, 50, 60; movement speed boots as you find them.']
    out['theory'].append('The campaign route and rewards were researched for 0.5; 1.0 (December 11) adds Acts 5 and '
                         '6 and removes the Interludes, so that part updates after launch.')
    stages['campaign'] = st

    # 3. early maps
    st = {'goal': 'Cap your resistances and build life and damage while the maps are easy.', 'checks': [],
          'pages': ['atlas', 'maps', 'farm']}
    st['checks'].append(_chk('Fire, cold and lightning resistance', '75% (the cap)', ele_min, ele_min is not None and
                             ele_min >= 75, ele_min is not None and ele_min >= 65, unit='%', source=res_src, why=res_why))
    st['checks'].append(_chk('Chaos resistance', 'at least 0%', r.get('chaos'), r.get('chaos') is not None and
                             r['chaos'] >= 0, unit='%', source=_src('chaos_res')[0]))
    st['checks'].append(_chk('Life + energy shield', 'about 3,000 before red maps', life_es, life_es is not None and
                             life_es >= 3000, life_es is not None and life_es >= 2400, source=red_src,
                             sure='researched minimum'))
    st['checks'].append(_chk('DPS (one target)', 'about 100,000 before red maps', dps, dps is not None and dps >= 1e5,
                             dps is not None and dps >= 7e4, source=dps_src, sure='estimate', why=dps_why))
    st['do'] = ['Run every tier once for atlas points; alch and go (no juice).',
                'Fix resistances first: every 1% under the cap is about 4% more damage taken.',
                'Pick a first atlas strategy (Atlas page) that suits a weak character: Essence or plain mapping.']
    stages['early'] = st

    # 4. red maps
    st = {'goal': 'Survive tier 15-16 maps comfortably and start a farming strategy.', 'checks': [],
          'pages': ['maps', 'tablets', 'farm']}
    st['checks'].append(_chk('Life + energy shield', 'at least 4,000 (risky under 3,000)', life_es,
                             life_es is not None and life_es >= 4000, life_es is not None and life_es >= 3000,
                             source=red_src, why=red_why, sure='researched (raised to be safe)'))
    st['checks'].append(_chk('Biggest hit you survive, weakest type', 'at least 5,000 each (risky under 3,500)',
                             low_hit, low_hit is not None and low_hit >= 5000, low_hit is not None and low_hit >= 3500,
                             source=hit_src, why=hit_why, sure='estimate from player reports'))
    if low_hit_t:
        st['checks'][-1]['what'] += f' ({low_hit_t})'
    st['checks'].append(_chk('DPS (one target)', '200,000-500,000 is comfortable (100,000 barely)', dps,
                             dps is not None and dps >= 2e5, dps is not None and dps >= 1e5, source=dps_src,
                             why=dps_why, sure='estimate'))
    st['do'] = ['Roll waystones for safety first (Maps page shows the deadly modifiers for your build).',
                'Start one farming strategy you meet the needs of (below); add tablets for it.']
    stages['red'] = st

    # 5. juicing + pinnacle
    st = {'goal': 'Juice maps for more loot and kill pinnacle bosses.', 'checks': [], 'pages': ['lab', 'farm']}
    st['checks'].append(_chk('DPS (one target)', '1,000,000+ for juiced maps and pinnacle bosses (200,000 entry)', dps,
                             dps is not None and dps >= 1e6, dps is not None and dps >= 5e5, source=boss_src,
                             sure='community rule of thumb'))
    st['checks'].append(_chk('Effective HP', 'about 25,000-30,000 for most juiced strategies', ehp,
                             ehp is not None and ehp >= 25000, ehp is not None and ehp >= 15000,
                             source='farming research: creator Path of Building snapshots', sure='estimate'))
    st['checks'].append(_chk('Life + energy shield', '5,000+ for harder pinnacle bosses', life_es,
                             life_es is not None and life_es >= 5000, life_es is not None and life_es >= 4000,
                             source=bl_src, sure='community heuristic'))
    st['do'] = ['Check each boss on the Build Lab (Boss readiness): it says ready, risky or not yet per boss.',
                'Juice one strategy at a time; the Maps page earnings card shows what it really makes per hour.']
    stages['endgame'] = st

    # 6. min-max
    st = {'goal': 'Close the gap to the top 1% of your ascendancy where it pays most.', 'checks': [],
          'pages': ['top1', 'lab', 'compare', 'character']}
    if b:
        try:
            from . import topcheck
            t = topcheck.check(con, b['id'])
            label = {'level': 'Level', 'dps': 'DPS', 'ehp': 'Effective HP', 'wealth': 'Gear value (div)'}
            for metric, p in (t.get('axes') or {}).items():
                mine = (t.get('yours') or {}).get(metric) if metric != 'wealth' else p.get('yours_div')
                need = p.get('top1_cutoff') if metric != 'wealth' else p.get('median_div')
                gx = p.get('gap_x')
                st['checks'].append(_chk(f"{label.get(metric, metric)} vs the top 1% of {t.get('scope')}",
                                         f'{need:,.0f}' if isinstance(need, (int, float)) else 'top 1%', mine,
                                         bool(p.get('in_top1')) or (metric == 'wealth' and need and mine and mine >= need),
                                         gx is not None and gx <= 1.25, sure='poe.ninja top 1% sample',
                                         why=(f'{gx}x to go' if gx else None)))
            if t.get('missing'):
                out['theory'].append('Top 1% numbers missing for: ' + ', '.join(t['missing']) +
                                     ' (Top 1% page: refresh the benchmarks).')
        except Exception as e:
            from . import safety
            st['checks'].append(_chk('Top 1% comparison', 'the Top 1% page', None, False,
                                     why=safety.explain(e)['error']))
    st['do'] = ['Upgrades ranked by DPS and defence per divine (Build Lab, Upgrades).',
                'Try each idea as a what-if card first: Path of Building measures it before you spend.']
    stages['minmax'] = st

    # ---- where you are ----
    now = None
    if b:
        for k in STAGES:
            cs = [c for c in stages[k]['checks'] if c['state'] != 'unknown' and c.get('gate', True)]
            if cs and any(c['state'] != 'ok' for c in cs):
                now = k
                break
        now = now or 'minmax'
    else:
        now = 'start'
    can, nxt = _farms(m, budget_div)
    for k in ('red', 'endgame'):
        stages[k]['farm_now'] = can if k == ('red' if now in ('start', 'campaign', 'early', 'red') else 'endgame') else []
    stages['red']['farm_next'] = nxt
    out['stages'] = [dict(stages[k], id=k, name=NAMES[k], state=('done' if STAGES.index(k) < STAGES.index(now) else
                                                                  'now' if k == now else 'later')) for k in STAGES]
    out['now'] = now
    out['farm'] = {'can_run_now': can, 'closest_next': nxt,
                   'note': 'Needs per strategy are estimates (rules of thumb from guides and creator Path of Building '
                           'snapshots); earnings are mid estimates for weeks 1-3 from the farming research.'}
    out['theory'].append('Thresholds are researched rules of thumb (sources on each check), not guarantees: your '
                         'build, your skill and the league change them.')
    out['note'] = ('A map with checkpoints, not a script: skip what you know, do it your way. Checks are measured '
                   'by Path of Building on your build; "not measured" means the data is missing, not that you failed.')
    return out
