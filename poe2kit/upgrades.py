"""Upgrade finder: try every affordable unique in each gear slot of a build (PoB's own compare calculator,
one PoB run for the whole search) and rank by DPS and defence gained per divine.

Uniques are tested at a typical (middle) roll; prices are the latest poe.ninja estimates for the league.
Rares can't be searched this way (no market data); use poe2_whatif with a specific rare instead."""

import hashlib
import json
import os
import subprocess
import tempfile

from . import money, ninja, pob, vault

GEAR_SLOTS = ['Weapon 1', 'Weapon 2', 'Helmet', 'Body Armour', 'Gloves', 'Boots', 'Amulet', 'Ring 1', 'Ring 2',
              'Belt', 'Charm 1', 'Flask 1', 'Flask 2']
BATCH = os.path.join(os.path.dirname(pob.SCRIPT), 'pobbatch.lua')
MAXHITS = ['PhysicalMaximumHitTaken', 'FireMaximumHitTaken', 'ColdMaximumHitTaken', 'LightningMaximumHitTaken',
           'ChaosMaximumHitTaken']


def _prices(con, league, max_price, min_listings):
    """{(title, base): price_div} for uniques with enough listings to actually buy."""
    rows = con.execute(
        """SELECT p.name, p.base, p.value, p.listings FROM price p JOIN
           (SELECT item_key, MAX(ts) mts FROM price WHERE league=? AND source='ninja-item' GROUP BY item_key) m
           ON p.item_key=m.item_key AND p.ts=m.mts WHERE p.league=? AND p.source='ninja-item'""",
        (league, league)).fetchall()
    out = {}
    for r in rows:
        if r['name'].endswith('[corrupted]') or (r['listings'] or 0) < min_listings or r['value'] is None:
            continue
        if max_price is not None and r['value'] > max_price:
            continue
        title = r['name'].split(' (')[0]
        key = (title.lower(), (r['base'] or '').lower())
        out[key] = min(out.get(key, 1e9), r['value'])
    return out


def _run_batch(xml_text, slots, names, main_group):
    with open(BATCH, 'rb') as f:
        script = hashlib.sha1(f.read()).hexdigest()
    key = hashlib.sha1(json.dumps([pob.version(), script, xml_text, slots, sorted(names), main_group]).encode()).hexdigest()
    cpath = os.path.join(pob.CACHE, 'batch-' + key + '.json')
    if os.path.exists(cpath):
        with open(cpath, encoding='utf-8') as f:
            return json.load(f)
    os.makedirs(pob.CACHE, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='pobb-', dir=pob.CACHE)
    paths = {k: os.path.join(tmp, k) for k in ('in.xml', 'jobs.json', 'out.json')}
    try:
        with open(paths['in.xml'], 'w', encoding='utf-8') as f:
            f.write(xml_text)
        with open(paths['jobs.json'], 'w', encoding='utf-8') as f:
            json.dump({'main_group': main_group, 'slots': slots, 'names': names}, f)
        env = dict(os.environ, POB_RUNTIME=os.path.join(pob.POB, 'runtime'), POB_IN=paths['in.xml'],
                   POB_JOBS=paths['jobs.json'], POB_OUT=paths['out.json'], TEMP=tmp, TMP=tmp)
        p = subprocess.run([os.path.abspath(pob.HOST), os.path.join(pob.POB, 'runtime'), BATCH],
                           cwd=os.path.join(pob.POB, 'src'), env=env, capture_output=True, text=True,
                           timeout=1800, stdin=subprocess.DEVNULL)
        if p.returncode != 0 or not os.path.exists(paths['out.json']):
            raise RuntimeError('PoB batch failed: ' + ' | '.join((p.stderr or p.stdout).strip().splitlines()[-6:]))
        with open(paths['out.json'], encoding='utf-8') as f:
            res = json.load(f)
        with open(cpath, 'w', encoding='utf-8') as f:
            json.dump(res, f)
        return res
    finally:
        for fp in paths.values():
            try:
                os.remove(fp)
            except OSError:
                pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass


def _pct(new, old):
    return round((new / old - 1) * 100, 1) if old else None


