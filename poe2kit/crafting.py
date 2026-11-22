"""Crafting Lab v1: mod pools from game data, target-item analysis and a step-by-step route with live costs.

Facts used (sources in PLAN.md module 12):
- What each currency / omen / bone does: the game's own description text (CurrencyItems table).
- Greater/Perfect minimum modifier levels (server-side, so from poe2wiki + community): Transmutation and
  Augmentation 55/70; Exalted and Chaos 35/50; Regal assumed 35/50 (unconfirmed). The floor is not absolute:
  a mod type with no tier at or above the floor can still roll its best tier.
- Essence mods: the game's EssenceMods table (essence -> item category -> exact mod).
- Mod tiers, item levels, prefix/suffix, groups: game data (RePoE export of this build).

NOT in the client: real spawn weights. Chances below assume every eligible mod family is equally likely and
every eligible tier equally likely. Real top tiers are rarer, so treat chances as optimistic and check exact
odds for a final plan in Craft of Exile (they estimate weights from experiments)."""

import glob
import json
import os
import re

from . import config, db, gamedata, money, ninja

GAMEFILES = config.GAMEFILES_DIR
COE = 'https://www.craftofexile.com/?game=poe2'
MIN_LEVEL = {
    'Exalted Orb': 0, 'Greater Exalted Orb': 35, 'Perfect Exalted Orb': 50,
    'Chaos Orb': 0, 'Greater Chaos Orb': 35, 'Perfect Chaos Orb': 50,
    'Regal Orb': 0, 'Greater Regal Orb': 35, 'Perfect Regal Orb': 50,
    'Orb of Transmutation': 0, 'Greater Orb of Transmutation': 55, 'Perfect Orb of Transmutation': 70,
    'Orb of Augmentation': 0, 'Greater Orb of Augmentation': 55, 'Perfect Orb of Augmentation': 70,
}
SIDE_OMEN = {'prefix': ('Omen of Sinistral Exaltation', 'Omen of Sinistral Annulment', 'Omen of Sinistral Erasure',
                        'Omen of Sinistral Necromancy', 'Omen of Sinistral Crystallisation'),
             'suffix': ('Omen of Dextral Exaltation', 'Omen of Dextral Annulment', 'Omen of Dextral Erasure',
                        'Omen of Dextral Necromancy', 'Omen of Dextral Crystallisation')}
DESEC_FAMILY_OMEN = {'Ulaman': 'Omen of the Sovereign', 'Amanamu': 'Omen of the Liege', 'Kurgal': 'Omen of the Blackblooded'}
_cache = {}


# ---------------- data ----------------

def _tables_dir():
    dirs = sorted(glob.glob(os.path.join(GAMEFILES, '*', 'tables')), key=os.path.getmtime)
    return dirs[-1] if dirs else None


def _t(name):
    key = 't:' + name
    if key not in _cache:
        with open(os.path.join(_tables_dir(), name + '.json'), encoding='utf-8') as f:
            _cache[key] = json.load(f)
    return _cache[key]


def effects():
    """{name: game description} for crafting currencies, omens, essences, bones."""
    if 'effects' not in _cache:
        p = config.data_file('currency_effects.json')
        with open(p, encoding='utf-8') as f:
            _cache['effects'] = {e['name']: re.sub(r'\[[^\]|]*\|([^\]]*)\]', r'\1', e['desc']).replace('[', '').replace(']', '')
                                 for e in json.load(f)}
    return _cache['effects']


def essence_map():
    """mod id -> [(essence name, [item class ids])] from the game's EssenceMods table."""
    if 'ess' not in _cache and not _tables_dir():   # fresh install: the shipped data pack
        p = config.data_file('essence_map.json')
        _cache['ess'] = {k: [tuple(x) for x in v] for k, v in json.load(open(p, encoding='utf-8')).items()} if p else {}
    if 'ess' not in _cache:
        bit, mods, ess = _t('baseitemtypes'), _t('mods'), _t('essences')
        cats, em, ic = _t('essencetargetitemcategories'), _t('essencemods'), _t('itemclasses')
        out = {}
        for r in em:
            try:
                e = ess[r['Essence']]
                name = bit[e['BaseItemType']]['Name']
                mid = mods[r['Mod']]['Id']
                classes = [ic[i]['Id'] for i in cats[r['TargetItemCategory']]['ItemClasses']]
            except (IndexError, KeyError, TypeError):
                continue
            out.setdefault(mid, []).append((name, classes))
        _cache['ess'] = out
    return _cache['ess']


