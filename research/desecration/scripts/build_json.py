"""Build research/desecration/desecration.json: the game data from extract_desecration.py plus the researched
rules (patch notes, poe2db, guides), each part tagged with confidence and source.

Usage:
    python build_json.py <desecration-data.json> [--out ../desecration.json]
Standard library only. Re-run after extract_desecration.py on a new game build.
"""
import argparse
import collections
import datetime
import json
import re

GAME = 'game files (build {b})'
PN030 = 'https://www.pathofexile.com/forum/view-thread/3826682'
PN031 = 'https://www.pathofexile.com/forum/view-thread/3862213'
PN040 = 'https://www.pathofexile.com/forum/view-thread/3883495'
PN050 = 'https://www.pathofexile.com/forum/view-thread/3932540'
P2DB = 'https://poe2db.tw/us/Desecrated_Modifiers'
MAXROLL = 'https://maxroll.gg/poe2/resources/abyss'
VAAL = 'https://www.vaal.tools/mechanics/desecrated_modifiers/'


def clean(t):
    return re.sub(r'\[([^|\]]+)\|([^\]]+)\]', r'\2', re.sub(r'\[([^|\]]+)\]', r'\1', t or ''))


# machine-friendly omen effects (the description text comes from the game files)
OMEN_EFFECTS = {
    'Omen of Abyssal Echoes': dict(effect_type='reveal_reroll', trigger='reveal', params={'rerolls': 1},
                                   notes='Rerolls the whole set of options once; the first set cannot be taken back '
                                         '(guides, medium). Must be active before you press Reveal.',
                                   confidence='high (effect) / medium (all 3 rerolled, no going back)'),
    'Omen of the Sovereign': dict(effect_type='force_lineage', trigger='desecrate', params={'lineage': 'Ulaman'},
                                  applies_to='Weapon, Quiver, Amulet, Ring, Belt (Jawbone / Collarbone, Preserved or Ancient)',
                                  notes='Guarantees at least one Ulaman option. Whether all 3 options become Ulaman is not '
                                        'published (low).',
                                  confidence='high (text) / low (how many of the 3 options)'),
    'Omen of the Liege': dict(effect_type='force_lineage', trigger='desecrate', params={'lineage': 'Amanamu'},
                              applies_to='Weapon, Quiver, Amulet, Ring, Belt (Jawbone / Collarbone, Preserved or Ancient)',
                              notes='As Sovereign, for Amanamu.', confidence='high (text) / low (how many of the 3 options)'),
    'Omen of the Blackblooded': dict(effect_type='force_lineage', trigger='desecrate', params={'lineage': 'Kurgal'},
                                     applies_to='Weapon, Quiver, Amulet, Ring, Belt (Jawbone / Collarbone, Preserved or Ancient)',
                                     notes='As Sovereign, for Kurgal.',
                                     confidence='high (text) / low (how many of the 3 options)'),
    'Omen of Putrefaction': dict(effect_type='replace_all_unrevealed_and_corrupt', trigger='desecrate',
                                 params={'max_unrevealed': 6, 'corrupts': True},
                                 notes='All mods are replaced by up to 6 Unrevealed Desecrated mods and the item becomes '
                                       'Corrupted. Each is then revealed at the Well. A gamble for finished-item '
                                       'lottery, not a deterministic craft.',
                                 confidence='high (text) / medium (each of the 6 revealed separately)'),
    'Omen of Light': dict(effect_type='annul_only_desecrated', trigger='annul', params={'side': 'desecrated'},
                          notes='Next Orb of Annulment removes only the Desecrated mod (items hold at most one, so it '
                                'removes exactly that mod). Removing a still-unrevealed mod this way is likely but not '
                                'confirmed (low).',
                          confidence='high'),
    'Omen of Sinistral Necromancy': dict(effect_type='force_side', trigger='desecrate', params={'side': 'prefix'},
                                         notes='The unrevealed mod is a prefix. On a full item the removed mod is '
                                               'then a prefix too (medium: inferred, not stated).',
                                         confidence='high (text)'),
    'Omen of Dextral Necromancy': dict(effect_type='force_side', trigger='desecrate', params={'side': 'suffix'},
                                       notes='The unrevealed mod is a suffix.', confidence='high (text)'),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('data')
    ap.add_argument('--out', default='../desecration.json')
    a = ap.parse_args()
    D = json.load(open(a.data, encoding='utf-8'))
    b = D['game_build']
    G = GAME.format(b=b)

    bones = []
    for x in D['bones']:
        n = x['name']
        kind = ('equipment' if x['bone'] in ('Jawbone', 'Rib', 'Collarbone') else
                'jewel' if x['bone'] == 'Cranium' else 'waystone' if x['bone'] == 'Vertebrae' else 'other')
        excl = x['raw_unk6_exclusive_chance']
        bones.append({
            'name': n, 'bone': x['bone'], 'tier': x['tier'], 'kind': kind,
            'item_classes': x['item_classes'], 'item_class_names': x['item_class_names'],
            'requires_rarity': 'rare',
            'max_item_level': x['max_item_level'], 'min_modifier_level': x['min_modifier_level'],
            'min_item_level': x['min_modifier_level'],  # currency with a minimum modifier level can't go on lower ilvl
            'stack_size': x['stack_size'], 'drop_level': x['drop_level'],
            'description': x['description'],
            'adds': '1 Unrevealed Desecrated modifier (random side unless a Necromancy omen); if the item has no '
                    'free affix of that side, a random existing modifier is removed first',
            'extra_pool_tag': x['pool_tag'],
            'exclusive_option_chance': excl,
            'exclusive_option_chance_note': 'Unnamed column in AbyssBenchTicketTypes (0.08 for Preserved/Ancient/'
                                            'Cranium/Altered, 0 for Gnawed, 1.0 for Vertebrae). Best reading: the chance '
                                            'that each revealed option comes from the Abyss-exclusive pool instead of the '
                                            'normal pool. Not confirmed by any public source.',
            'lineage_omens_allowed': x['raw_unk7_lineage_omens'],
            'unstable': kind == 'jewel',
            'dropped_since': '0.4.0: no longer drops' if kind == 'waystone' else None,
            'raw': {'unk3': x['raw_unk3']},
            'confidence': {'classes_limits_text_stack': 'high', 'exclusive_option_chance': 'low',
                           'lineage_omens_allowed': 'medium (matches omen text: weapons/jewellery only)'},
            'source': [G + ': AbyssBenchTicketTypes, CurrencyItems, BaseItemTypes', P2DB],
        })

    omens = []
    for o in D['omens']:
        e = OMEN_EFFECTS.get(o['name'], {})
        omens.append({'name': o['name'], 'description': o['description'], 'stack_size': o['stack_size'],
                      'drop_level': o['drop_level'], **e,
                      'source': [G + ': CurrencyItems', P2DB, MAXROLL]})
    omens.append({'name': 'Omen of Whittling', 'description': 'Next Chaos Orb removes the lowest level modifier',
                  'effect_type': 'chaos_remove_lowest', 'trigger': 'chaos',
                  'notes': 'An Unrevealed Desecrated mod counts as level 1, so Whittling + Chaos removes it '
                           '(0.3.1 made Whittling highlight it). Useful to undo a bad desecration.',
                  'confidence': 'medium', 'source': [PN031, 'poe2wiki (snippet)']})

    pool = []
    for m in D['mod_pool']:
        shown = next((L for L in ('Ulaman', 'Amanamu', 'Kurgal') if L in m['affix_name']), None)
        lineage = shown or m['lineage']
        conflict = sorted({v for v in (shown, m['lineage'], m['lineage_in_spawn_tags']) if v} - {lineage})
        pool.append({
            'id': m['id'], 'name': m['affix_name'], 'lineage': lineage,
            'lineage_conflict': conflict or None,
            'side': m['side'], 'pool': m['source'],
            'item_classes': m['item_classes'],
            'spawn_tags': [s['tag'] for s in m['spawn_weights'] if s['weight'] > 0],
            'level': m['level'], 'tier_group': m['families'][0] if m['families'] else m['mod_type'],
            'families': m['families'], 'mod_type': m['mod_type'],
            'text': clean(m['text']), 'stats': m['stats'],
            'weight': 1 if m['spawnable'] else 0,
            'spawnable': m['spawnable'],
        })

    def count(pred):
        c = collections.Counter()
        for p in pool:
            if p['spawnable'] and pred(p):
                for ic in p['item_classes']:
                    c[f"{ic}|{p['side']}"] += 1
        return dict(sorted(c.items()))

    out = {
        'meta': {
            'title': 'PoE 2 desecration (bones, Well of Souls, desecrated mods)',
            'game_build': b, 'generated': datetime.date.today().isoformat(),
            'covers': 'patch 0.5.x data; 1.0 (2026-12-11) not yet known',
            'confidence_legend': {'high': 'game files or official patch notes', 'medium': 'several community sources agree / strong inference from data',
                                  'low': 'one source, or our own reading of an unnamed data column'},
            'scripts': ['scripts/extract_desecration.py <tables_dir> --repoe <repoe_dir>', 'scripts/build_json.py desecration-data.json'],
        },
        'rules': [
            {'id': 'rare_only', 'rule': 'Bones only work on Rare items of their item classes.', 'confidence': 'high', 'source': [G, P2DB]},
            {'id': 'one_desecrated', 'rule': 'An item can hold at most 1 Desecrated mod (revealed or not); "This item already has a Desecrated Modifier."', 'confidence': 'high', 'source': [G + ': ClientStrings, KeywordPopups', PN050]},
            {'id': 'full_item_removes_random', 'rule': 'No open affix needed: if modifiers are full a random modifier is removed and the unrevealed mod added.', 'confidence': 'high', 'source': [G + ': KeywordPopups Abyssalify', P2DB]},
            {'id': 'side', 'rule': 'The unrevealed mod is a Desecrated Prefix or Desecrated Suffix (shown on the item); the side is random unless Sinistral/Dextral Necromancy is used, and the reveal only offers mods of that side.', 'confidence': 'high (side shown) / medium (random 50/50 weighting)', 'source': [G + ': ClientStrings ItemDisplayVeiledPrefix/Suffix', 'poe2wiki (snippet)']},
            {'id': 'armour_suffix_only', 'rule': 'Body Armour, Helmet, Gloves, Boots, Shield and Buckler have no exclusive desecrated prefixes. The reveal can still offer normal prefixes (medium).', 'confidence': 'high (no exclusive prefixes)', 'source': [G, P2DB]},
            {'id': 'gnawed_cap', 'rule': 'Gnawed bones: item level 64 or lower. All exclusive lineage mods are level 65, so Gnawed bones can only reveal normal mods.', 'confidence': 'high', 'source': [G]},
            {'id': 'ancient_floor', 'rule': 'Ancient bones: Minimum Modifier Level 40 (offered mods are level 40+, except a mod type that has no tier that high keeps its best tier); cannot be used below item level 40.', 'confidence': 'high', 'source': [G + ': KeywordPopups BetterCurrencyMinimumLevel']},
            {'id': 'counts_as', 'rule': 'Since 0.5.0 (25/5/26 update) desecrated mods no longer count as crafted mods.', 'confidence': 'high', 'source': [PN050]},
            {'id': 'well_slot_locked', 'rule': 'An item in the Well of Souls slot cannot be modified.', 'confidence': 'high', 'source': [G + ': ClientStrings VeiledItemCannotBeModifiedError']},
            {'id': 'mark_of_abyssal_lord', 'rule': 'Essence of the Abyss adds "Mark of the Abyssal Lord"; desecrating that item always removes the Mark and adds a higher-tier Unrevealed mod.', 'confidence': 'high (text) / low (what "higher tier" means)', 'source': [G + ': KeywordPopups MarkofAbyssalLord']},
            {'id': 'recombinator', 'rule': 'Recombination can carry at most one Desecrated mod.', 'confidence': 'high', 'source': [G + ': ClientStrings RecombinatorErrorTooManyAbyssMods']},
            {'id': 'jewel_unstable', 'rule': 'Preserved Cranium on jewels: rising chance to destroy the jewel each time (Unstable Desecration). Heart of the Well / Time-Lost style jewels say "Can be Desecrated N Times".', 'confidence': 'high (text) / unknown numbers', 'source': [G, PN031]},
        ],
        'reveal_model': {
            'where': 'Well of Souls (Act 2 Abyss hub; travel via the world map pin)',
            'choices': 3, 'pick': 1, 'reroll_omen': 'Omen of Abyssal Echoes', 'rerolls_with_omen': 1,
            'side': 'fixed by the unrevealed mod (prefix or suffix)',
            'option_draw': [
                'For each of the 3 options: with probability exclusive_option_chance (bone field; 0.08 for Preserved/Ancient) draw from the Abyss-exclusive pool for that item class and side, else from the item\'s normal mod pool (same side, item level, bone minimum modifier level).',
                'Normal-pool draws use the normal spawn weights (the same as Exalted Orbs). Real weights are not in the game files; the app uses equal weights as elsewhere.',
                'Exclusive-pool draws: all exclusive mods have flat weight 1 in the data, so uniform among the eligible ones.',
                'Options are distinct mod groups (assumed, like other multi-mod draws), and none may share a group with a mod already on the item.',
                'Lineage omen (Weapon/Jewellery): at least 1 option is from that lineage.',
                'Altered Collarbone adds the breach_desecration tag, so its otherworldly (Genesis) mods can be drawn; their chance is not published.',
                'Preserved Vertebrae (exclusive chance 1.0): options are always desecrated waystone mods.',
            ],
            'confidence': {'3_options_pick_1': 'high (0.3.0 notes, game UI text)', 'normal_mods_included': 'medium-high (poe2db "may include base modifiers")',
                           'exclusive_chance_0.08': 'low (our reading of an unnamed column)', 'distinct_groups': 'low (assumed)',
                           'lineage_omen_one_of_three': 'low', 'weights': 'not in game files'},
            'p_at_least_one_exclusive': {'Preserved/Ancient': round(1 - 0.92 ** 3, 4), 'with_echoes': round(1 - 0.92 ** 6, 4), 'Gnawed': 0.0},
            'source': [PN030, G + ': AbyssBenchTicketTypes, ClientStrings', P2DB, MAXROLL],
        },
        'unrevealed_item': {
            'occupies_affix': {'value': True, 'confidence': 'high', 'note': 'shown as "Desecrated Prefix/Suffix"; counts toward the 3/3 limit'},
            'can_desecrate_again': {'value': False, 'confidence': 'high'},
            'chaos_annul_remove_it': {'value': True, 'confidence': 'medium', 'note': 'it is a mod like any other; Whittling treats it as level 1; Omen of Light targets it'},
            'exalt_divine_work': {'value': True, 'confidence': 'medium', 'note': 'Exalt can fill other free slots; Divine has no values to reroll on an unrevealed mod (low)'},
            'fracture': {'value': 'unknown', 'confidence': 'low'},
            'vaal': {'value': 'unknown', 'confidence': 'low', 'note': 'Putrefaction corrupts with unrevealed mods still revealable, which suggests corrupted items can still be revealed'},
            'tradeable': {'value': 'unknown (no rule against it found)', 'confidence': 'low'},
            'source': [G, P2DB, PN031, 'https://poe2craft.com/guides/abyss-well-of-souls'],
        },
        'consumes': {
            'desecrate': ['bone (see bones)', 'optional: Omen of Sinistral/Dextral Necromancy', 'optional: Omen of the Sovereign/Liege/Blackblooded', 'optional: Omen of Putrefaction'],
            'reveal': ['nothing (free at the Well of Souls)', 'optional: Omen of Abyssal Echoes'],
            'remove_desecrated': ['Orb of Annulment + Omen of Light', 'or Chaos Orb + Omen of Whittling (unrevealed only)'],
        },
        'bones': bones,
        'omens': omens,
        'mod_pool': pool,
        'mod_pool_counts': {'exclusive_equipment': count(lambda p: p['pool'] == 'bone_equipment'),
                            'jewel': count(lambda p: p['pool'] == 'cranium_jewel'),
                            'waystone': count(lambda p: p['pool'] == 'vertebrae_waystone'),
                            'altered_collarbone': count(lambda p: p['pool'] == 'altered_collarbone')},
        'patch_history': [
            {'patch': '0.3.0', 'change': 'Abyss league: bones, Well of Souls, desecrated mods, 15 omens', 'confidence': 'high', 'source': PN030},
            {'patch': '0.3.1', 'change': 'Whittling highlights desecrated mods; Unstable Desecration keyword; Well shows more detail', 'confidence': 'high', 'source': PN031},
            {'patch': '0.4.0', 'change': 'Abyss in the core game; Preserved Vertebrae no longer drop; a desecrated movement-penalty mod removed; staff ailment-magnitude mod buffed', 'confidence': 'high', 'source': PN040},
            {'patch': '0.5.0', 'change': 'Instant-leech desecrated mods can no longer roll; Abyss omens only drop in level 65+ areas; "of Union" waystone mod disabled; desecrated mods no longer count as crafted, limit 1 per item', 'confidence': 'high', 'source': PN050},
            {'patch': '1.0 (2026-12-11)', 'change': 'Nothing desecration-specific announced yet', 'confidence': 'medium', 'source': None},
        ],
        'game_text': {'keywords': D['keywords'], 'client_strings': D['client_strings']},
        'sources': [G, PN030, PN031, PN040, PN050, P2DB, VAAL, MAXROLL, 'https://poe2db.tw/us/Omen_of_Abyssal_Echoes',
                    'https://poe2db.tw/us/Omen_of_Putrefaction', 'https://poe2db.tw/us/Altered_Collarbone'],
    }
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    sp = sum(p['spawnable'] for p in pool)
    print(f'wrote {a.out}: {len(bones)} bones, {len(omens)} omens, {len(pool)} mods ({sp} can roll)')


if __name__ == '__main__':
    main()
