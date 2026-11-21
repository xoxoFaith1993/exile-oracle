"""The Compare page: two builds side by side, visually (the author, 2026-11-21: "a comparison page that can be fed by the
oracle, more visual than just stats in a table").

compare_view(a, b) pairs two Character-page payloads (poe2kit.character) and Path of Building's key stats
(lab.defence) into what the page draws: a shape (radar) on 8 axes, bars per stat with the difference, biggest hit per
damage type, the two passive trees overlaid, gear slot by slot, skills, and the three biggest gaps in plain words.
A = "you" (or the first build), B = the one you compare against. The Oracle can push a comparison here with notes
(poe2_compare show=true); the page shows the last one pushed until the player picks another."""

import json
import math

from . import db

# (key in PoB key stats, label, higher is better, how to show)
STATS = [('DPS (combined)', 'Damage per second', True, 'big'), ('effective HP', 'Effective health pool', True, 'big'),
         ('life', 'Life', True, 'int'), ('energy shield', 'Energy shield', True, 'int'), ('mana', 'Mana', True, 'int'),
         ('spirit', 'Spirit', True, 'int'), ('armour', 'Armour', True, 'int'), ('evasion', 'Evasion', True, 'int'),
         ('fire res', 'Fire resistance', True, 'pct'), ('cold res', 'Cold resistance', True, 'pct'),
         ('lightning res', 'Lightning resistance', True, 'pct'), ('chaos res', 'Chaos resistance', True, 'pct'),
         ('casts/attacks per sec', 'Casts / attacks per second', True, 'dec'),
         ('crit chance %', 'Critical hit chance', True, 'pct'), ('movement speed x', 'Movement speed', True, 'mult')]
HITS = ('physical', 'fire', 'cold', 'lightning', 'chaos')


def _stats(con, bid):
    from . import lab
    try:
        return lab.defence(con, bid)['stats']
    except Exception:
        return {}


def _radar(sa, sb):
    """8 axes, each value as a share of the larger of the two (1.0 = the better one)."""
    def ele(s):
        r = [s.get(f'{x} res') for x in ('fire', 'cold', 'lightning')]
        r = [v for v in r if v is not None]
        return sum(r) / len(r) if r else None

    def low_hit(s):
        h = [s.get(f'max hit: {t}') for t in HITS]
        h = [v for v in h if v]
        return min(h) if h else None
    axes = [('Damage', lambda s: s.get('DPS (combined)') or s.get('DPS (main skill)')),
            ('Toughness (EHP)', lambda s: s.get('effective HP')),
            ('Life + ES', lambda s: (s.get('life') or 0) + (s.get('energy shield') or 0) or None),
            ('Weakest hit taken', low_hit), ('Elemental res', ele),
            ('Chaos res', lambda s: (s.get('chaos res') or 0) + 100 if s.get('chaos res') is not None else None),
            ('Speed', lambda s: s.get('casts/attacks per sec')), ('Movement', lambda s: s.get('movement speed x'))]
    out = []
    for name, f in axes:
        a, b = f(sa), f(sb)
        top = max(x for x in (a, b, 0) if x is not None) or 1
        # log scale: the better one sits on the rim; each of 3 rings in = 10x less (a 190x gap stays readable)
        sc = lambda v: max(0.04, 1 + math.log10(v / top) / 3) if v and v > 0 else 0.04
        out.append({'axis': name, 'a': sc(a), 'b': sc(b), 'a_raw': a, 'b_raw': b})
    return out


def _bars(sa, sb):
    rows = []
    for key, label, up, fmt in STATS:
        a, b = sa.get(key), sb.get(key)
        if a is None and b is None:
            continue
        pct = round(((b or 0) / a - 1) * 100) if a else None
        rows.append({'label': label, 'a': a, 'b': b, 'fmt': fmt, 'pct': pct,
                     'better': None if a == b else ('b' if ((b or 0) > (a or 0)) == up else 'a')})
    return rows


def _gaps(sa, sb, na, nb):
    """The three biggest ways B is ahead of A, in plain words."""
    gaps = []

    def add(score, text, area):
        gaps.append({'score': score, 'text': text, 'area': area})
    da, db_ = sa.get('DPS (combined)') or 0, sb.get('DPS (combined)') or 0
    if da and db_ > da * 1.1:
        add(db_ / da, f"{nb} does {db_ / da:.1f}× your damage ({db_:,.0f} vs {da:,.0f} DPS)", 'damage')
    ea, eb = sa.get('effective HP') or 0, sb.get('effective HP') or 0
    if ea and eb > ea * 1.1:
        add(eb / ea, f"{nb} is {eb / ea:.1f}× tougher ({eb:,.0f} vs {ea:,.0f} effective health)", 'toughness')
    for t in HITS:
        ha, hb = sa.get(f'max hit: {t}') or 0, sb.get(f'max hit: {t}') or 0
        if ha and hb > ha * 1.3:
            add(hb / ha, f"{nb} survives {hb / ha:.1f}× bigger {t} hits ({hb:,.0f} vs {ha:,.0f})", f'{t} hits')
    for x in ('fire', 'cold', 'lightning'):
        ra, rb = sa.get(f'{x} res'), sb.get(f'{x} res')
        if ra is not None and rb is not None and ra < 75 <= rb:
            add(1.5 + (75 - ra) / 50, f"your {x} resistance is {ra:g}% (uncapped); {nb} has {rb:g}%", f'{x} res')
    gaps.sort(key=lambda g: -g['score'])
    if not gaps:
        return [{'text': f'{na} is ahead of or level with {nb} on every main number.', 'area': None}]
    return [{'text': g['text'], 'area': g['area']} for g in gaps[:3]]


