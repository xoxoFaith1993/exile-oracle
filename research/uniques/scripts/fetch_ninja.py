"""Step 1: poe.ninja PoE 2 economy (public, economy-only) - current unique overviews for the leagues poe.ninja still serves,
then per-item daily history for the chosen uniques. Polite: 2.5 s between live requests, everything cached in ../cache.
Never touches builds/character/profile endpoints."""
import json, os, sys, urllib.parse
import fetchlib as f

BASE = 'https://poe.ninja/poe2/api/economy/stash/current/item'
TYPES = ['UniqueWeapons', 'UniqueArmours', 'UniqueAccessories', 'UniqueFlasks', 'UniqueCharms', 'UniqueJewels',
         'UniqueSanctumRelics', 'UniqueTablets', 'PrecursorTablets']
LEAGUES = ['Runes of Aldur', 'Forbidden Rites']
OUT = os.path.join(f.CACHE, 'ninja')
os.makedirs(OUT, exist_ok=True)


def overview(lg, t):
    return f.get_json(f'{BASE}/overview?' + urllib.parse.urlencode({'league': lg, 'type': t}))[1]


def history(lg, t, iid):
    return f.get_json(f'{BASE}/history?' + urllib.parse.urlencode({'league': lg, 'type': t, 'id': iid}))[1]


if __name__ == '__main__':
    step = sys.argv[1] if len(sys.argv) > 1 else 'overview'
    if step == 'overview':
        allrows = []
        for lg in LEAGUES:
            for t in TYPES:
                d = overview(lg, t)
                for ln in (d or {}).get('lines', []):
                    allrows.append({'league': lg, 'type': t, 'id': ln['id'], 'name': ln['name'], 'base': ln.get('baseType'),
                                    'variant': ln.get('variant'), 'corrupted': ln.get('corrupted'), 'value': ln.get('primaryValue'),
                                    'listings': ln.get('listingCount'), 'spark': (ln.get('sparkLine') or {}).get('totalChange'),
                                    'detailsId': ln.get('detailsId'), 'level': ln.get('levelRequired')})
                print(lg, t, len((d or {}).get('lines', [])))
        json.dump(allrows, open(os.path.join(OUT, 'overview_rows.json'), 'w'), indent=0)
    elif step == 'history':
        sel = json.load(open(os.path.join(OUT, 'selected.json')))  # [{league,type,id,name,...}]
        out = {}
        for r in sel:
            h = history(r['league'], r['type'], r['id'])
            out[f"{r['league']}|{r['type']}|{r['id']}"] = {'meta': r, 'history': h}
            print(r['league'], r['name'], r.get('corrupted'), len(h or []))
        json.dump(out, open(os.path.join(OUT, 'histories.json'), 'w'))
