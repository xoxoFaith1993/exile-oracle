"""Drop-rate estimates from the web (research\\drop-rates.json): only GGG knows the real rates, so everything here is
anecdotal: creator farming sessions, community boss samples, patch-note multipliers. Each tracked setup is
priced with live poe.ninja prices to estimate loot value per map (or per boss kill), always shown with its sample
size, patch and confidence so a 14-map anecdote never looks like fact."""

import json
import os
import statistics

from . import money, ninja

FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'research', 'drop-rates.json')
UNITS = ('per map', 'per boss kill')
# research mechanic -> Farming board mechanic
MECH = {'Ritual': 'Ritual', 'Abyss': 'Abyss', 'Delirium': 'Delirium', 'Breach': 'Breach', 'Expedition': 'Expedition',
        'Essences': 'Essences', 'Ultimatum': 'Soul cores (Ultimatum)', 'Runes': 'Runes', 'Idols': 'Idols',
        'Bossing': 'Bossing (fragments)', 'Verisium': 'Verisium (Runes of Aldur)', 'Base currency': 'Base currency'}
ALIAS = {'Simulacrum (300 Simulacrum Splinters)': 'Simulacrum'}
RANK = {'high': 3, 'medium': 2, 'low': 1}


def load():
    try:
        with open(FILE, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def _prices(con, league):
    rows = con.execute(
        """SELECT p.name, p.value FROM price p JOIN (SELECT item_key, category, MAX(ts) m FROM price WHERE league=?
           GROUP BY item_key, category) x ON p.item_key=x.item_key AND p.category=x.category AND p.ts=x.m
           WHERE p.league=? AND p.value > 0""", (league, league)).fetchall()
    out = {}
    for r in rows:
        out[r['name']] = min(out.get(r['name'], r['value']), r['value'])
    return out


def setups(con, league=None):
    """Mechanic -> list of tracked setups priced at today's prices, best evidence first."""
    league = league or ninja.current_league(con)
    price = _prices(con, league)
    rt = money.rates(con, league)
    groups = {}
    for e in load():
        unit = (e.get('unit') or '').lower()
        if unit not in UNITS or not (e.get('rate') or 0) > 0:
            continue
        key = (e['mechanic'], unit, e.get('source_url'), (e.get('conditions') or '')[:80], e.get('patch_or_date'))
        groups.setdefault(key, []).append(e)
    out = {}
    for (mech, unit, url, cond, patch), es in groups.items():
        items, ev, unpriced = [], 0.0, []
        for e in es:
            nm = ALIAS.get(e['item'], e['item'])
            p = price.get(nm)
            if p is None:
                unpriced.append(e['item'])
                continue
            v = e['rate'] * p
            ev += v
            items.append({'item': nm, 'rate': e['rate'], 'value_div': round(v, 4), 'price_div': round(p, 4)})
        if not items:
            continue
        conf = min(es, key=lambda e: RANK.get(e.get('confidence'), 0)).get('confidence')
        sample = next((e.get('sample_size') for e in es if e.get('sample_size')), None)
        out.setdefault(MECH.get(mech, mech), []).append({
            'unit': unit, 'value_div': round(ev, 3), 'value': money.fmt(ev, rt), 'confidence': conf,
            'sample': sample, 'patch': patch, 'conditions': cond, 'source': url,
            'current_patch': '0.5' in (patch or ''),
            'items': sorted(items, key=lambda x: -x['value_div']), 'unpriced': unpriced})
    for m, lst in out.items():
        lst.sort(key=lambda s: (-s['current_patch'], -RANK.get(s['confidence'], 0), -s['value_div']))
    return out


def best(lst, unit='per map'):
    """The setup to headline: current patch, best confidence, per map."""
    for s in lst or []:
        if s['unit'] == unit:
            return s
    return None
