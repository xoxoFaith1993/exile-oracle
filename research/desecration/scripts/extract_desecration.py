"""Pull PoE 2 desecration data (bones, desecration omens, desecrated mod pool, game text) out of the extracted
game tables. Read-only, standard library only, re-runnable on a new game build.

Usage:
    python extract_desecration.py <tables_dir> [--repoe <repoe_dir>] [--out <desecration-data.json>]

<tables_dir>  folder of the game's tables as JSON (mods.json, baseitemtypes.json, ...), e.g.
              <data folder>\\gamefiles\\26744644\\tables
--repoe       optional folder with RePoE's mods.min.json; only used for the readable stat text of each mod
--out         where to write the result (default: ./desecration-data.json)

The result is the "game data" half of desecration.json; build_json.py merges it with the researched rules.
"""
import argparse
import collections
import json
import os
import re
import sys

LINEAGES = {'ulaman_mod': 'Ulaman', 'amanamu_mod': 'Amanamu', 'kurgal_mod': 'Kurgal'}
GEN = {1: 'prefix', 2: 'suffix', 3: 'unique'}


def load(folder, name):
    with open(os.path.join(folder, name + '.json'), encoding='utf-8') as f:
        return json.load(f)


def clean(text):
    """[Keyword|Shown text] -> Shown text."""
    return re.sub(r'\[([^|\]]+)\|([^\]]+)\]', r'\2', re.sub(r'\[([^|\]]+)\]', r'\1', text or ''))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tables')
    ap.add_argument('--repoe')
    ap.add_argument('--out', default='desecration-data.json')
    a = ap.parse_args()
    T = a.tables
    build = os.path.basename(os.path.dirname(os.path.abspath(T)))

    bases = load(T, 'baseitemtypes')
    cur = {r['BaseItemType']: r for r in load(T, 'currencyitems')}
    classes = load(T, 'itemclasses')
    tags = load(T, 'tags')
    mods = load(T, 'mods')
    fams = load(T, 'modfamily')
    mtypes = load(T, 'modtype')
    tickets = load(T, 'abyssbenchtickettypes')
    words = {r['Id']: r for r in load(T, 'keywordpopups')}
    strings = {}
    for n in ('clientstrings', 'clientstrings2'):
        try:
            for r in load(T, n):
                strings[r['Id']] = r['Text']
        except FileNotFoundError:
            pass
    text_of = {}
    if a.repoe:
        rp = json.load(open(os.path.join(a.repoe, 'mods.min.json'), encoding='utf-8'))
        text_of = {k: v.get('text') or '' for k, v in rp.items()}

    tag_id = lambda i: tags[i]['Id'] if i is not None and 0 <= i < len(tags) else None

    # ---- bones -------------------------------------------------------------------------------------------
    bones = []
    for t in tickets:
        b = bases[t['BaseItemType']]
        c = cur.get(t['BaseItemType'], {})
        name = b['Name']
        tier = name.split()[0]
        bones.append({
            'name': name,
            'metadata_id': b['Id'],
            'bone': name.split()[-1],
            'tier': tier,
            'action': c.get('Action'),
            'item_classes': [classes[i]['Id'] for i in t['UsableOnItemClasses']],
            'item_class_names': [classes[i]['Name'] for i in t['UsableOnItemClasses']],
            'max_item_level': t['MaximumItemLevel'] or None,
            'min_modifier_level': t['MinimumModLevel'] or None,
            'drop_level': b['DropLevel'],
            'stack_size': c.get('StackSize'),
            'description': clean(c.get('Description')),
            'directions': c.get('Directions'),
            'pool_tag': tag_id(t['Tag']),
            # unnamed columns of AbyssBenchTicketTypes, kept raw; see desecration.md for what they most likely mean
            'raw_unk3': t['_unk3'],
            'raw_unk6_exclusive_chance': round(t['_unk6'], 4),
            'raw_unk7_lineage_omens': t['_unk7'],
        })

    # ---- omens that mention desecration --------------------------------------------------------------------
    omens = []
    for i, b in enumerate(bases):
        if '/Omen' not in b['Id']:
            continue
        c = cur.get(i, {})
        d = c.get('Description') or ''
        if 'Abyssalify' in d or 'Abyss' in b['Id']:
            omens.append({'name': b['Name'], 'metadata_id': b['Id'], 'drop_level': b['DropLevel'],
                          'stack_size': c.get('StackSize'), 'description': clean(d)})

    # ---- base tags per item class (to resolve which classes a mod can appear on) ---------------------------
    # The tables only list a base's own tags, not the ones it inherits from its parent .ot file, so RePoE's
    # base_items export (which has the full tag list) is used when given.
    class_bases = collections.defaultdict(list)
    cls_index = {c['Id']: i for i, c in enumerate(classes)}
    rb = None
    if a.repoe and os.path.exists(os.path.join(a.repoe, 'base_items.min.json')):
        rb = json.load(open(os.path.join(a.repoe, 'base_items.min.json'), encoding='utf-8'))
    if rb:
        for v in rb.values():
            if v.get('release_state') == 'released' and v['item_class'] in cls_index:
                class_bases[cls_index[v['item_class']]].append(set(v['tags']) | {'default'})
    else:
        for b in bases:
            ic = b['ItemClass']
            if ic is None or not b['Name'] or b['Id'].startswith('Metadata/Items/Currency'):
                continue
            class_bases[ic].append({tag_id(x) for x in b['Tags']} | {'default'})
    bone_tags = {t['Tag'] and tag_id(t['Tag']) for t in tickets} - {None}
    # item classes each kind of bone can be used on (a mod only counts on classes its bone accepts)
    def bone_classes(pred):
        return {i for t in tickets if pred(bases[t['BaseItemType']]['Name']) for i in t['UsableOnItemClasses']}
    src_classes = {
        'bone_equipment': bone_classes(lambda n: n.split()[-1] in ('Jawbone', 'Rib', 'Collarbone')),
        'altered_collarbone': bone_classes(lambda n: n.startswith('Altered')),
        'cranium_jewel': bone_classes(lambda n: n.endswith('Cranium')),
        'vertebrae_waystone': bone_classes(lambda n: n.endswith('Vertebrae')),
    }

    def weight_for(base_tags, sw):
        for tg, w in sw:
            if tg in base_tags:
                return w
        return 0

    # ---- desecrated mod pool ------------------------------------------------------------------------------
    pool = []
    for m in mods:
        if m['Domain'] != 28 or GEN.get(m['GenerationType']) not in ('prefix', 'suffix'):
            continue
        if not m['Id'].startswith(('AbyssMod', 'ConvertedAbyssMod', 'GenesisTree', 'MapAbyss')):
            continue  # Unique* rows are fixed mods of unique items, not part of the bone pool
        sw = [(tag_id(t), w) for t, w in zip(m['SpawnWeight_Tags'], m['SpawnWeight_Values'])]
        imp = [tag_id(t) for t in m['ImplicitTags']]
        lineage = next((LINEAGES[x] for x in imp if x in LINEAGES), None)
        sw_lineage = [LINEAGES[tg] for tg, w in sw if tg in LINEAGES]
        if m['Id'].startswith('GenesisTree'):
            source = 'altered_collarbone'
        elif m['Id'].startswith('MapAbyss'):
            source = 'vertebrae_waystone'
        elif re.match(r'AbyssMod(Radius)?Jewel(Prefix|Suffix)', m['Id']):
            source = 'cranium_jewel'
        else:
            source = 'bone_equipment'
        cls = []
        for ic, blist in class_bases.items():
            if ic in src_classes[source] and any(weight_for(bt | bone_tags if source == 'altered_collarbone' else bt, sw) > 0 for bt in blist):
                cls.append(classes[ic]['Id'])
        stats = []
        for k in range(1, 9):
            s = m.get(f'Stat{k}')
            if s is not None:
                stats.append({'stat_index': s, 'min': m[f'Stat{k}Value'][0], 'max': m[f'Stat{k}Value'][1]})
        pool.append({
            'id': m['Id'],
            'affix_name': m['Name'],
            'side': GEN[m['GenerationType']],
            'lineage': lineage,
            'lineage_in_spawn_tags': sw_lineage[0] if sw_lineage else None,
            'source': source,
            'level': m['Level'],
            'max_level': m['MaxLevel'],
            'mod_type': mtypes[m['ModType']]['Name'],
            'families': [fams[f]['Id'] for f in m['Families']],
            'spawn_weights': [{'tag': tg, 'weight': w} for tg, w in sw],
            'spawnable': any(w > 0 for _, w in sw),
            'item_classes': sorted(cls),
            'implicit_tags': imp,
            'text': text_of.get(m['Id'], ''),
            'stats': stats,
        })

    # ---- desecration-related game text -------------------------------------------------------------------
    kw = {k: clean(words[k]['Definition']) for k in ('Abyssalify', 'UnstableDesecration', 'MarkofAbyssalLord',
                                                     'BetterCurrencyMinimumLevel', 'CurrencyMaximumItemLevel',
                                                     'AbyssalDepths', 'ContainsAbyss') if k in words}
    cs = {k: clean(v) for k, v in strings.items() if re.search(
        r'Veiled|Unveil|Desecrat|AbyssRefresh|OmenIncompatible|TooManyAbyssMods|AbyssWell', k)
        and not k.startswith(('TutorialPanelVeiled', 'BetrayalChoice', 'MasterFullName'))}
    can_veil = {c['Id']: c.get('CanHaveVeiledMods') for c in classes}

    out = {
        'game_build': build,
        'tables': os.path.abspath(T),
        'bones': bones,
        'omens': omens,
        'mod_pool': pool,
        'keywords': kw,
        'client_strings': cs,
        'item_classes_can_have_veiled_mods': sorted(k for k, v in can_veil.items() if v),
    }
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    n = collections.Counter((p['source'], p['spawnable']) for p in pool)
    print(f'build {build}: {len(bones)} bones, {len(omens)} omens, {len(pool)} desecrated affix mods {dict(n)}',
          file=sys.stderr)


if __name__ == '__main__':
    main()