def find(con, build_id=None, pob_code=None, budget_div=None, slots=None, main_group=None, league=None,
         min_listings=5, top=5):
    league = league or ninja.current_league(con)
    if build_id is not None:
        r = con.execute('SELECT label, pob_code FROM build WHERE id=?', (int(build_id),)).fetchone()
        if not r:
            raise ValueError('no such build in the vault')
        label, pob_code = r['label'], r['pob_code']
    else:
        label = 'pasted build'
    xml = vault.decode(pob_code)
    if main_group is None:  # same main skill the stats tool picks (strongest if the build's own reads 0)
        main_group = pob.calc(xml).get('main_group')
    prices = _prices(con, league, budget_div, min_listings)
    names = sorted({t for t, _ in prices})
    res = _run_batch(xml, slots or GEAR_SLOTS, names, main_group)
    base = res['base']
    bdps = base.get('CombinedDPS') or base.get('TotalDPS') or 0
    bpool = (base.get('Life') or 0) + (base.get('EnergyShield') or 0)
    bmin = min((base.get(k) for k in MAXHITS if base.get(k)), default=0)

    per_slot, everything = [], []
    for s in res['slots']:
        cands = []
        for t in s.get('tried') or []:
            if 'out' not in t:
                continue
            title, _, tbase = t['name'].partition(', ')
            price = prices.get((title.lower(), tbase.lower()))
            if price is None:  # PoB has this base but poe.ninja prices another one
                alts = [v for (n, b), v in prices.items() if n == title.lower()]
                price = min(alts) if alts else None
            if price is None or t['name'] == s.get('current'):
                continue
            o = t['out']
            dps = o.get('CombinedDPS') or o.get('TotalDPS') or 0
            pool = (o.get('Life') or 0) + (o.get('EnergyShield') or 0)
            mn = min((o.get(k) for k in MAXHITS if o.get(k)), default=0)
            uncapped = [k[:-6].lower() for k in ('FireResist', 'ColdResist', 'LightningResist')
                        if (base.get(k) or 0) >= 75 > (o.get(k) or 0)]
            blockers = [f"needs {o['Req' + a]} {a.lower()} (you'd have {round(o.get(a) or 0)})"
                        for a in ('Str', 'Dex', 'Int') if (o.get('Req' + a) or 0) > (o.get(a) or 0)]
            if (o.get('SpiritUnreserved') or 0) < 0:
                blockers.append(f"not enough spirit for your auras/buffs ({round(o['SpiritUnreserved'])} left)")
            c = {'item': t['name'], 'price_div': round(price, 2), 'req_level': t.get('req_level'),
                 'can_use': not blockers, 'blockers': blockers,
                 'dps_pct': _pct(dps, bdps), 'life_es_change': round(pool - bpool),
                 'lowest_max_hit_pct': _pct(mn, bmin), 'spirit_change': round((o.get('Spirit') or 0) - (base.get('Spirit') or 0)),
                 'loses_res_cap': uncapped}
            c['dps_pct_per_div'] = round(c['dps_pct'] / max(price, 0.05), 2) if c['dps_pct'] is not None else None
            cands.append(c)
            everything.append(dict(c, slot=s['slot'], replaces=s.get('current')))
        usable = [c for c in cands if c['can_use']]
        by_dps = sorted([c for c in usable if (c['dps_pct'] or 0) > 0], key=lambda c: -c['dps_pct'])[:top]
        by_def = sorted([c for c in usable if (c['life_es_change'] > 0 or (c['lowest_max_hit_pct'] or 0) > 0)],
                        key=lambda c: -((c['lowest_max_hit_pct'] or 0) + c['life_es_change'] / 50))[:top]
        blocked = [c for c in cands if not c['can_use']]
        kinds = {}
        for c in blocked:
            for b in c['blockers']:
                k = 'spirit' if 'spirit' in b else b.split()[2]  # 'needs 121 str (...)' -> 'str'
                kinds[k] = kinds.get(k, 0) + 1
        why = None
        if usable == [] and blocked and kinds.get('spirit', 0) == len(blocked):
            why = (f"every other item here leaves you short on spirit: {s.get('current')} is holding up your "
                   "spirit reservations (auras/buffs). Fix spirit elsewhere to open this slot up.")
        best_blocked = sorted(blocked, key=lambda c: -((c['dps_pct'] or 0) + (c['lowest_max_hit_pct'] or 0)
                                                      + c['life_es_change'] / 50))[:3]
        per_slot.append({'slot': s['slot'], 'current': s.get('current'), 'tested': len(cands),
                         'skipped_cant_use': len(blocked), 'blocked_by': kinds, 'blocked_note': why,
                         'best_if_unblocked': [{k: c[k] for k in ('item', 'price_div', 'dps_pct', 'life_es_change',
                                                                  'lowest_max_hit_pct', 'blockers')} for c in best_blocked],
                         'best_for_damage': by_dps, 'best_for_defence': by_def})
    value = sorted([c for c in everything if c['can_use'] and (c['dps_pct'] or 0) > 1],
                   key=lambda c: -(c['dps_pct_per_div'] or 0))[:10]
    big = sorted([c for c in everything if c['can_use'] and (c['dps_pct'] or 0) > 1], key=lambda c: -c['dps_pct'])[:10]
    icons = {}
    for r in con.execute("SELECT name, base, icon FROM price WHERE league=? AND source='ninja-item' AND icon IS NOT NULL", (league,)):
        icons[(r['name'].split(' (')[0].lower(), (r['base'] or '').lower())] = r['icon']
    def _icon(c):
        t, _, b = c['item'].partition(', ')
        return icons.get((t.lower(), b.lower())) or next((v for (n, _b), v in icons.items() if n == t.lower()), None)
    rt = money.rates(con, league)
    for lst in [value, big] + [s[k] for s in per_slot for k in ('best_for_damage', 'best_for_defence', 'best_if_unblocked')]:
        for c in lst:
            c['icon'] = _icon(c)
    for lst in [value, big] + [s[k] for s in per_slot for k in ('best_for_damage', 'best_for_defence', 'best_if_unblocked')]:
        money.annotate(lst, rt, key='price_div')
    return {'build': label, 'league': league, 'main_group': res.get('main_group'),
            'budget': money.fmt(budget_div, rt) if budget_div is not None else 'no limit',
            'baseline': {'dps': round(bdps), 'life+es': round(bpool), 'lowest_max_hit': round(bmin),
                         'spirit': base.get('Spirit')},
            'budget_div': budget_div, 'uniques_considered': len(names),
            'best_value_damage_upgrades': value, 'biggest_damage_upgrades': big, 'slots': per_slot,
            'notes': ['Uniques are tested at a middle roll; your own copy may roll better or worse.',
                      'Prices are poe.ninja estimates for the league (min listings %d).' % min_listings,
                      'Rares aren\'t searched (no market data); test a specific rare with poe2_whatif.',
                      'Items whose effect PoB can\'t model (e.g. Headhunter\'s stolen mods) are undervalued.',
                      'Items you can\'t equip (attributes) or that break spirit reservations are left out; see '
                      'best_if_unblocked per slot.']}