def _gear(ca, cb):
    def by_slot(c):
        vals = (c.get('value') or {}).get('slots') or {}
        out = {}
        for g in c.get('gear') or []:
            s = g.get('slot') or '?'
            v = vals.get(s) or {}
            out[s] = {'name': g.get('name'), 'base': g.get('base'), 'rarity': g.get('rarity'), 'art': g.get('art'),
                      'icon': g.get('icon'), 'value_div': v.get('value_div')}
        return out
    a, b = by_slot(ca), by_slot(cb)
    order = ['Weapon 1', 'Weapon 2', 'Helmet', 'Body Armour', 'Gloves', 'Boots', 'Belt', 'Amulet', 'Ring 1', 'Ring 2',
             'Flask 1', 'Flask 2', 'Charm 1', 'Charm 2', 'Charm 3']
    slots = [s for s in order if s in a or s in b] + sorted(s for s in set(a) | set(b) if s not in order and 'Swap' not in s)
    return [{'slot': s, 'a': a.get(s), 'b': b.get(s), 'same': (a.get(s) or {}).get('name') == (b.get(s) or {}).get('name')}
            for s in slots]


def _skills(c):
    out = []
    for g in c.get('skills') or []:
        gems = [x for x in g.get('gems') or [] if x.get('enabled', True)]
        act = [x['name'] for x in gems if not x.get('support')]
        if act:
            out.append({'skills': act, 'supports': [x['name'] for x in gems if x.get('support')]})
    return out


def compare_view(con, a_id, b_id):
    from . import character
    ca, cb = character.character(con, int(a_id)), character.character(con, int(b_id))
    sa, sb = _stats(con, a_id), _stats(con, b_id)
    short = lambda c, i: (c.get('label') or f'#{i}').split(' (')[0].split(' - ')[0]
    na, nb = short(ca, a_id), short(cb, b_id)
    ta, tb = set(ca['tree']['allocated']), set(cb['tree']['allocated'])
    sk_a, sk_b = _skills(ca), _skills(cb)
    names_a = {s for g in sk_a for s in g['skills'] + g['supports']}
    names_b = {s for g in sk_b for s in g['skills'] + g['supports']}
    head = lambda c, s: {'id': c['id'], 'label': c.get('label'), 'class': c.get('class'), 'ascendancy': c.get('ascendancy'),
                         'level': c.get('level'), 'main_skill': c.get('main_skill'), 'owner': c.get('owner'),
                         'value_div': (c.get('value') or {}).get('total_div'), 'dps': s.get('DPS (combined)')}
    return {'a': head(ca, sa), 'b': head(cb, sb), 'radar': _radar(sa, sb), 'bars': _bars(sa, sb),
            'hits': [{'type': t, 'a': sa.get(f'max hit: {t}'), 'b': sb.get(f'max hit: {t}')} for t in HITS],
            'gaps': _gaps(sa, sb, 'You' if ca.get('owner') == 'me' else na, nb),
            'tree': {'version': ca['tree']['version'], 'same_version': ca['tree']['version'] == cb['tree']['version'],
                     'only_a': sorted(ta - tb), 'only_b': sorted(tb - ta), 'both': sorted(ta & tb)},
            'keystones': {'a': [k['name'] for k in ca.get('keystones') or []], 'b': [k['name'] for k in cb.get('keystones') or []]},
            'gear': _gear(ca, cb),
            'skills': {'a': sk_a, 'b': sk_b, 'only_a': sorted(names_a - names_b), 'only_b': sorted(names_b - names_a)},
            'pushed': pushed(con) if pushed(con).get('a') == int(a_id) and pushed(con).get('b') == int(b_id) else None}


def push(con, a_id, b_id, note=None):
    """The Oracle puts a comparison on the Compare page (with its own notes)."""
    db.kv_set(con, 'compare:last', json.dumps({'a': int(a_id), 'b': int(b_id), 'note': (note or '')[:2000]}))
    con.commit()


def pushed(con):
    try:
        return json.loads(db.kv_get(con, 'compare:last') or '{}')
    except ValueError:
        return {}