def prices(con, league=None):
    league = league or ninja.current_league(con)
    key = 'p:' + league
    if key not in _cache:
        rows = con.execute(
            """SELECT p.name, p.value FROM price p JOIN (SELECT item_key, category, MAX(ts) m FROM price WHERE league=?
               AND source='ninja-exchange' GROUP BY item_key, category) x ON p.item_key=x.item_key AND
               p.category=x.category AND p.ts=x.m WHERE p.league=?""", (league, league)).fetchall()
        _cache[key] = {r['name']: r['value'] for r in rows}
    return _cache[key]


# ---------------- mod pool ----------------

def _clean(t):
    return re.sub(r'\[([^\]|]*)\|([^\]]*)\]', r'\2', re.sub(r'\[([^\]|]*)\]', r'\1', t or ''))


def pool(base, ilvl=82):
    """Every prefix/suffix family this base can roll at this item level, tiers best-first."""
    b = gamedata.base_info(base)
    if not b:
        raise ValueError(f'unknown base type {base!r}')
    tags = b['tags']
    fams = {}
    for mid, m in gamedata.load('mods').items():
        if m.get('domain') not in ('item', 'misc') or m.get('generation_type') not in ('prefix', 'suffix'):
            continue
        if m.get('is_essence_only') or not m.get('text'):
            continue
        if not gamedata._spawns_on({'weights': m.get('spawn_weights', [])}, tags):
            continue
        key = (m['generation_type'], tuple(m.get('groups', [])), re.sub(r'\d+', '#', _clean(m['text'])))
        fams.setdefault(key, []).append({'id': mid, 'name': m.get('name'), 'level': m.get('required_level', 1),
                                         'text': _clean(m['text'])})
    out = []
    for (gen, groups, tmpl), tiers in fams.items():
        tiers.sort(key=lambda t: -t['level'])
        for i, t in enumerate(tiers):
            t['tier'] = i + 1
        avail = [t for t in tiers if t['level'] <= ilvl]
        if avail:
            out.append({'side': gen, 'groups': list(groups), 'template': tmpl, 'tiers': tiers, 'available': avail})
    return {'base': base, 'class': b['class'], 'ilvl': ilvl, 'families': out,
            'prefix_families': sum(1 for f in out if f['side'] == 'prefix'),
            'suffix_families': sum(1 for f in out if f['side'] == 'suffix')}


def _hit_chance(fams_side, fam, tier_needed, min_level):
    """Rough chance one Exalt (with a side omen) lands this family at tier <= tier_needed (T1 best)."""
    eligible = []
    for f in fams_side:
        ok = [t for t in f['available'] if t['level'] >= min_level] or f['available'][:1]  # floor isn't absolute
        eligible.append((f, ok))
    total = len(eligible)
    for f, ok in eligible:
        if f is fam:
            good = [t for t in ok if t['tier'] <= tier_needed]
            return (1 / total) * (len(good) / len(ok)) if ok and total else 0.0
    return 0.0


# ---------------- analysis + route ----------------

