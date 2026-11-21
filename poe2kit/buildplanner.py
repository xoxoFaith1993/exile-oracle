"""Export a build to Path of Exile 2's in-game Build Planner.

GGG documents the format (https://www.pathofexile.com/developer/docs/game, "Build Planner", Version 1,
experimental): a JSON *.build file in Documents/My Games/Path of Exile 2/BuildPlanner. The game watches that folder,
so a new or changed file shows up in game by itself: the passive tree path with hover notes, the skills and supports
to cut, and hints on gear slots.

  make(con, build_id | pob_code, notes)  -> the .build document + a report of what was left out
  write(doc, confirm)                    -> saves "Exile Oracle - <name>.build" (the first write ever needs confirm)

Ids: PoB passive numbers -> PassiveSkills Id and ascendancy names -> Ascendancy Id come from planner_ids.json (data
pack, made from the game's own tables); PoB's gems already carry their BaseItemTypes id.
The toolkit only ever writes and deletes its own files (the "Exile Oracle - " prefix, or "PoE2 Toolkit - " from before the rename) in that folder."""

import json
import os
import re
import time
import xml.etree.ElementTree as ET

from . import config, osutil, vault

PREFIX = 'Exile Oracle - '
OLD_PREFIXES = ('PoE2 Toolkit - ',)   # files from before the rename are still ours
ENDGAME_FROM = 55   # levelling plans: endgame gear hints show from this level, levelling hints before it
SLOTS = {'Weapon 1': 'Weapon1', 'Weapon 2': 'Offhand1', 'Weapon 1 Swap': 'Weapon2', 'Weapon 2 Swap': 'Offhand2',
         'Helmet': 'Helm1', 'Body Armour': 'BodyArmour1', 'Gloves': 'Gloves1', 'Boots': 'Boots1',
         'Amulet': 'Amulet1', 'Ring 1': 'Ring1', 'Ring 2': 'Ring2', 'Belt': 'Belt1'}
_cache = {}


def folder():
    """The game's BuildPlanner folder (Windows Documents, or the Proton prefix on Linux / Steam Deck), or None if
    the game has never been started on this PC."""
    for d in osutil.documents_dirs():
        game = os.path.join(d, 'My Games', 'Path of Exile 2')
        if os.path.isdir(game):
            return os.path.join(game, 'BuildPlanner')
    return None


def _ids():
    if 'ids' not in _cache:
        p = config.data_file('planner_ids.json')
        if not p:
            raise FileNotFoundError('planner_ids.json is missing from the data pack')
        with open(p, encoding='utf-8') as f:
            _cache['ids'] = json.load(f)
    return _cache['ids']


def _meta_gems():
    """Meta gems (Cast on Critical, Cast on Shock, ...) aren't supported by the Build Planner yet."""
    if 'meta' not in _cache:
        p = os.path.join(config.POB_DIR, 'src', 'Data', 'Gems.lua')
        meta = set()
        try:
            text = open(p, encoding='utf-8').read()
            for block in text.split('\n\t["')[1:]:
                gid = block.split('"', 1)[0]
                if re.search(r'\n\t\t\tmeta = true', block):
                    meta.add(gid)
        except OSError:
            pass
        _cache['meta'] = meta
    return _cache['meta']


def _clean(t):
    """Free text for a hover note: the markup uses { }, so keep them out of plain text."""
    return re.sub(r'[{}]', '', str(t or '')).strip()


MARKUP = re.compile(r'<(?:[a-z]+|rgb\(\d+, ?\d+, ?\d+\))>\{')


def _note(t):
    """A hover note: kept as written when it already uses the game's markup (<green>{...}), else made plain."""
    t = str(t or '').strip()
    return t if MARKUP.search(t) else _clean(t)


def _node_names(version):
    try:
        from . import character
        return {n['id']: n for n in character.tree(version)['nodes']}
    except Exception:
        return {}


def _levels(title):
    m = re.search(r'(?:level|lvl|lv)\s*(\d{1,3})', title or '', re.I) or re.match(r'^\s*(\d{1,3})\b', title or '')
    if m:
        return int(m.group(1))
    return 100 if re.search(r'end ?game|final|maps', title or '', re.I) else None


