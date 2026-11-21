""""I'm stuck" (Level 2 refine, session 3; the author 2026-11-21: "if someone genuinely feels stuck and wants to restart,
I want this to have sort of an emergency prepare plan").

The player says what's wrong (dying, too slow, broke, lost, start over). The build is measured by Path of Building
(poe2kit/journey.py) and compared with the numbers for the content they play; the real bottleneck comes first,
with the gap in numbers. Then three ways out, cheapest first:
  fix cheaply   the gear / passive / gem changes that close the gap, tried as Build Lab what-if cards first;
  respec        when the gap is too big for gear (the build itself is the problem);
  start over    a fresh plan sized to the currency they have (the League plan from scratch).
If the build can't be read (no Path of Building, no build, a failed import) it asks a few plain questions instead
and answers from those. Thresholds are the same researched rules of thumb as the League plan, with sources."""

from . import config

SYMPTOMS = {
    'dying': 'I keep dying',
    'damage': "I'm too slow / my damage is low",
    'broke': "I'm not making currency",
    'lost': "I don't know what to do next",
    'restart': 'I want to start over',
}
CONTENT = {'campaign': 'the campaign', 'early': 'tier 1-10 maps', 'red': 'tier 15-16 maps',
           'endgame': 'juiced maps and pinnacle bosses'}
# the numbers per content (the same researched rules of thumb as journey.py; sources there and in boss-readiness.json)
NEED = {
    'campaign': {'ele': 30, 'chaos': None, 'life_es': None, 'hit': None, 'dps': None},
    'early': {'ele': 75, 'chaos': 0, 'life_es': 3000, 'hit': 3500, 'dps': 1e5},
    'red': {'ele': 75, 'chaos': 0, 'life_es': 4000, 'hit': 5000, 'dps': 2e5},
    'endgame': {'ele': 75, 'chaos': 20, 'life_es': 5000, 'hit': 6000, 'dps': 1e6},
}
LEAGUE_DAY_RESTART = 'Starting over costs time, not your old character: keep it as a stash mule or a second build.'


def _content_from(m, stage_now):
    """What they're probably playing: given, else from level / damage."""
    lvl = (m or {}).get('level') or 0
    if lvl and lvl < 65:
        return 'campaign'
    dps = (m or {}).get('dps') or 0
    if dps >= 1e6:
        return 'endgame'
    if dps >= 2e5 or lvl >= 85:
        return 'red'
    return 'early'


def _findings(m, content):
    """Gaps between the build and the content, biggest first: [{area, what, have, need, gap, fix}]."""
    need = NEED[content]
    out = []
    r = m.get('res') or {}
    for t in ('fire', 'cold', 'lightning'):
        v = r.get(t)
        if v is not None and need['ele'] is not None and v < need['ele']:
            out.append({'area': 'defence', 'what': f'{t.title()} resistance', 'have': v, 'need': need['ele'], 'unit': '%',
                        'gap': (need['ele'] - v) / 25,
                        'fix': f'{need["ele"] - v:g}% {t} resistance short: every 1% under the cap is about 4% more '
                               f'{t} damage taken. Resistance on rings, amulet, belt, boots or gloves is the cheapest '
                               'fix; try the item as a Build Lab what-if card before buying.'})
    ch = r.get('chaos')
    if ch is not None and need['chaos'] is not None and ch < need['chaos']:
        out.append({'area': 'defence', 'what': 'Chaos resistance', 'have': ch, 'need': need['chaos'], 'unit': '%',
                    'gap': (need['chaos'] - ch) / 40,
                    'fix': 'Chaos resistance on gear, or a chaos resistance passive near your path.'})
    le = m.get('life_es')
    if le is not None and need['life_es'] and le < need['life_es']:
        out.append({'area': 'defence', 'what': 'Life + energy shield', 'have': le, 'need': need['life_es'], 'unit': '',
                    'gap': (need['life_es'] - le) / need['life_es'] * 1.5,
                    'fix': 'Life (or energy shield) on body armour, helmet, belt and rings first, then the life '
                           'passive clusters near your path. The Build Lab shows what each change adds.'})
    hits = m.get('hits') or {}
    if hits and need['hit']:
        t = min(hits, key=hits.get)
        if hits[t] < need['hit']:
            how = {'physical': 'armour or evasion, physical damage reduction', 'chaos': 'chaos resistance and more life'}.get(
                t, f'{t} resistance (and maximum {t} resistance)')
            out.append({'area': 'defence', 'what': f'Biggest {t} hit you survive', 'have': hits[t], 'need': need['hit'],
                        'unit': '', 'gap': (need['hit'] - hits[t]) / need['hit'] * 1.2,
                        'fix': f'Your weakest spot is {t} damage: {how}.'})
    dps = m.get('dps')
    if dps is not None and need['dps'] and dps < need['dps']:
        out.append({'area': 'damage', 'what': 'DPS (one target)', 'have': dps, 'need': need['dps'], 'unit': '',
                    'gap': min(3.0, need['dps'] / max(dps, 1) - 1),
                    'fix': 'Build Lab, Upgrades: every affordable unique tried in each slot, ranked by DPS per divine. '
                           'Also check the right skill is the one measured (Character page, Build check), and your '
                           'gem levels and supports (ask the Oracle to test supports at your level).'})
    out.sort(key=lambda f: -f['gap'])
    return out