def analyze(con, base, mods, ilvl=None, league=None):
    """mods: explicit mod lines of the target item. Returns per-mod source, tier and rough odds, plus a route."""
    league = league or ninja.current_league(con)
    b = gamedata.base_info(base)
    if not b:
        raise ValueError(f'unknown base type {base!r}')
    tags = b['tags']
    read = [gamedata.read_mod(m, tags) or {'text': m, 'mod': None} for m in mods]
    need_ilvl = max([r.get('ilvl_needed') or 1 for r in read if r.get('mod')] + [1])
    ilvl = max(ilvl or 0, need_ilvl)
    pl = pool(base, ilvl)
    fams = pl['families']
    by_side = {'prefix': [f for f in fams if f['side'] == 'prefix'], 'suffix': [f for f in fams if f['side'] == 'suffix']}
    ess = essence_map()
    allmods = gamedata.load('mods')
    pr = prices(con, league)
    rt = money.rates(con, league)
    rows = []
    for line, r in zip(mods, read):
        row = {'text': line}
        if r.get('mod'):
            # find the family + tier this line belongs to
            fam = next((f for f in fams if any(t['name'] == r['mod'] and abs(t['level'] - r['ilvl_needed']) < 1 for t in f['tiers'])), None)
            row.update(side=r['gen'], tier=r['tier'], tiers=r['tiers'], level=r['ilvl_needed'], roll_pct=r['roll_pct'],
                       source='normal')
            if fam:
                row['family'] = fam['template']
                row['chances'] = {}
                for orb in ('Exalted Orb', 'Greater Exalted Orb', 'Perfect Exalted Orb'):
                    p = _hit_chance(by_side[fam['side']], fam, r['tier'], MIN_LEVEL[orb])
                    omen = SIDE_OMEN[fam['side']][0]
                    each = (pr.get(orb) or 0) + (pr.get(omen) or 0)
                    row['chances'][orb] = {'chance': round(p, 4), 'one_in': round(1 / p) if p else None,
                                           'cost_per_try_div': round(each, 3),
                                           'expected_cost_div': round(each / p, 2) if p else None}
                best = min((v for v in row['chances'].values() if v['expected_cost_div']), key=lambda v: v['expected_cost_div'],
                           default=None)
                row['best_orb'] = next((k for k, v in row['chances'].items() if v is best), None)
        else:
            # essence-only / desecrated / other
            tmpl = re.sub(r'\d+(?:\.\d+)?', '#', line).lower()
            hit = None
            for mid, m in allmods.items():
                if not m.get('text'):
                    continue
                if re.sub(r'\(?-?\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?\))?', '#', _clean(m['text'])).lower() == tmpl:
                    if m.get('is_essence_only') or m.get('domain') == 'desecrated':
                        hit = (mid, m)
                        break
            if hit and hit[1].get('domain') == 'desecrated':
                fam = next((k for k in DESEC_FAMILY_OMEN if k in (hit[1].get('name') or '')), None)
                row.update(source='desecrated', side=hit[1]['generation_type'], family=fam,
                           omen=DESEC_FAMILY_OMEN.get(fam))
            elif hit:
                row.update(source='essence', side=hit[1]['generation_type'],
                           essences=[e for e, cls in ess.get(hit[0], []) if b['class'] in cls] or [e for e, _ in ess.get(hit[0], [])])
            else:
                row.update(source='unknown', note='not a normal roll: probably a rune/augment, corruption, crafted '
                                                  'or a combined (hybrid) value')
        rows.append(row)

    steps, total = [], 0.0

    def cost(name, n=1):
        v = pr.get(name)
        return (v or 0) * n

    def step(title, items, note=None, exp=None):
        nonlocal total
        c = exp if exp is not None else sum(cost(i) for i in items)
        total += c
        steps.append({'step': len(steps) + 1, 'do': title, 'uses': items, 'expected_cost_div': round(c, 2),
                      'expected_cost': money.fmt(c, rt), 'note': note})

    step(f'Get a {base} with item level {ilvl}+ (top tiers here need item level {need_ilvl}).', [],
         'Buy a normal or magic base on the trade site, or use one you found.')
    for r in [r for r in rows if r['source'] == 'essence']:
        e = (r.get('essences') or ['?'])[0]
        step(f"Essence step: {e} guarantees “{r['text']}”.", [e],
             'On a magic item it upgrades to rare with this mod; a Perfect Essence on a rare removes a mod and adds it '
             '(Omen of Sinistral/Dextral Crystallisation picks which side is removed).')
    normal = sorted([r for r in rows if r['source'] == 'normal' and r.get('best_orb')],
                    key=lambda r: r['chances'][r['best_orb']]['chance'])
    if not any(r['source'] == 'essence' for r in rows) and normal:
        first = normal[0]
        coron = 'Omen of Sinistral Coronation' if first['side'] == 'prefix' else 'Omen of Dextral Coronation'
        step('Make it rare with a clean start: Orb of Transmutation (Greater/Perfect for higher-level mods), '
             f'Orb of Augmentation, then Regal Orb + {coron} so the 3rd mod lands on the side you need most.',
             ['Orb of Transmutation', 'Orb of Augmentation', 'Regal Orb', coron],
             'Keep the base if the first mods are useful; otherwise start over on a new base (cheaper than fixing it).')
    for r in normal:
        c = r['chances'][r['best_orb']]
        omen = SIDE_OMEN[r['side']][0]
        step(f"{r['side'].title()}: “{r['text']}” (T{r['tier']}) with {r['best_orb']} + {omen}.",
             [r['best_orb'], omen],
             f"≈1 in {c['one_in']} per try (rough). Misses: remove them with Orb of Annulment + "
             f"{SIDE_OMEN[r['side']][1]} (removes a random {r['side']}, so lock good mods first).",
             exp=c['expected_cost_div'])
    for r in [r for r in rows if r['source'] == 'normal' and not r.get('best_orb')]:
        omen = SIDE_OMEN.get(r.get('side') or 'prefix', SIDE_OMEN['prefix'])[0]
        step(f"{(r.get('side') or 'mod').title()}: “{r['text']}” (T{r.get('tier')}) with Exalted Orbs + {omen}.",
             ['Exalted Orb', omen], 'Odds unknown for this one (its tier family could not be matched); budget extra tries.')
    if len(normal) >= 3:
        step('Lock your hardest mod: Fracturing Orb (needs 4+ mods; fractures a random one, so do it when the mod '
             'you want locked is the best odds).', ['Fracturing Orb'],
             'Optional. Hinekora’s Lock lets you preview the result of the next currency first (very expensive).')
    for r in [r for r in rows if r['source'] == 'desecrated']:
        bone = ('Ancient Jawbone' if any(t in gamedata.base_info(base)['tags'] for t in ('weapon', 'quiver')) else
                'Ancient Collarbone' if any(t in gamedata.base_info(base)['tags'] for t in ('ring', 'amulet', 'belt')) else
                'Ancient Rib')
        if r.get('side') not in SIDE_OMEN:   # e.g. 'unique'-generation mods (special jewels): not craftable
            r['source'] = 'special'
            continue
        items = [bone, SIDE_OMEN[r['side']][3]] + ([r['omen']] if r.get('omen') else [])
        odds, exp = None, None
        try:   # the real bone for this class, a lineage omen when it helps, and the odds (poe2kit/desecration.py)
            import re as _re
            from . import desecration as _d, craftsim as _cs
            pool_ = _cs.get_pool(base, ilvl)
            norm = lambda s: _re.sub(r'\(?[\d.]+(-[\d.]+)?\)?', '#', s or '').lower()
            xm = next((m for m in _d.exclusive(pool_['class'], r['side']) if norm(m['text']) == norm(r['text'])), None)
            ok = [b for b in _d.bones_for(pool_['class'], ilvl) if b['ok'] and b['exclusive_option_chance']]
            if xm and ok:
                bb = min(ok, key=lambda b: pr.get(b['name']) or 9e9)
                lo = next((k for k, v in _d.LINEAGE_OMEN.items() if v == xm.get('lineage')), None) \
                    if bb['lineage_omens'] else None
                items = [bb['name'], _d.SIDE_OMEN[r['side']]] + ([lo] if lo else []) + [_d.ECHOES]
                p = _d.p_offer({'base': base, 'ilvl': ilvl, 'rarity': 'rare', 'mods': []}, pool_,
                               {'xid': xm['id'], 'side': r['side']}, _d.bone(bb['name']), True, xm.get('lineage') if lo else None)
                c = sum(pr.get(i) or 0 for i in items)
                odds = f'about {p * 100:.0f}% per try' if p else None
                exp = round(c / p, 2) if p and c else None
                bone = bb['name']
        except Exception:
            pass
        step(f"Desecrated mod “{r['text']}”: {' + '.join(items)}, then reveal it at the Well of Souls and pick it from "
             f"the 3 options (Abyssal Echoes rerolls them once). A miss: Orb of Annulment + Omen of Light removes only "
             f"the desecrated mod, then try again.", items,
             (f'{odds} (rough: our reading of the game data, every mod counted the same).' if odds else
              'Odds unknown for this one; budget extra tries.'), exp=exp)
    if any(r.get('roll_pct', 100) < 100 for r in rows if r['source'] == 'normal'):
        step('Finish: Divine Orbs to push the rolls up (rerolls all values).', ['Divine Orb'],
             'Optional and repeatable; Omen of Sanctification makes the next Divine sanctify the item instead.')
    return {
        'base': base, 'item_level': ilvl, 'class': b['class'], 'league': league,
        'pool_size': {'prefix_families': pl['prefix_families'], 'suffix_families': pl['suffix_families']},
        'mods': rows, 'route': steps, 'expected_total_div': round(total, 1), 'expected_total': money.fmt(total, rt),
        'warnings': ['Chances assume equal weights (the game files don’t contain real weights); top tiers are rarer '
                     'in reality, so treat costs as a floor. Check exact odds in Craft of Exile before spending big.',
                     'Annulment / Chaos remove a RANDOM mod of the chosen side: protect good mods (fracture) first.'],
        'craft_of_exile': COE,
    }