def make(con, build_id=None, pob_code=None, notes=None, name=None, include_gear=True, auto_route=False):
    """notes (all optional, usually written by Claude):
         {'description': str,
          'passives': {node name or game id: text},
          'skills':   {gem name: text},
          'slots':    {'Helmet' | 'Ring 1' | ...: text}}"""
    notes = notes or {}
    label = 'pasted build'
    if build_id is not None:
        r = con.execute('SELECT label, pob_code FROM build WHERE id=?', (int(build_id),)).fetchone()
        if not r:
            raise ValueError('no such build in the vault')
        label, pob_code = r['label'], r['pob_code']
    if not pob_code:
        raise ValueError('give build_id or pob_code')
    root = ET.fromstring(vault.decode(pob_code))
    ids = _ids()
    report = {'unmapped_passives': [], 'skipped_skills': [], 'stages': []}
    b_el = root.find('Build')

    # ---- passives: the active tree; several trees titled with levels become a levelling route ----
    tree = root.find('Tree')
    specs = tree.findall('Spec')
    active = specs[max(0, int(tree.get('activeSpec') or 1) - 1)] if specs else None
    staged = [(s, _levels(s.get('title'))) for s in specs]
    staged = sorted([x for x in staged if x[1]], key=lambda x: x[1]) if all(x[1] for x in staged) and len(specs) > 1 else []
    names = _node_names((active.get('treeVersion') if active is not None else None) or '0_5')
    pn = {str(k).lower(): v for k, v in (notes.get('passives') or {}).items()}

    def passive(num, interval=None):
        gid = ids['passives'].get(str(num))
        if not gid:
            report['unmapped_passives'].append(num)
            return None
        node = names.get(num) or {}
        text = pn.get(gid.lower()) or pn.get((node.get('n') or '').lower()) or pn.get(str(num))
        if not text and node.get('k') in ('keystone',):
            text = f"<gold>{{Keystone: {_clean(node.get('n'))}}}"
        if not text and interval is None:
            return gid
        p = {'id': gid}
        if interval:
            p['level_interval'] = interval
        if text:
            p['additional_text'] = _note(text)
        return p

    passives = []
    if staged:   # e.g. "Level 30", "Level 60", "Endgame 95": each node from the stage it first appears in
        seen, prev = {}, 0
        for s, lvl in staged:
            for num in (int(x) for x in (s.get('nodes') or '').split(',') if x):
                seen.setdefault(num, (prev + 1 if prev else 1))
            report['stages'].append({'title': s.get('title'), 'level': lvl})
            prev = lvl
        final = [int(x) for x in (staged[-1][0].get('nodes') or '').split(',') if x]
        for num in final:
            p = passive(num, [seen.get(num, 1), 100])
            if p:
                passives.append(p)
    elif active is not None and auto_route:
        # one endgame tree: the automatic levelling route (route.py) decides the order and the level of each node
        from . import route
        have = [int(x) for x in (active.get('nodes') or '').split(',') if x]
        cls = b_el.get('className') if b_el is not None else None
        main, asc_nodes, _start = route.order(have, active.get('treeVersion') or '0_5', cls)
        # the game shows a passive only while the character's level is inside its range, so each one appears
        # LOOKAHEAD levels before it's due (seen at level 1: nothing showed when ranges started at the due level)
        ahead = route.LOOKAHEAD

        def due(p, lvl, tag):
            p['level_interval'] = [max(1, lvl - ahead), 100]
            p['additional_text'] = tag + ('\n' + p['additional_text'] if p.get('additional_text') else '')
            return p
        lv_list = route.levels(len(main))
        ws = route.weapon_set_nodes(main, lv_list, active.get('treeVersion') or '0_5')
        for num, lvl in zip(main, lv_list):
            p = passive(num, [1, 100])
            if p:
                tag = f"<grey>{{Take at level {lvl}}}"
                if num in ws:   # quest points come as Weapon Set points: damage nodes go on Weapon Set I
                    p['weapon_set'] = 1
                    tag += f"\n<orange>{{Use a Weapon Set I point ({ws[num]} quest)}}"
                passives.append(due(p, lvl, tag))
        report['weapon_set_nodes'] = len(ws)
        report['route_nodes'] = [{'node': n, 'level': l, 'ws': n in ws} for n, l in zip(main, lv_list)]   # Build Lab
        report['route_start'] = _start
        report['tree_version'] = active.get('treeVersion') or '0_5'
        trials = ['1st', '2nd', '3rd', '4th']
        for i, (num, lvl) in enumerate(zip(asc_nodes, route.asc_levels(len(asc_nodes)))):
            p = passive(num, [1, 100])
            if p:
                passives.append(due(p, lvl, f"<grey>{{Ascendancy: after your {trials[min(3, i // 2)]} trial}}"))
        report['asc_nodes'] = [{'node': n, 'level': l} for n, l in zip(asc_nodes, route.asc_levels(len(asc_nodes)))]
        report['route'] = 'automatic'
    elif active is not None:
        for num in (int(x) for x in (active.get('nodes') or '').split(',') if x):
            p = passive(num)
            if p:
                passives.append(p)

    levelling_gear = True   # "look for these mods" until 55, the endgame item after: sound for every plan

    # ---- skills: socket groups (not the copies PoB adds for item/tree-granted skills) ----
    meta = _meta_gems()
    sn = {str(k).lower(): v for k, v in (notes.get('skills') or {}).items()}
    skills_el = root.find('Skills')
    sets = skills_el.findall('SkillSet') if skills_el is not None else []
    use = sets[max(0, int(skills_el.get('activeSkillSet') or 1) - 1)] if sets else skills_el
    skills = []
    for grp in (use.iter('Skill') if use is not None else []):
        if grp.get('source') or grp.get('enabled') == 'false':
            continue
        gems = [g for g in grp.findall('Gem') if g.get('enabled') != 'false' and g.get('gemId')]
        actives = [g for g in gems if 'SupportGem' not in g.get('gemId')]
        supports = [g for g in gems if 'SupportGem' in g.get('gemId')]
        for g in actives:
            if g.get('gemId') in meta:
                report['skipped_skills'].append(f"{g.get('nameSpec')} (meta gems aren't supported by the planner yet)")
        actives = [g for g in actives if g.get('gemId') not in meta]
        if not actives:
            continue
        for i, g in enumerate(actives):
            sk = {'id': g.get('gemId')}
            text = sn.get((g.get('nameSpec') or '').lower())
            gid = g.get('gemId')
            if not text and ('Ascendancy' in gid or 'Unique' in gid or 'PlayerDefault' in gid):
                text = '<grey>{Granted by your ascendancy or an item: cut only its supports}'
            if text:
                sk['additional_text'] = _note(text)
            from . import route
            gl = route.gem_level(gid)   # a fact from the game data: shown for every plan
            if gl and gl > 1:   # when it can first be cut and used
                sk['level_interval'] = [gl, 100]
            if i == 0 and supports:
                sk['support_skills'] = []
                for s in supports:
                    st = sn.get((s.get('nameSpec') or '').lower())
                    sl = route.gem_level(s.get('gemId'))
                    e = {'id': s.get('gemId')}
                    if sl and sl > 1:
                        e['level_interval'] = [sl, 100]
                    if st:
                        e['additional_text'] = _note(st)
                    sk['support_skills'].append(e if len(e) > 1 else s.get('gemId'))
            if not any(x['id'] == sk['id'] for x in skills):
                skills.append(sk)

    # ---- gear hints: what goes in each slot, uniques by name, top mods for rares, toolkit price ----
    slots = []
    if include_gear:
        from . import cost
        items = {it.get('id'): (it.text or '') for it in root.find('Items').iter('Item')} if root.find('Items') is not None else {}
        prices = {}
        if build_id is not None:
            try:
                prices = cost.slot_values(con, build_id).get('slots') or {}
            except Exception:
                prices = {}
        gn = {str(k).lower(): v for k, v in (notes.get('slots') or {}).items()}
        done = set()
        for sl in root.find('Items').iter('Slot') if root.find('Items') is not None else []:
            slot, inv = sl.get('name'), SLOTS.get(sl.get('name'))
            if not inv or inv in done or sl.get('itemId') in (None, '0') or sl.get('itemId') not in items:
                continue
            done.add(inv)
            it = cost.parse_item(items[sl.get('itemId')])
            entry = {'inventory_id': inv}
            v = (prices.get(slot) or {}).get('value_div')
            price = f"\n<grey>{{toolkit price: about {v:.1f} div}}" if v else ''
            custom = gn.get(slot.lower())
            mods = [m for m in it['mods'] if not re.search(r'\(rune\)|\(implicit\)|\(enchant\)', m)]
            if it['rarity'] == 'UNIQUE' and it['name']:
                entry['unique_name'] = it['name']
                text = f"<unique>{{{_clean(it['name'])}}}\n<grey>{{{_clean(it['base'])}}}" + price
            else:
                text = (f"<yellow>{{{_clean(it['base'] or 'Rare item')}}}\n\n<grey>{{Wanted mods (yours)\n"
                        "-------------------\n" + '\n'.join(f"{i + 1}. {_clean(m)}" for i, m in enumerate(mods[:5]))
                        + '}' + price)
            entry['additional_text'] = _note(custom) if custom else text
            if levelling_gear:
                # a levelling plan: the endgame item only from ENDGAME_FROM; before that, the kinds of stats to look
                # for (the same mods without numbers: they matter at any level, the numbers don't)
                entry['level_interval'] = [ENDGAME_FROM, 100]
                kinds = list(dict.fromkeys(re.sub(r'[+-]?\d+(?:\.\d+)?', '#', _clean(m)) for m in mods))[:5]
                if kinds:
                    lead = (f"Until you have {_clean(it['name'])}: look for" if it['rarity'] == 'UNIQUE'
                            else "Look for these mods (any base)")
                    slots.append({'inventory_id': inv, 'level_interval': [1, ENDGAME_FROM - 1],
                                  'additional_text': f"<yellow>{{Levelling}}\n<grey>{{{lead}\n-------------------\n"
                                  + '\n'.join(f"{i + 1}. {k}" for i, k in enumerate(kinds)) + '}'})
            slots.append(entry)

    b = root.find('Build')
    asc = (active.get('ascendancyInternalId') if active is not None else None) or \
        ids['ascendancies'].get(b.get('ascendClassName') if b is not None else '')
    doc = {'name': _clean(name or label)[:60] or 'Exile Oracle build', 'author': 'Exile Oracle',
           'description': _clean(notes.get('description')) or
           f"{b.get('ascendClassName') if b is not None else ''} level {b.get('level') if b is not None else '?'}, "
           f"exported by Exile Oracle {time.strftime('%Y-%m-%d')}",
           'link': f'https://github.com/{config.REPO}'}
    if report.get('route') == 'automatic':
        doc['description'] += '\nLevelling route reviewed with Claude: passives show 10 levels before they are due.'
    elif not staged:
        doc['description'] += ('\nFull endgame path. Ask the Oracle to plan and review a levelling route for this build '
                               '(passive order, early skills).')
    if True:   # the passive point quests (24 in all) are easy to skip: a fact, shown for every plan
        from . import route
        qs = route.quest_reminders()
        if qs:
            doc['description'] += ('\nDon\'t skip the passive point quests (+2 each): ' +
                                   '; '.join(f"Act {q['act']} {q['area']} ({q['who']})" for q in qs))
    if asc and asc != 'nil':
        doc['ascendancy'] = asc
    doc['passives'] = passives
    doc['skills'] = skills
    if slots:
        doc['inventory_slots'] = slots
    report.update(passives=len(passives), skills=len(skills), slots=len(slots), ascendancy=doc.get('ascendancy'))
    return doc, report


