"""Write cache/exchange_names.json (exchange item name -> group), cache/gem_names.json and cache/unique_names.json
from the app's game data (<data folder>/data: repoe base_items, skill_gems, uniques, trade-static) and the
metadata ids seen in cache/prices. Also cache/meta_names.json (metadata id -> name, group).
Usage: python -I build_names.py"""
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
C = os.path.join(HERE, 'cache')
DATA = '<data folder>/data'


def group_of(name, meta, ts_cat):
    n = name.lower()
    if n.startswith('omen of'):
        return 'Omens'
    if 'soul core' in n:
        return 'Soul cores'
    if 'catalyst' in n:
        return 'Catalysts'
    if 'essence' in n:
        return 'Essences'
    if n.startswith('uncut '):
        return 'Uncut gems'
    if 'liquid' in n or n.startswith('distilled') or 'simulacrum' in n:
        return 'Delirium'
    if 'breach' in n or 'wombgift' in n:
        return 'Breach'
    if re.search(r'jawbone|rib$|collarbone|cranium', n):
        return 'Abyssal bones'
    if n.endswith(' fate') or 'ultimatum' in n or 'barya' in n:
        return 'Ultimatum/Sekhemas'
    if n.endswith(' rune') or 'talisman' in n or re.search(r'\brune of\b', n):
        return 'Runes'
    if 'idol' in n:
        return 'Idols'
    if ts_cat:
        return ts_cat
    if '/Gems/' in meta:
        return 'LineageSupportGems'
    if 'Expedition' in meta or 'artifact' in n or 'coinage' in n:
        return 'Expedition'
    if 'Splinter' in meta or 'Fragment' in meta or 'splinter' in n:
        return 'Fragments'
    return 'Currency'


def main():
    base = json.load(open(f'{DATA}/repoe/base_items.min.json', encoding='utf-8'))
    ts = json.load(open(f'{DATA}/trade-static.json', encoding='utf-8'))['result']
    ts_cat = {}
    for c in ts:
        for e in c['entries']:
            if e.get('text'):
                ts_cat.setdefault(e['text'], c['label'])
    seen = set()
    for p in glob.glob(os.path.join(C, 'prices', '*.json')):
        seen |= set(json.load(open(p, encoding='utf-8'))['items'])
    EXC = {'StackableCurrency', 'SoulCore', 'Omen', 'UncutSkillGemStackable', 'UncutReservationGemStackable',
           'UncutSupportGemStackable', 'MapFragment', 'VaultKey', 'PinnacleKeyStackable', 'PinnacleKey_OLD',
           'Breachstone', 'IncubatorStackable', 'Expedition2Logbooks', 'AtlasCurrency'}
    for m, v in base.items():
        if v.get('item_class') in EXC and v.get('name') and v.get('release_state', 'released') == 'released'                 and not re.search(r'\[|unused|dnt|test', v['name'], re.I):
            seen.add(m)
    meta = {}
    for m in seen:
        name = (base.get(m) or {}).get('name') or m.rsplit('/', 1)[-1]
        meta[m] = {'name': name, 'group': group_of(name, m, ts_cat.get(name))}
    names = {v['name']: v['group'] for v in meta.values()}
    for t, c in ts_cat.items():
        if t not in names and c not in ('Waystones',):
            names[t] = group_of(t, '', c)
    json.dump(meta, open(os.path.join(C, 'meta_names.json'), 'w', encoding='utf-8'), indent=0, ensure_ascii=False)
    json.dump(names, open(os.path.join(C, 'exchange_names.json'), 'w', encoding='utf-8'), indent=0, ensure_ascii=False)
    gems = json.load(open(f'{DATA}/repoe/skill_gems.min.json', encoding='utf-8'))
    gn = {}
    for v in gems.values():
        bi = v.get('base_item') or {}
        n = bi.get('display_name')
        if n and bi.get('release_state', 'released') == 'released':
            gn[n] = {'type': v.get('gem_type'), 'lineage': bool(v.get('is_lineage'))}
    json.dump(gn, open(os.path.join(C, 'gem_names.json'), 'w', encoding='utf-8'), indent=0, ensure_ascii=False)
    un = json.load(open(f'{DATA}/repoe/uniques.min.json', encoding='utf-8'))
    uq = sorted({v['name'] for v in un.values() if v.get('name')})
    json.dump(uq, open(os.path.join(C, 'unique_names.json'), 'w', encoding='utf-8'), indent=0, ensure_ascii=False)
    print(len(meta), 'exchange ids,', len(names), 'names,', len(gn), 'gems,', len(uq), 'uniques')


if __name__ == '__main__':
    main()