_EFFECT = re.compile(r'(\d+(?:\.\d+)?)% increased Effect of (Prefixes|Suffixes)', re.I)
_EST_CACHE = {}


def estimate_rare(con, base, mods, ilvl=None, league=None):
    """A price estimate for a rare nobody publishes prices for: the expected currency to craft one like it.
    Special crafted mods ("increased Effect of Suffixes/Prefixes", which boost the other side's values beyond normal
    tiers) are taken off first: the other side's numbers are scaled back to normal rolls, and the special mod is
    flagged as not priced, so the result is a floor for those items."""
    key = (base, tuple(mods), ilvl, league)
    if key in _EST_CACHE:
        return _EST_CACHE[key]
    special, clean, boost = [], [], {}
    for m in mods:
        e = _EFFECT.search(m)
        if e:
            boost['suffix' if e.group(2).lower() == 'suffixes' else 'prefix'] = float(e.group(1)) / 100
            special.append(m)
        else:
            clean.append(m)
    out = None
    try:
        if boost:
            # read once to know each line's side, then scale the boosted side back to its natural roll
            b = gamedata.base_info(base) or {}
            fixed = []
            for m in clean:
                tmpl = re.sub(r'\d+(?:\.\d+)?', '#', m)
                side = None
                for f in pool(base, ilvl or 82)['families']:
                    if re.sub(r'\(?-?\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?\))?', '#', f['template']) == tmpl:
                        side = f['side']
                        break
                k = boost.get(side) or (boost.get('suffix') if side is None and 'suffix' in boost else None)
                fixed.append(re.sub(r'\d+(?:\.\d+)?', lambda x: str(round(float(x.group()) / (1 + k))), m) if k else m)
            clean = fixed
        r = analyze(con, base, clean, ilvl, league)
        unknown = [x['text'] for x in r['mods'] if x.get('source') in ('unknown', 'special')]
        out = {'est_div': r['expected_total_div'], 'est': r['expected_total'], 'special': special,
               'not_counted': unknown,
               'kind': 'floor' if (special or unknown) else 'craft cost',
               'note': ('≈ craft cost of the normal mods' + (' + special mod(s) not priced: ' + '; '.join(special)
                                                             if special else '') +
                        (f'; {len(unknown)} mod(s) could not be matched' if unknown else ''))}
    except Exception as ex:
        out = {'est_div': None, 'error': str(ex)}
    _EST_CACHE[key] = out
    return out


def from_item_text(con, text, league=None):
    """Plan from Ctrl+C / PoB item text."""
    from .character import _item
    it = _item(text)
    if it['rarity'] != 'RARE':
        raise ValueError('paste a rare item (uniques can’t be crafted)')
    ilvl = int(re.sub(r'\D', '', it['item_level'] or '') or 0) or None
    return analyze(con, it['base'], [m['t'] for m in it['explicits']], ilvl, league)


def from_build(con, build_id, slot, league=None):
    from . import character
    c = character.character(con, int(build_id))
    it = next((g for g in c['gear'] + c['jewels'] if g['slot'].lower() == slot.lower()), None)
    if not it:
        raise ValueError(f'no item in slot {slot!r}; slots: ' + ', '.join(g['slot'] for g in c['gear']))
    if it['rarity'] != 'RARE':
        raise ValueError(f"{slot} is {it['rarity'].lower()}: only rares can be crafted")
    ilvl = int(re.sub(r'\D', '', it.get('item_level') or '') or 0) or None
    res = analyze(con, it['base'], [m['t'] for m in it['explicits']], ilvl, league)
    res['item'] = f"{it['name']} ({it['base']})"
    res['art'] = it.get('art')
    return res