def _filename(name):
    return PREFIX + re.sub(r'[^\w\- .()]+', '', name).strip()[:60] + '.build'


def write(doc, confirm=False):
    """Save to the game's BuildPlanner folder. The first write ever needs confirm=True (a change on the player's PC);
    after that it's remembered. Only the toolkit's own files are ever replaced."""
    d = folder()
    if not d:
        return {'ok': False, 'error': "Path of Exile 2's Documents folder wasn't found: start the game once first."}
    path = os.path.join(d, _filename(doc['name']))
    if not config.settings().get('build_planner_ok') and not confirm:
        return {'ok': False, 'needs_ok': True, 'path': path,
                'note': "First time: this puts a file in the game's BuildPlanner folder (GGG's documented feature for "
                        "builds from other tools). Confirm once to allow it."}
    if confirm:
        config.save_settings({'build_planner_ok': True})
    os.makedirs(d, exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)   # one step, so the game's file watcher never sees half a file
    for old in OLD_PREFIXES:   # the same plan saved under the old name: remove it so the game lists it once
        stale = os.path.join(d, old + os.path.basename(path)[len(PREFIX):])
        if os.path.exists(stale):
            try:
                os.remove(stale)
            except OSError:
                pass
    return {'ok': True, 'path': path, 'size': os.path.getsize(path)}


def files():
    d = folder()
    if not d or not os.path.isdir(d):
        return []
    return [{'file': f, 'mine': f.startswith((PREFIX,) + OLD_PREFIXES), 'modified': os.path.getmtime(os.path.join(d, f))}
            for f in sorted(os.listdir(d)) if f.endswith('.build')]


def remove(file):
    d = folder()
    if not d or not file.startswith((PREFIX,) + OLD_PREFIXES) or os.sep in file or '/' in file:
        return {'ok': False, 'error': "only the toolkit's own .build files can be removed here"}
    try:
        os.remove(os.path.join(d, file))
    except OSError as e:
        return {'ok': False, 'error': str(e)}
    return {'ok': True}