def rescue(con, symptom, build_id=None, budget_div=None, content=None, level=None, scratch=False):
    """symptom: one of SYMPTOMS. Returns the diagnosis and three ways out."""
    from . import journey
    symptom = symptom if symptom in SYMPTOMS else 'lost'
    try:
        budget_div = float(budget_div) if budget_div not in (None, '') else None
    except (TypeError, ValueError):
        budget_div = None
    p = journey.plan(con, build_id, budget_div=budget_div, scratch=scratch)
    m = p.get('measured')
    if m is None and level:
        try:
            m = {'level': int(level)}
        except (TypeError, ValueError):
            m = None
    content = content if content in CONTENT else _content_from(m, p.get('now'))
    out = {'symptom': symptom, 'symptom_text': SYMPTOMS[symptom], 'content': content, 'content_text': CONTENT[content],
           'build': p.get('build'), 'measured': bool(p.get('measured')), 'budget_div': budget_div,
           'experience': config.experience()}
    if not p.get('measured'):
        out['questions'] = [
            {'id': 'content', 'ask': 'Where are you playing?', 'options': CONTENT},
            {'id': 'level', 'ask': 'Your character level?'},
            {'id': 'budget', 'ask': 'About how many Divine Orbs could you spend?'},
        ]
        out['not_measured'] = p.get('not_measured') or 'Your build could not be read.'
    f = _findings(p['measured'], content) if p.get('measured') else []
    if symptom == 'dying':
        f.sort(key=lambda x: (x['area'] != 'defence', -x['gap']))
    elif symptom == 'damage':
        f.sort(key=lambda x: (x['area'] != 'damage', -x['gap']))
    out['findings'] = f
    big_dps_gap = any(x['area'] == 'damage' and x['gap'] >= 3 for x in f)
    many_def = sum(1 for x in f if x['area'] == 'defence' and x['gap'] >= 0.5) >= 3

    # what they can farm now (for "broke"), from the plan
    farm = p.get('farm') or {}
    can, nxt = farm.get('can_run_now') or [], farm.get('closest_next') or []

    # ---- what the numbers say about the symptom itself ----
    area = {'dying': 'defence', 'damage': 'damage'}.get(symptom)
    out['reassure'] = None
    if p.get('measured') and area and not any(x['area'] == area for x in f):
        if area == 'damage':
            d = p['measured'].get('dps')
            out['reassure'] = (f"Your single-target damage measures fine for {CONTENT[content]} ({d:,.0f} vs about "
                               f"{NEED[content]['dps']:,.0f}). If maps feel slow, it is usually clear speed: area of "
                               'effect, movement speed, or a second skill for packs, not boss damage.')
        else:
            out['reassure'] = (f'Your defences measure fine for {CONTENT[content]}. Deaths then usually come from '
                               'specific map modifiers or ground effects: the Maps page marks the modifiers that are '
                               'deadly for your build, and Sessions shows where you died.')

    # ---- three ways out ----
    fix = [{'text': x['fix'], 'page': 'lab'} for x in f[:3]]
    if symptom == 'damage' and not any(x['area'] == 'damage' for x in f):
        fix.insert(0, {'text': 'For clear speed: try an area skill or more area of effect as Build Lab cards; the '
                               'Upgrades list also ranks items by damage per divine.', 'page': 'lab'})
    if symptom == 'dying' and not any(x['area'] == 'defence' for x in f):
        fix.insert(0, {'text': 'Check which waystone modifiers are deadly for your build before running a map '
                               '(Maps page), and where you died (Sessions).', 'page': 'maps'})
    if symptom == 'broke':
        fix = []
    if symptom == 'broke' or not fix:
        if can:
            fix.append({'text': 'Farm what your build can already run, best first: ' + ', '.join(
                f"{c['name']}" + (f" (about {c['div_per_hour_mid']} div/h)" if c.get('div_per_hour_mid') else '')
                for c in can[:3]) + '.', 'page': 'farm'})
        fix.append({'text': 'Sell what is rising and keep what usually climbs (the Oracle on the Economy page); '
                            'Exchange gaps there show the same item cheaper in one currency than another.',
                    'page': 'economy'})
        fix.append({'text': 'Price-check your loot with the overlay before vendoring it: rares with good rolls '
                            'sell.', 'page': 'status'})
        if symptom == 'broke':   # surviving harder content earns more: the build gaps come after the money moves
            fix += [{'text': f"Then close your biggest gap so harder (better paying) maps are safe: {x['what']} "
                             f"{x['have']:,.0f}{x['unit']} -> {x['need']:,.0f}{x['unit']}.", 'page': 'journey'}
                    for x in f[:2]]
    if symptom == 'lost' or not fix:
        now = next((s for s in p['stages'] if s['state'] == 'now'), None)
        if now:
            fix += [{'text': f"Your next checkpoint is {now['name']}: {d}", 'page': 'journey'} for d in now.get('do') or []][:3]
    respec = []
    if big_dps_gap or many_def or symptom == 'restart':
        respec = [
            {'text': 'When the gap is too big for gear, the build is usually the problem: compare your skill and '
                     'tree with the top 1% of your ascendancy (Top 1% page).', 'page': 'top1'},
            {'text': 'Try another main skill or a known build as Build Lab cards first: Path of Building measures it '
                     'before you spend anything.', 'page': 'lab'},
            {'text': 'Respeccing passives costs gold in town (more at higher levels); your gear and gems mostly '
                     'carry over if you stay in the same ascendancy.', 'page': None},
        ]
    restart = [
        {'text': 'A fresh plan for any class (League plan, "from scratch"): the stages, what each needs, how to pick '
                 'a build.', 'page': 'journey'},
        {'text': 'Pick the class and ascendancy chain on the League start page: skills by level, campaign rewards, '
                 'cheap levelling uniques' + (f' (you have about {budget_div:g} div)' if budget_div else '') + '.',
         'page': 'league'},
        {'text': 'Campaign: the route and every permanent reward (Campaign pages), with the in-game route panel.',
         'page': 'campaign'},
        {'text': LEAGUE_DAY_RESTART, 'page': None},
    ]
    if budget_div is not None and budget_div < 5:
        restart.insert(1, {'text': 'With under 5 div, pick a build whose levelling uniques are cheap and that '
                                   'farms plain maps or essences well; the farming list shows what needs no '
                                   'investment.', 'page': 'farm'})
    out['ways_out'] = {'fix': fix[:5], 'respec': respec, 'restart': restart}
    out['recommend'] = ('restart' if symptom == 'restart' else 'respec' if (big_dps_gap and many_def) else 'fix')
    out['farm_next'] = nxt[:3]
    out['note'] = ('Numbers are rules of thumb from guides and player reports (sources on the League plan), measured '
                   'on your build by Path of Building. You decide: this only shows where the gaps are and the '
                   'cheapest ways out.')
    return out
