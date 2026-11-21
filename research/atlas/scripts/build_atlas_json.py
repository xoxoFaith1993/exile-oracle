"""Build research/atlas/atlas.json from the game data + hand-written research notes.

    python build_atlas_json.py <repoe_dir> <atlas-tree.json> <out atlas.json>

Data parts (waystone mods, tablet mods, tablet bases, node names) come from the files, so re-running this after
the 1.0 re-export refreshes them. Danger ratings, strategy picks, rolling notes and sources are research
annotations (marked with confidence) and live in this file.
"""
import json
import re
import sys
from collections import defaultdict

GAME_VERSION = '0.5.5 (client build 26744644, tables + repoe export of 2026-11-20)'
MARK = re.compile(r'\[([^\]|]*)\|([^\]]*)\]|\[([^\]]*)\]')


def demark(s):
    return MARK.sub(lambda m: m.group(2) if m.group(2) is not None else m.group(3), s or '')


# ---------------------------------------------------------------- waystone mod danger annotations
# key = repoe mod 'type'. level: deadly | risky | fine (for the archetypes listed; 'fine' for everyone else).
# answered_by_stat = the Path of Building / character stat the app should compare.
DANGER = {
    'MapMonsterAccuracy': dict(
        archetypes=['evasion', 'deflection'], answered_by_stat='Evasion / Deflection chance vs monster accuracy',
        level='fine', note='Only lowers evasion/deflect chance; armour/ES builds ignore it.'),
    'MapMonsterArmourBreak': dict(
        archetypes=['armour stackers', 'melee'], answered_by_stat='Armour (after break), physical max hit',
        level='risky', note='Fully broken armour turns physical hits into raw damage; also +19% magic/rare monsters.'),
    'MapMonsterBleeding': dict(
        archetypes=['low regen', 'no bleed immunity'], answered_by_stat='Bleed immunity / Thawing-type charm, life regen',
        level='fine', note='Harmless with bleed immunity; annoying for life builds that kite.'),
    'MapMonsterCritIncrease': dict(
        archetypes=['everyone', 'low max hit', 'ES/CI casters'],
        answered_by_stat='Physical/elemental max hit incl. crits; reduced extra damage from crits',
        level='risky', note='T4 (260-300% crit chance, +26-30% crit damage) makes rares one-shot glass builds; deadly with Painful + Exposure.'),
    'MapMonsterDamageAsChaos': dict(
        archetypes=['low chaos res', 'ES/CI'], answered_by_stat='Chaos resistance, chaos max hit',
        level='risky', note='20-24% extra chaos on every hit at T4; check chaos res before running.'),
    'MapMonsterDamageAsCold': dict(
        archetypes=['low cold res', 'low ailment threshold'], answered_by_stat='Cold resistance (incl. max), cold max hit, freeze threshold',
        level='risky', note='Extra cold also builds freeze.'),
    'MapMonsterDamageAsFire': dict(
        archetypes=['low fire res'], answered_by_stat='Fire resistance (incl. max), fire max hit, ignite threshold',
        level='risky', note='Also +16% monster effectiveness.'),
    'MapMonsterDamageAsLightning': dict(
        archetypes=['low lightning res'], answered_by_stat='Lightning resistance (incl. max), lightning max hit, shock threshold',
        level='risky', note='Shock = more damage taken; stacks badly with Penetrating/Exposure.'),
    'MapMonsterDamageIncrease': dict(
        archetypes=['everyone', 'low max hit'], answered_by_stat='All max-hit values (EHP)',
        level='risky', note='Flat damage up for all monsters; values cut in the 0.5.0 pre-launch patch.'),
    'MapMonsterLifeIncrease': dict(
        archetypes=['low DPS', 'slow clear'], answered_by_stat='DPS / clear speed (time cost, not death)',
        level='fine', note='26-30% more life at T4; costs time, not lives. Gives +23% magic/rare monsters.'),
    'MapMonsterPoisoning': dict(
        archetypes=['low chaos res', 'no poison immunity'], answered_by_stat='Poison immunity / chaos res / regen',
        level='fine', note='Up to 40% poison chance; dangerous only stacked with Profane.'),
    'MapMonsterSpeedIncrease': dict(
        archetypes=['slow melee', 'low max hit', 'hardcore'], answered_by_stat='Max hit + movement speed / dodge-roll safety',
        level='risky', note='10-15% faster monsters at every tier; T1/T2 versions are generation type "unique" in the data.'),
    'MapMonsterStunBuildup': dict(
        archetypes=['casters', 'ES/CI', 'low life'], answered_by_stat='Stun threshold / heavy-stun immunity',
        level='risky', note='100-110% more stun buildup at T4; low-life ES casters get heavy-stunned.'),
    'MapMonstersElementalPenetration': dict(
        archetypes=['everyone (elemental hits)'], answered_by_stat='Max elemental resistances / elemental damage reduction / ele max hit',
        level='deadly', note='14-16% pen at T4 ignores capped res; with Exposure + an extra-element prefix it is the classic one-shot stack. Values cut 2026-05-25 but still top-danger.'),
    'MapMonsterElementAilmentChance': dict(
        archetypes=['low ailment threshold', 'no freeze immunity'], answered_by_stat='Ailment threshold, freeze/shock/ignite immunity',
        level='risky', note='0.5.0 changed it to Elemental Ailment Application (was freeze buildup/shock chance/flammability).'),
    'MapMonsterElementalResistances': dict(
        archetypes=['elemental damage builds'], answered_by_stat='Elemental penetration / exposure / damage (time cost)',
        level='fine', note='35-40% more monster ele res at T4: a DPS tax on elemental builds, not a death risk.'),
    'MapMonsterStunAilmentThreshold': dict(
        archetypes=['ailment builds (freeze, shock, ignite, bleed)', 'stun-lock melee'], answered_by_stat='Ailment magnitude / stun buildup',
        level='fine', note='Cuts freeze/shock lock and heavy-stun uptime; build-dependent DPS loss.'),
    'MapMonstersBaseSelfCriticalMultiplier': dict(
        archetypes=['crit builds'], answered_by_stat='Crit damage share of DPS',
        level='fine', note='26-30% less extra crit damage: DPS loss only.'),
    'MapMonstersCurseEffectOnSelf': dict(
        archetypes=['curse builds (Blood Mage, Hexblast, curse-on-hit)'], answered_by_stat='Curse effect / damage from curses',
        level='fine', note='40-50% less curse effect at T3/T4: DPS and defence loss if curses are core.'),
    'MapPlayerCooldownRecovery': dict(
        archetypes=['cooldown builds (warcries, invocations, triggers, travel skills)'], answered_by_stat='Cooldown recovery rate / reliance on cooldown skills',
        level='risky', note='25-30% less cooldown recovery; defensive cooldowns come back slower.'),
    'MapPlayerFlaskChargeGain': dict(
        archetypes=['life-flask sustain', 'charm users'], answered_by_stat='Flask charge generation / non-flask recovery',
        level='fine', note='30-35% reduced flask charges.'),
    'MapPlayerMaximumResists': dict(
        archetypes=['everyone'], answered_by_stat='Maximum resistances (elemental + chaos) and ele max hit',
        level='deadly', note='-8 to -10% max res at T4 (cut 2026-05-25). Every point of max res is ~10% more ele damage taken near cap.'),
    'MapPlayerRecoveryRate': dict(
        archetypes=['leech / regen / recoup / ES-recharge sustain (e.g. Blood Mage)'], answered_by_stat='Life/ES recovery per second vs incoming DPS',
        level='deadly', note='36-40% less life and ES recovery rate at T3/T4. Sustain builds lose most of their defence.'),
    'MapSpreadBurningGround': dict(
        archetypes=['melee', 'low fire res'], answered_by_stat='Fire res / ignite immunity / movement',
        level='fine', note='Ground patches; +15% monster effectiveness.'),
    'MapSpreadChilledGround': dict(
        archetypes=['melee', 'slow builds'], answered_by_stat='Chill/freeze immunity, movement speed',
        level='fine', note='Slows you; worse with Frostbitten.'),
    'MapSpreadShockedGround': dict(
        archetypes=['melee', 'low lightning res'], answered_by_stat='Shock immunity / lightning res',
        level='risky', note='Shocked = more damage taken; stacks with Thunderous.'),
    'MapMonstersStealCharges': dict(
        archetypes=['charge builds'], answered_by_stat='Reliance on Power/Frenzy/Endurance charges',
        level='fine', note='Generation type "unique" in 0.5.5 data, and 0.5.0 listed Enervating among mods that can no longer roll on waystones: treat as legacy.'),
}

# reward stat ids on waystone mods (0.5.x): every mod = waystone chance + exactly one of the four "reward types"
REWARD_STATS = {
    'map_map_item_drop_chance_+%_final_from_map': 'waystone_chance_more_pct',
    'map_pack_size_+%_final_from_map': 'pack_size_more_pct',
    'map_item_found_rarity_+%_final_from_map': 'item_rarity_more_pct',
    'map_monster_potency_+%_final_from_map': 'monster_effectiveness_more_pct',
    'map_magic_and_rare_monster_rarity_+%_final_from_map': 'monster_rarity_more_pct',
}
# the omen that EXCLUDES each reward type on a Chaos reroll (0.5.0 notes; Quantity = pack size is our inference)
OMEN_BY_REWARD = {'item_rarity_more_pct': 'Omen of Chaotic Rarity', 'pack_size_more_pct': 'Omen of Chaotic Quantity (inferred)',
                  'monster_rarity_more_pct': 'Omen of Chaotic Monsters', 'monster_effectiveness_more_pct': 'Omen of Chaotic Effectiveness'}


def reward_of(mod):
    out = {}
    for s in mod.get('stats', []):
        key = REWARD_STATS.get(s['id'])
        if key:
            out[key] = s['max']
        elif 'rarity' in s['id'] and 'item' in s['id'] and 'final' in s['id']:
            out['item_rarity_more_pct'] = s['max']
        elif 'magic' in s['id'] and 'rare' in s['id'] and 'final' in s['id']:
            out['monster_rarity_more_pct'] = s['max']
    txt = demark(mod.get('text', ''))
    # fallback: read the reward lines from the text (covers stat ids we did not list)
    for pat, key in ((r'(\d+)% more Waystones found', 'waystone_chance_more_pct'), (r'(\d+)% more Pack size', 'pack_size_more_pct'),
                     (r'(\d+)% more Rarity of Items', 'item_rarity_more_pct'), (r'(\d+)% more Effectiveness', 'monster_effectiveness_more_pct'),
                     (r'(\d+)% more Magic and Rare Monsters', 'monster_rarity_more_pct')):
        m = re.search(pat, txt)
        if m and key not in out:
            out[key] = int(m.group(1))
    if 'monster_rarity_more_pct' in out:
        out['note'] = 'Monster Rarity = more magic and rare monsters AND the same % more chance of rare monster modifiers'
    return out


def waystone_mods(mods):
    fam = defaultdict(list)
    for mid, m in mods.items():
        if m.get('domain') != 'area':
            continue
        tiers = [w['tag'] for w in m.get('spawn_weights', []) if w['weight'] > 0 and w['tag'].startswith('map_key_')]
        if tiers:
            fam[m['type']].append((mid, m, tiers[0]))
    order = {'map_key_low': 1, 'map_key_medium': 2, 'map_key_high': 3, 'map_key_highest': 4}
    tier_span = {'map_key_low': 'Waystone T1-5', 'map_key_medium': 'T6-10', 'map_key_high': 'T11-15', 'map_key_highest': 'T16'}
    out = []
    for typ, rows in sorted(fam.items()):
        rows.sort(key=lambda r: order[r[2]])
        last = rows[-1][1]
        lines = [l for l in demark(last.get('text', '')).split('\n') if l]
        gen = {r[1]['generation_type'] for r in rows}
        kind = 'prefix' if 'prefix' in gen else 'suffix' if 'suffix' in gen else sorted(gen)[0]
        d = DANGER.get(typ, {})
        out.append({
            'mod_text': lines[0] if lines else typ,
            'mod_id_or_group': typ, 'mod_ids': [r[0] for r in rows], 'affix_name': last.get('name'),
            'kind': kind,
            'generation_types_in_data': sorted(gen),
            'reward': reward_of(last),
            'danger': {'archetypes': d.get('archetypes', []), 'answered_by_stat': d.get('answered_by_stat'),
                       'level': d.get('level', 'unrated'), 'note': d.get('note')},
            'tiers': [{'tier_band': tier_span[r[2]], 'mod_id': r[0],
                       'effect': demark(r[1].get('text', '')).split('\n')[0]} for r in rows],
            'source': 'game data: repoe mods.min.json domain=area, spawn tags map_key_low/medium/high/highest; '
                      'cross-checked 108/108 against client Mods.datc64 build 26744644. Danger = Claude analysis.',
            'confidence': {'text_tiers_reward': 'high (game data)', 'danger': 'medium (estimated from mechanics)'},
        })
    return out


def desecrated_waystone_mods(mods):
    out = []
    for mid, m in mods.items():
        if m.get('domain') == 'desecrated' and any(w['tag'] == 'map' and w['weight'] > 0 for w in m.get('spawn_weights', [])):
            out.append({'mod_id': mid, 'kind': m['generation_type'], 'affix_name': m.get('name'),
                        'mod_text': demark(m.get('text', '')).replace('\n', ' / ')})
    return out


def instilled(mods):
    names = ['Ire', 'Guilt', 'Greed', 'Paranoia', 'Envy', 'Disgust', 'Despair', 'Fear', 'Suffering',
             'Isolation (also Melancholy, Ferocity, Contempt)']
    out = []
    for i, n in enumerate(names, 1):
        m = mods.get(f'InstilledMapDelirium{i}')
        if m:
            out.append({'emotion': n, 'mod_id': f'InstilledMapDelirium{i}', 'effect': demark(m.get('text', '')).replace('\n', ' / ')})
    return out


def tablets(mods, bases):
    by_tag = defaultdict(list)
    for mid, m in mods.items():
        if m.get('domain') != 'tablet':
            continue
        tags = [w['tag'] for w in m.get('spawn_weights', []) if w['weight'] > 0] or ['(no spawn tag: unique/implicit/disabled)']
        for t in tags:
            by_tag[t].append({'mod_id': mid, 'kind': m['generation_type'], 'affix_name': m.get('name'),
                              'text': demark(m.get('text', '')).replace('\n', ' / ')})
    types = []
    for k, b in bases.items():
        if b.get('item_class') == 'TowerAugmentation':
            tag = [t for t in b['tags'] if t.startswith('tower_augment_')][0]
            imp = b.get('implicits') or []
            types.append({'name': b['name'], 'base_id': k, 'tag': tag,
                          'implicit': demark(mods.get(imp[0], {}).get('text', '')).replace('\n', ' / ') if imp else None,
                          'own_suffixes': by_tag.get(tag, [])})
    return types, by_tag.get('default', []), by_tag.get('(no spawn tag: unique/implicit/disabled)', [])


# ---------------------------------------------------------------- strategies (node names checked against the tree)
S = lambda name, why: {'name': name, 'why': why}
STRATEGIES = [
    {'name': 'Juiced generic (rarity + monster density)',
     'mechanics': ['rare/magic monsters', 'waystone mods', 'tablets'],
     'key_nodes': [S('The Journey Ahead', 'choice: 6% pack size / 15% effectiveness / 10% rarity'),
                   S('Rising Danger', '20% increased rare monsters'), S('Bountiful Bloodlines', '20% increased magic monsters'),
                   S('Expanding Hordes', 'magic pack size +10%'), S('Multiplying Monstrosities', 'magic pack size +10%'),
                   S('Twin Threats', '1 rare per area duplicated'),
                   S('Adaptive Biology', '+1 max rare monster mods; each mod >=100% rarity'),
                   S('Mutating Monsters', '+1 max rare monster mods; each mod >=100% rarity'),
                   S('No Simple Battles', 'rares have at least 3 mods, each >=100% rarity'),
                   S('Nemesis Rising', 'choice: rare effectiveness / mods / extra rare / 10% rare rarity'),
                   S('To the Strong Go the Spoils', '2% rarity per monster modifier'),
                   S('Risk and Reward', '2% rarity per explicit map modifier'),
                   S('Enigmatic Intensification', '3% more waystone explicit effect per tablet'),
                   S('Controlled Climates', '5% tablet explicit effect per tablet'),
                   S('Industrial Improvements', '4th tablet slot on City maps'),
                   S('Grass Mastery', 'choice: 10% basic->greater or 5% greater->perfect currency'),
                   S('Swamp Mastery', 'choice: 25% Chaos drop as Exalted (or pack size)')],
     'tablets': ['3x same-mechanic tablet or generic tablets with Collector\'s (rarity), Brimming (rares), Breeding (pack size), Abounding (monster rarity)'],
     'waystone_setup': 'Rare, 6 mods (Alchemy + Exalts), instilled Liquid Paranoia/Greed, avoid the deadly list; masters: Doryani Evolutionary Pressure + Improved Calibration, Hilda Breeding Season + Ancient Inscriptions.',
     'source': 'node picks: Claude from 0.5.5 node texts; direction: Boostmatch 0.5.0 guide (2026-05-28, used 0.4 names), Timesaver atlas guide (2026-08-09)',
     'version': '0.5.5', 'confidence': 'medium (node effects = data; ranking = estimate)'},
    {'name': 'Breach', 'mechanics': ['Breach', 'Hives', 'Genesis Tree (Wombgifts, Hiveblood)', 'Vruun'],
     'key_nodes': [S('Shape the Chains', 'choice: Grow Quantity = Breaches +15% pack size'), S('Swelling Hives', 'extra Hive wave'),
                   S('Moment of Risk', '2 extra rares when stabilised; wombgift level-up per map mod'),
                   S('Frantic Invasion', '100% more chance of Vruun'), S('Study the Chains', 'Vruun 50% more Lineage Supports'),
                   S('Breeding Program', 'choice: target Wombgift type'), S('Growing Wealth', '+5 Genesis points (Currency Womb)'),
                   S('Reactive Hiveseeding', '10% chance to add a Hive nearby'), S('Tear Open the Rift', 'choice: Breach stronghold adds map mods'),
                   S('Reality Wound', '+10 s before unstable breaches collapse')],
     'tablets': ['Breach Tablet: of the Horde (5-15% pack size), of the Form (wombgift qty 30-60%), of the Flesh (wombgift level), of the Invasion (+1-2 rares), of the Commander (Vruun)'],
     'waystone_setup': 'Pack-size + monster-rarity mods; 2-3 Breach tablets; 0.5.5 tier list puts Breach in B tier (3-7 div/h).',
     'source': 'node texts: game data 0.5.5; tier: Timesaver 0.5.4 tier list (2026-06-28/08-07)', 'version': '0.5.5', 'confidence': 'medium'},
    {'name': 'Ritual', 'mechanics': ['Ritual altars', 'Tribute', 'Favours (omens, uniques)', 'Audience with the King', 'Rite of the Nameless'],
     'key_nodes': [S('Tempting Offers', '+1 favour reroll'), S('Magnanimous Offerings', '20% free rerolls'),
                   S('Patient Devotion', 'deferred favours 50% sooner, 50% cheaper'), S('From the Mists', 'extra Wildwood pack per Ritual'),
                   S('Reborn in Shadow', 'revived monsters more often magic/rare = more tribute'),
                   S('Mysterious Rites', '8% Queen\'s Ritual: +10 omens in first favour set'), S('Traveller\'s Woe', 'choice: ritual type'),
                   S('Invigorated Sacrifices', 'choice: tribute/favour tweaks'), S('Spreading Darkness', 'unique item slot type by ritual type'),
                   S('Royal Tithe', 'King progress'), S('Prayer and Pledge', 'King progress from spent tribute'),
                   S('Hour of the Nameless', 'Rite of the Nameless can offer valuable uniques')],
     'tablets': ['Ritual Tablet: of Sacrifice (18-30% tribute), of Omens (35-70% omen chance), of Prayers (+1-3 rerolls), of the Dogma/Occult/Devotion/Appeal (cheaper/free rerolls & defers). 0.5.5: >1 Ritual tablet adds an extra altar.'],
     'waystone_setup': 'Pack size and magic/rare monster mods (more tribute); item rarity does not affect favours. A-tier in 0.5.4 (4-12 div/h, omen-driven).',
     'source': 'node texts: game data; tribute logic: AOEAH 0.5 Ritual guide (2026-06-01, several node names wrong); tier: Timesaver 0.5.4',
     'version': '0.5.5', 'confidence': 'medium'},
    {'name': 'Delirium', 'mechanics': ['Delirium fog', 'Fracturing / Grand mirrors', 'Simulacrum', 'Liquid emotions'],
     'key_nodes': [S('The mirrors... the mirrors!', '50% more fracturing mirrors'), S("Is that the best you've got?!", 'more escalation shards'),
                   S('Come on! Face me!', 'more unique boss shards; kills pause timer'), S('Get out of my head!', 'magic monsters extra delirium mod'),
                   S('These demons are all your own...', 'rares always manifest demons'), S('I know your childhood fears...', 'more liquid emotions, 20% ancient'),
                   S("You can't scare me anymore!", 'uniques drop potent emotions'), S('Is this about me... or you?', 'Simulacrum splinters in 75+ maps'),
                   S('Recurring Nightmares', 'choice: +30% deliriousness or fog spreads to +4 maps')],
     'tablets': ['Delirium Tablet: of Mirrors, of Shattering, of Phobia (unique bosses), of the Simulacrum (splinter stack), of Persecution (pack size), of Eternity/of the Unending (longer fog), of Freeze Time'],
     'waystone_setup': 'High-rarity rares; build must handle deliriousness. C-tier/spiky (3-9 div/h) in 0.5.4; highest ceiling, build-gated.',
     'source': 'node texts: game data; tier: Timesaver 0.5.4', 'version': '0.5.5', 'confidence': 'medium'},
    {'name': 'Expedition / Grand Expedition', 'mechanics': ['Expedition', 'Verisium Remnants', 'Logbooks', 'Grand Expedition bosses'],
     'key_nodes': [S('Calculated Investment', 'choice: 1% item quantity per runic modifier'), S('Double or Nothing', 'choice: 25% chance extra runic mod'),
                   S('Expanding Territory', 'choice: +remnant or +25% expedition chance'), S('Steady Development', 'choice: extra remnant or explosive'),
                   S('Strategic Advantage', 'choice: faster or stronger explosives'), S('Sown Seeds', 'logbooks per runic mod'),
                   S('Gaining Traction', 'remnant monster rarity stacking'), S('Feeling Lucky?', 'Farrow sells Liquid Verisium'),
                   S('The Quest Continues', 'Grand Expeditions up to 3 mods, +1 area level')],
     'tablets': ['Expedition Tablet: of Runes (more runic markers), of Knowledge (logbooks), of Power (rarity), of Twins, of Remnants, of Ancient Evil, of Verisium, of Treasure (buried strongboxes)'],
     'waystone_setup': 'Any layout; rarity/monster-rarity mods. S-tier in 0.5.4 (10-20 div/h claimed; 50 = optimized ceiling). Subtree points from Grand Expedition bosses (0.5.4). Hilda Scarred Lands, Jado Eastern Knowledge.',
     'source': 'node texts: game data; tier & points: Timesaver 0.5.4, PCGamesN/allthings 0.5.4 notes coverage', 'version': '0.5.5', 'confidence': 'medium'},
    {'name': 'Abyss', 'mechanics': ['Abysses, pits, Abyssal Depths', 'Desecrated currency', 'Abyssal factions'],
     'key_nodes': [S('Balance of Power', 'choice: faction (Ulaman recommended for currency)'), S('Strange Aversions', 'Ulaman may have currency chests'),
                   S('From Below', '+1 pit'), S('Dark Depths', 'chance for 2-4 extra pits'), S('Sprawling Rupture', '25% more abyss monsters'),
                   S('Lord of the Pit', 'choice: scatter pits / effectiveness per pit / extra abyss'), S('Vile Treasures', 'choice: eyes / omens / lineage'),
                   S('Rotting Bones', 'ancient desecrated currency'), S('Close to the Surface', 'waystone mods apply in Depths'),
                   S('Shadow of Undeath', 'abyss-influenced essences and rogue exiles'), S('Abyssal Ire', 'bosses in 78+ Depths')],
     'tablets': ['Abyss Tablet (0.5.0: only enables Abyss): of Hollows (+1 abyss), of Schisms (20-40% chance +4), of Treasures (pits twice as likely rewards), of the Horde, of Champions (+2-3 rares), of Dark Power, of Ossification (desecrated currency)'],
     'waystone_setup': 'Desecrated Abyssal prefixes (e.g. Abysses lead to Depths / overrun) if available; keep revives. A-tier (4-10 div/h) in 0.5.4; most consistent floor in 0.5.3.',
     'source': 'node texts: game data; AOEAH Abyss guide (2026-06-03, unverified claims); Timesaver 0.5.3/0.5.4', 'version': '0.5.5', 'confidence': 'medium'},
    {'name': 'Essence', 'mechanics': ['Essence monsters', 'Essence corruption'],
     'key_nodes': [S('The Chosen Path', 'choice: Essences = 100% more essences'), S('Essence Dowsing', 'choice: target Greater/Perfect essence types'),
                   S('Crystalline Patterns', 'choice: second essence-type pick'), S('Inexplicable Alchemy', 'Exalted Orb adds an essence to an essence monster'),
                   S('Crystalline Overgrowth', '15% extra essence'), S('Intensifying Energies', 'extra essence chance per map mod'),
                   S('Flawless Patterns', '30% more Perfect essences'), S('Corrupted Lattices', 'choice: corruption behaviour'),
                   S('Harmonic Corruption', '37% double corruption'), S('Overlord\'s Domain', 'choice: extra essence with powerful bosses')],
     'tablets': ['Overseer Tablet (+ of Crystals: 1-2 essences); any tablet with the Crystallised prefix (+1 essence) or of the Essence suffix'],
     'waystone_setup': 'Desert/Vaal-city biomes (Arid Stability, Monuments in Time); Doryani Archaic Corruption, Stitch the Flesh.',
     'source': 'node texts: game data; AOEAH Essence guide (2026-06-08, seller site)', 'version': '0.5.5', 'confidence': 'medium-low'},
    {'name': 'Boss / Citadel', 'mechanics': ['Map bosses', 'Powerful Map Bosses', 'Citadels', 'Pinnacles'],
     'key_nodes': [S('Fit for a King', '20% boss rarity'), S('Hard-Won Treasures', '15% boss quantity'), S('Pathkeepers', '15% boss waystone quantity'),
                   S('Overlord\'s Domain', 'choice: extra content with powerful bosses'), S('Overlord\'s Influence', 'choice: extra content with powerful bosses'),
                   S('Fabled Showdown', 'choice: Favour the Villain = shrine on boss for extra reward'), S('Eons of Domination', 'Overseer tablets drop from powerful bosses'),
                   S('Runic Flare', 'summoning circles upgrade nearby bosses'), S('Memories of the Vaal', 'anomaly bosses extra lineage support (also Maraketh/Ezomytes/Karui)'),
                   S('Warlord\'s Vendetta', 'invaded cities: citadel boss'), S('Bring Me Your Leader', 'city summoning circles: citadel boss')],
     'tablets': ['Overseer Tablet: of Hoards (13-20% boss quantity), of Treasure (35-60% boss rarity), of Pathways (18-30% boss waystones), of Conquering (xp)'],
     'waystone_setup': 'Masters: Hilda Mighty Prey + Patient Battue + Claimed Territories, Jado In The Wrong Hands, Doryani Head of the Snake.',
     'source': 'node + master texts: game data 0.5.5', 'version': '0.5.5', 'confidence': 'medium'},
    {'name': 'Strongbox', 'mechanics': ['Strongboxes', 'Unique strongboxes'],
     'key_nodes': [S('The Chosen Path', 'choice: Strongboxes'), S('Intriguing Designs', 'no Basic strongboxes'),
                   S('Specialised Containers', 'extra item-type prefixes on Arcane/Cartographer/Jeweller/Researcher'),
                   S('Enchanted Locks', '+1 prefix'), S('Inlaid Inscriptions', '+1 suffix'), S('Bardiyan Craftsmanship', '+1 suffix'),
                   S('Royal Craftsmanship', 'greater suffixes'), S('An Appropriate Vault', '2% quantity per mod'),
                   S('Hidden Compartments', '15% openable twice'), S('Craftsman\'s Creed', 'choice: attribute prefixes'),
                   S('Overlord\'s Influence', 'choice: extra strongbox')],
     'tablets': ['any tablet with of the Antiquarian (+1 strongbox) / of Strongboxes; Overseer of Compartments (1-2)'],
     'waystone_setup': 'Jado Trove Seekers (100% more unique strongboxes), Mysterious Gifts, Stolen Relics; Doryani Mechanical Guardians; Mountain biome Favoured Treasures.',
     'source': 'node + master texts: game data 0.5.5', 'version': '0.5.5', 'confidence': 'medium-low (no 0.5 guide found)'},
    {'name': 'Rogue Exile', 'mechanics': ['Rogue Exiles (gear, uniques, waystones, tablets)'],
     'key_nodes': [S('The Chosen Path', 'choice: Rogue Exiles'), S('Wealthy Exiles', '25% rarity'), S('Here for the Same Reason', '6% rarity per map mod'),
                   S('Uncommon Alliances', '10% pairs'), S('Famous Locals', 'city pairs'), S('The Deadliest Hunt', 'more equipped uniques'),
                   S('Legendary Duels', 'choice: unique slot type'), S('Competing Explorers', '+waystone drop'), S('Competitive Archaeology', '+tablet drop'),
                   S('Dressed in Fineries', 'exceptional items'), S('Man Trap', 'essence monsters become exiles'), S('Overlord\'s Domain', 'choice: extra exile')],
     'tablets': ['Exiled prefix (+1 exile), of the Exile suffix (70-100% chance)'],
     'waystone_setup': 'Hilda Dangerous Game (exiles flee and upgrade). Pairs with Abyss (Shadow of Undeath).',
     'source': 'node texts: game data; AOEAH Abyss guide mentions exile synergy', 'version': '0.5.5', 'confidence': 'medium-low'},
    {'name': 'Temple (Atziri / Fate of the Vaal)', 'mechanics': ['Vaal Beacons', 'Temple rooms', "Atziri's Vault"],
     'key_nodes': [S("Atziri's Assets", 'choice: extra vault reward type'), S('Training and Preparation', '+1 temple area level'),
                   S('Transcendent Progress', 'tier 4 rooms'), S('Power Relays', '10% room modifier effect'), S('Efficient Arteries', '15% effect from 4-adjacent rooms'),
                   S("Xipocado's Machinations", '1% effect per different room'), S('Expanded Designs', 'extra restricted room'),
                   S('Protected Treasures', 'restricted rooms extra chests'), S('Riches of the Empire', '15% temple currency duplicated'),
                   S('Stolen Authority', '35% more medallions')],
     'tablets': ['Temple Tablet (guarantees Vaal Beacons; suffixes: extra packs, beacon uniques, crystal chance)'],
     'waystone_setup': 'Area level 75+ required to be worthwhile; S-tier steady (3-8 div/h) in 0.5.4.',
     'source': 'node texts: game data; tier: Timesaver 0.5.4', 'version': '0.5.5', 'confidence': 'medium'},
]

TREE_NOTES = {
    'files': {
        'graph': 'metadata/atlasskillgraphs/atlasskillgraph.psg (inside the game bundles; extract with poe2x: '
                 'poe2x extract <PoE2>\\Bundles2\\_.index.bin <out> metadata/atlasskillgraphs). Not in the tables folder.',
        'nodes': 'tables/passiveskills.json rows with SkillType == 1 (1734 rows; only the ~575 present in the .psg are live).',
        'stats': 'tables/stats.json (Stats indices) + data/statdescriptions/atlas_stat_descriptions.csd, endgame_map_stat_descriptions.csd, '
                 'map_stat_descriptions.csd and atlas_variant_stat_descriptions.csd for the English text (UTF-16 .csd, extract with poe2x).',
        'subtrees': 'tables/atlaspassiveskillsubtrees.json: index used by PassiveSkills.AtlasSubTree (0 Breach, 1 Expedition, 2 Delirium, '
                    '3 Ritual, 4 Abyss, 5 Incursion/Temple); each has a UI background and "Grants X Atlas passive points on completion".',
        'choices': 'tables/passiveskillvarianttypes.json (Id == the keystone Id) + passiveskillvariants.json (Type -> Variant = PassiveSkills row) '
                   'give the options of "Select a bonus" keystones; PassiveSkills.VariantType points at the variant type.',
        'masters': 'tables/atlasclasspassives.json (36 rows: Jado/Doryani/Hilda x 12 keystones, Stats + StatValues) and atlasclasspassiveclasses.json.',
        'tree_type': 'tables/passiveskilltrees.json row "Atlas" -> Metadata/AtlasSkillGraphs/AtlasSkillGraph; "EndgameMap" -> the Fortress layout graph.',
    },
    'psg_format': 'v3: u8 version, u8 ?, u8 orbit_count, u8[orbit_count] skills_per_orbit (1,12,24,24,72,72,72,24,72,144); '
                  'u32 root_count + (u32 graph_id, u32 0) each; u32 group_count; per group f32 x, f32 y, u32 flags, u32 ?, u8 ?, u32 node_count; '
                  'per node u32 graph_id, u32 orbit, u32 orbit_index, u32 conn_count + (u32 graph_id, i32 curvature) each. graph_id = PassiveSkills.PassiveSkillGraphId.',
    'positions': 'node = group (x,y) + orbit radius at angle 2*pi*index/skills_per_orbit (x += r*sin, y -= r*cos). Radii assumed equal to the '
                 'character tree (0,82,162,335,493,662,846,251,1080,1322); a test render looks right (symmetric main tree, 6 separate subtrees).',
    'links': 'connections are stored once (directed in the file); treat as undirected. curvature != 0 means an arc (orbit link).',
    'roots': 'AtlasGenericStart (main tree, centre) + 6 subtree roots (AtlasRitualStart, AtlasBreachStart, AtlasDeliriumStart, AtlasAbyssStart, '
             'AtlasIncursionStart_, AtlasExpeditionStart). Allocation must connect to a root of the same tree.',
    'gates': 'PassiveSkills.Requirement = a PassiveSkills row of a Fortress map node (AtlasInsideFortress..., from the EndgameMap graph): the node needs '
             'that Fortress map done. PassiveSkills._unk67 = area level gate (70 or 75): 307 nodes ungated, 141 need AL70, 127 need AL75.',
    'decor': '38 AtlasGenericMastery* nodes are isolated art only; skip them for allocation.',
    'counts_0_5_5': {'nodes': 575, 'links': 586, 'groups': 255, 'main': 375, 'Ritual': 37, 'Incursion': 37, 'Abyss': 36, 'Breach': 33,
                     'Delirium': 32, 'Expedition': 25, 'notables': 224, 'keystones_incl_choice': 44, 'choice_keystones': 44},
    'points': 'Main tree: points from Fortress maps (1+ each, official 0.5.0), +4 per Precursor Tower and 6+ per pinnacle (guides); killing the Arbiter '
              'of Divinity 5x completes Fortress maps (official). Enough points exist to allocate the whole tree, so respec is gone (only choice '
              'nodes can be switched). Subtrees: points from that mechanic\'s questline/boss (Expedition: Grand Expedition bosses, 0.5.4).',
    'output': 'scripts/atlas_tree.py writes atlas-tree-26744644.json (nodes with x/y, text, choices, gates; links; groups).',
    'version': '0.5.5 build 26744644', 'confidence': 'high (parsed from the client; area-level meaning of _unk67 inferred from 70/75 values + guide)',
}

ROLLING = [
    {'method': 'White (normal) waystone', 'cost_note': '0', 'expected_reward': 'no mod rewards; most revives; safest',
     'when': 'build not yet able to take mods, or sustain is fine without mods', 'source': 'mechanics', 'confidence': 'high'},
    {'method': 'Magic (Transmute + Augment)', 'cost_note': '~2 ex at 2026-11-21 prices (Transmute 1.15 ex, Aug 1.0 ex)',
     'expected_reward': '1 prefix + 1 suffix at T16, average: ~30% more waystones, ~5% pack size, ~9% item rarity, ~6% monster rarity, ~5% effectiveness',
     'when': 'early maps, Waystone sustain', 'source': 'computed from game data (equal weights)', 'confidence': 'medium'},
    {'method': 'Rare: Alchemy (4 mods) + Exalted to 6', 'cost_note': '~6 ex (Alchemy 4.2 ex + 2 Exalted 1 ex each); Regal on magic 0.9 ex',
     'expected_reward': '3P+3S at T16, average: ~89% more waystones, ~15% pack size, ~28% item rarity, ~19% monster rarity, ~16% effectiveness '
                        '(additive between waystone mods, multiplicative with atlas bonuses); 4-mod Alchemy alone ~2/3 of that',
     'when': 'default for any build that survives 6 mods; costs revives', 'source': '0.5.0 patch notes (reward/multiplicative); prices: poe.ninja via toolkit DB', 'confidence': 'medium'},
    {'method': 'Chaos Orb (swap one random mod)', 'cost_note': '~41 ex', 'expected_reward': 'replaces 1 mod; only to remove a deadly mod on an otherwise good stone',
     'when': 'rarely worth it vs a fresh Alchemy (4.2 ex) unless the stone is corrupted/instilled', 'source': 'PoE 2 Chaos Orb behaviour', 'confidence': 'medium'},
    {'method': 'Chaos + Omens of Chaotic X (up to 3 active)', 'cost_note': 'Omens: Rarity ~251 ex, Quantity ~350 ex, Monsters ~37 ex, Effectiveness ~120 ex (+41 ex Chaos)',
     'expected_reward': 'rerolls ALL mods excluding the omen\'s reward type; 3 omens force every mod into the 4th type (e.g. all rarity mods)',
     'when': 'only for top juicers whose map yield is several divines; never at league start', 'source': '0.5.0 patch notes (omen rework); prices snapshot', 'confidence': 'medium (Quantity = pack size is inferred)'},
    {'method': 'Vaal Orb (corrupt)', 'cost_note': '~9 ex',
     'expected_reward': 'community: 4 outcomes ~25% each: nothing / tier +-1 with rerolled mods / one side locked + other reforged / both locked + 0-4 extra mods (up to 10). '
                        'Jado "Unexpected Missions": corrupted waystones open maps with +1 random modifier.',
     'when': 'on finished 6-mod T15/T16 rares when you can afford to lose the tier; corrupted stones cannot be changed after',
     'source': 'U4N (2025-07-28, updated 2026-11-21), Maxroll corruption page (2026-05-24); odds not confirmed for 0.5', 'confidence': 'low-medium'},
    {'method': 'Instill Liquid Emotions', 'cost_note': 'Diluted Greed ~1 ex, Liquid Paranoia ~2.2 ex, Envy ~0.3 ex, Disgust ~2.8 ex, Despair ~11 ex',
     'expected_reward': 'see instilled list: Greed 8% rarity, Paranoia 15% rare monsters, Envy 30% waystones, Disgust 30% tablets; each adds deliriousness',
     'when': 'cheap: almost always worth it on rares you keep', 'source': 'game data (BlightCraftingItems -> InstilledMapDelirium mods); prices snapshot', 'confidence': 'high (effects), low (how many per waystone in 0.5)'},
    {'method': 'Desecrate (Abyssal bone) a rare waystone', 'cost_note': 'bone prices vary (Gnawed Jawbone ~1.6 ex ... Ancient ones are thousands)',
     'expected_reward': 'adds an Abyssal prefix (more abysses, depths, magic packs) or a nasty suffix (of Cycling / Deceleration / Retribution)',
     'when': 'Abyss farming', 'source': 'game data desecrated domain + poe2db (Preserved Vertebrae desecrates rare waystones)', 'confidence': 'medium'},
    {'method': 'Orb of Chance on tablets', 'cost_note': '~27 ex', 'expected_reward': 'chance at a unique tablet', 'when': 'cheap normal tablets only',
     'source': '0.5.0 patch notes', 'confidence': 'high (allowed), low (value)'},
    {'method': 'When re-rolling beats running', 'cost_note': '-',
     'expected_reward': 'Rule of thumb (estimate): fill every kept T15/T16 to 6 mods (cost ~6 ex is small vs map yield) unless a mod is deadly for the build; '
                        'Chaos/Annul only when the waystone already carries > ~1 div of investment (instills, corruption). Below T15, run, do not reroll.',
     'when': 'see text', 'source': 'Claude estimate from snapshot prices', 'confidence': 'low'},
]

SEARCH_BOX = {
    'max_len': 250,
    'max_len_note': 'Official 0.5.0 patch notes: "Search textbox maximum length increased to 250 characters" (was 50; several mid-2026 guides still say 50). Verify in client.',
    'syntax': {
        'terms': 'space-separated terms must all match (AND); a quoted string is one term and may contain spaces',
        'negation': 'a leading ! excludes items matching that term (e.g. "!term" or "!a|b" excludes either)',
        'alternation': '| inside a term = OR; parentheses group alternatives',
        'regex': 'regular expressions are supported inside a term: . .+ * [a-z] [0-9] \\ escape, ^ $ anchors (anchor support assumed from PoE 1)',
        'case': 'case-insensitive (PoE 1 behaviour, widely reported; verify)',
        'matched_text': 'since 0.5.0 searching by item text matches the ADVANCED description format (the Ctrl+Alt+C text), which includes affix '
                        'names/tiers; patterns written against the plain text may need adjusting',
    },
    'quirks': [
        'quotes, spaces and ! count toward the 250 characters',
        'numbers are text: ranges must be built from digit classes (e.g. a 2-digit value 40-99 needs [4-9]. )',
        'short fragments can hit other mods: test each fragment against the full waystone mod list (the generator should check uniqueness)',
        'the same search box exists in stash and vendor windows; the Atlas screen has its own live search (names, biomes, bosses, content words)',
        'property lines (e.g. revives available, monster pack size, item rarity totals) can be matched on 0.4-era waystones; confirm the 0.5 line names from a copied waystone before relying on them',
    ],
    'common_patterns_described': [
        'avoid-list: one negated alternation of short unique fragments of the deadly mod texts (Exposure, Smothering/Recovery Rate, Penetrates, crit chance)',
        'want-list: positive fragments for pack size / rarity / rare monsters, or value thresholds on the summary lines',
        'six-mod finder: match "revives available: 0" style lines (forum guide, 2025-09/2026-01)',
    ],
    'sources': ['https://www.pathofexile.com/forum/view-thread/3932540 (0.5.0 patch notes, 250 chars, advanced format)',
                'https://www.pathofexile.com/forum/view-thread/3858429 (player regex guide, 2025-09-22, edited 2026-01-06)',
                'https://maxroll.gg/poe2/resources/rolling-waystones-and-precursor-tablets (quoted terms with |)'],
    'licence_note': 'poe.re / poe2.re are AGPL-3.0: describe syntax only, never copy their patterns or code.',
}

V1_WATCHLIST = [
    {'date': '2026-11-06', 'item': '1.0 launches Dec 11 PST; full patch notes about a week before (~Dec 4). Re-export the atlas tree, waystone and tablet mods then.', 'source': 'GGG Steam announcement 2026-11-06', 'confidence': 'high'},
    {'date': '2026-11-06', 'item': 'Conquerors of Wraeclast league: castles, factions, "delegate Atlas progression to your own commanders" (real-time endgame system); hunting-ground maps around a castle reset when it changes hands.', 'source': 'GGG Steam announcement; Maxroll ExileCon recap (2026-11-09)', 'confidence': 'high'},
    {'date': '2026-11-09', 'item': '"No plans for major difficulty increase in the endgame for 1.0"; Mark Roberts likes fewer deaths per area and more waystone modifiers (current revive/mod system likely stays).', 'source': 'Maxroll ExileCon 2026 recap', 'confidence': 'medium'},
    {'date': '2026-11-09', 'item': 'Multichoice nodes still exist on the Atlas Passive Skill Tree in 1.0; questline locations teleportable once unlocked; league mechanics keep fixed Atlas locations; mechanic unlocks slowed.', 'source': 'Maxroll ExileCon 2026 recap', 'confidence': 'medium'},
    {'date': '2026-11-09', 'item': 'Champion Rares (campaign) "might be added to the endgame"; Trial of the Ancestors and Sekhemas rework come after 1.0.', 'source': 'Maxroll ExileCon 2026 recap', 'confidence': 'medium'},
    {'date': '2026-11-15', 'item': 'Rogers: late endgame was "getting stale" (same builds, jewel sockets); passive tree rework moves sockets into clusters. No statement found on waystone/tablet mod changes.', 'source': 'UnGeek interview 2026-11-15', 'confidence': 'medium'},
    {'date': 'expect', 'item': 'Things to re-check on 1.0 data: waystone mod list + reward values, tablet types (new league tablet?), Atlas tree node ids/positions, master keystones, search box limit.', 'source': 'Claude', 'confidence': 'n/a'},
]

SOURCES = [
    {'id': 'game', 'what': 'PoE 2 client build 26744644 (0.5.5): passiveskills, atlas tables, Mods, atlasskillgraph.psg, stat descriptions', 'date': '2026-11-20 extract'},
    {'id': 'repoe', 'what': 'repoe-fork poe2 export (mods.min.json, base_items.min.json)', 'date': '2026-11-20'},
    {'id': 'ggg-050', 'url': 'https://www.pathofexile.com/forum/view-thread/3932540', 'what': 'Content Update 0.5.0 patch notes', 'date': '2026-05-21/25'},
    {'id': 'ggg-1.0', 'url': 'https://store.steampowered.com/news/app/2694490/view/698779962638862661', 'what': 'Full release announcement', 'date': '2026-11-06'},
    {'id': 'poe2db-055d', 'url': 'https://poe2db.tw/Version_0.5.5d', 'what': '0.5.5d notes (3 tablet slots fix)', 'date': '2026-09'},
    {'id': 'poe2db-waystones', 'url': 'https://poe2db.tw/us/Waystones', 'what': 'waystone mods, desecrated mods, revivals rule', 'date': 'n/d (0.5)'},
    {'id': 'maxroll-exilecon', 'url': 'https://maxroll.gg/poe2/news/exilecon-2026-recap', 'what': 'ExileCon 2026 recap', 'date': '2026-11-09'},
    {'id': 'ungeek', 'url': 'https://www.ungeek.ph/2026/11/interview-path-of-exile-2-director-jonathan-rogers-on-version-1-0s-big-changes-and-what-reworks-didnt-make-the-cut/', 'what': 'Rogers interview', 'date': '2026-11-15'},
    {'id': 'timesaver-tier', 'url': 'https://timesaver.gg/blog/poe2-0-5-4-currency-farming-tier-list', 'what': '0.5.4 currency tier list', 'date': '2026-06-28 / 08-07'},
    {'id': 'timesaver-atlas', 'url': 'https://timesaver.gg/blog/poe2-atlas-tree-currency-farming-guide', 'what': 'atlas tree farming guide', 'date': '2026-08-09'},
    {'id': 'boostmatch', 'url': 'https://boostmatch.gg/blog/poe-2/articles/poe2-atlas-tree-guide-0-5-0-return-of-the-ancients', 'what': 'pre-launch atlas guide (uses 0.4 / invented node names)', 'date': '2026-05-28'},
    {'id': 'domistae', 'url': 'https://domistae.github.io/poe2-leveling/poe2_endgame_guide.html', 'what': 'endgame summary (points, tree sections AL70/75)', 'date': '0.5.5'},
    {'id': 'aoeah-abyss', 'url': 'https://www.aoeah.com/news/4616--poe-2-05-abyss-farming-guide-best-faction-tablets--atlas-tree', 'what': 'seller-site Abyss guide', 'date': '2026-06-03'},
    {'id': 'aoeah-essence', 'url': 'https://www.aoeah.com/news/4627--poe-2-05-best-essence-farming-strategy-atlas-tablet-master-skills-and-more', 'what': 'seller-site Essence guide', 'date': '2026-06-08'},
    {'id': 'aoeah-ritual', 'url': 'https://www.aoeah.com/news/4608--best-poe-2-05-ritual-farming-strategy--guide', 'what': 'seller-site Ritual guide (wrong node names)', 'date': '2026-06-01'},
    {'id': 'u4n-vaal', 'url': 'https://www.u4n.com/news/poe-2-vaal-orb-waystones-outcome-chances-explained.html', 'what': 'Vaal outcomes on waystones', 'date': '2025-07-28, upd. 2026-11-21'},
    {'id': 'maxroll-corrupt', 'url': 'https://maxroll.gg/poe2/resources/corruption-outcomes', 'what': 'corruption outcomes', 'date': '2026-05-24'},
    {'id': 'maxroll-rolling', 'url': 'https://maxroll.gg/poe2/resources/rolling-waystones-and-precursor-tablets', 'what': 'rolling guide (0.2 era, history only)', 'date': '2025'},
    {'id': 'forum-regex', 'url': 'https://www.pathofexile.com/forum/view-thread/3858429', 'what': 'player regex guide', 'date': '2025-09-22 / 2026-01-06'},
    {'id': 'pcgamesn-031', 'url': 'https://www.pcgamesn.com/path-of-exile-2/update-endgame-changes-towers-removed', 'what': '0.3.1 tablet charges/tower change history', 'date': '2025-09-26'},
    {'id': 'prices', 'what': 'poe.ninja economy snapshot in the toolkit DB (Forbidden Rites, late league)', 'date': '2026-11-21 08:40 UTC, 1 div = 473 ex'},
]


def expected_per_mod(ws):
    """Average reward of one random mod at T16 (equal spawn weights, rollable prefix/suffix only)."""
    res = {}
    for kind in ('prefix', 'suffix'):
        rows = [w for w in ws if w['kind'] == kind and kind in w['generation_types_in_data']]
        keys = ['waystone_chance_more_pct', 'pack_size_more_pct', 'item_rarity_more_pct', 'monster_rarity_more_pct', 'monster_effectiveness_more_pct']
        res[kind] = {'families': len(rows), **{k: round(sum(r['reward'].get(k, 0) for r in rows) / max(len(rows), 1), 1) for k in keys}}
    by_type = defaultdict(list)
    for w in ws:
        for k in ('pack_size_more_pct', 'item_rarity_more_pct', 'monster_rarity_more_pct', 'monster_effectiveness_more_pct'):
            if k in w['reward']:
                by_type[k].append(f"{w['affix_name']} ({w['reward'][k]}%)")
    res['families_by_reward_type'] = {k: {'excluded_by': OMEN_BY_REWARD[k], 'mods': v} for k, v in by_type.items()}
    res['note'] = ('Equal spawn weight (1) per tier in the data. A 6-mod rare averages ~6x these, summed. '
                   'Waystone chance is on every mod (10-25%). Effectiveness also adds quantity/xp at half rate (0.5.0).')
    return res


def main(repoe, tree_path, out):
    mods = json.load(open(f'{repoe}/mods.min.json', encoding='utf-8'))
    bases = json.load(open(f'{repoe}/base_items.min.json', encoding='utf-8'))
    tree = json.load(open(tree_path, encoding='utf-8'))
    live = {n['name'] for n in tree['nodes'].values() if n.get('name')}
    missing = [(s['name'], k['name']) for s in STRATEGIES for k in s['key_nodes'] if k['name'] not in live]
    ws = waystone_mods(mods)
    types, generic_mods, special = tablets(mods, bases)
    data = {
        'generated': '2026-11-21', 'game_version': GAME_VERSION,
        'tree_build_notes': TREE_NOTES,
        'strategies': STRATEGIES,
        'strategy_node_check': {'all_names_in_live_tree': not missing, 'missing': missing},
        'guide_names_not_in_0_5_5_tree': ['Constant Crossroads (legacy row AtlasGenericNotable16, not in graph)', 'Deadly Evolution', 'Crystalline Growth',
                                          'Ominous Portents', 'Promised Devotion', 'Wandering Path', 'Interdimensional Assault', 'Rising Pyre'],
        'waystone_mods': ws,
        'waystone_expected_per_mod_T16': expected_per_mod(ws),
        'deadly_for_most_builds': {
            'list': ['of Exposure (-max res)', 'Penetrating (ele pen)', 'of Smothering (less recovery)'],
            'combos': ['Exposure + Penetrating + any "extra <element>" prefix', 'Destructive (T4 crit) + Painful', 'Smothering on leech/regen builds',
                       'Impacting on low-life ES casters', 'desecrated of Cycling (no damage 3 of 10 s) for bossing'],
            'source': 'Claude analysis of 0.5.5 values; GGG cut damage/pen/max-res values on 2026-05-25 because they were too strong',
            'confidence': 'medium'},
        'waystone_desecrated_mods': desecrated_waystone_mods(mods),
        'waystone_instilled_emotions': instilled(mods),
        'waystone_facts': {
            'tiers': 'T1-5 low (area 65-69), T6-10 medium (70-74), T11-15 high (75-79), T16 highest (80). Source: maptiers + mod spawn tags.',
            'identify': 'must be identified to open (0.5.0)',
            'reward_rules': 'mod bonuses add up between waystone mods and multiply with atlas passives (0.5.0); prefixes = monster offence, suffixes = player/monster defences (0.5.0)',
            'removed_in_0_5_0': ["Baron's", 'Beastly', 'Brambled', "Doryani's", 'Enervating', "Faridun's", 'Hallowed', 'of Nemeses', "Perennial's", 'Rusted', 'Sacrificial', 'extra projectiles (disabled 2026-05-25)'],
            'revivals': 'more mods = fewer revivals (poe2db); Doryani Stitch the Flesh +1 revival up to 6; forum regex guide used "revives 0" to find 6+ mod stones. Exact formula unverified.',
            'tablet_slots': 'up to 3 tablets per map (0.5.5d fix mentions 3-slot maps); +1 on City maps with Industrial Improvements; empty slots add random league content (0.5.0)',
            'area_corruption_mods': 'EndgameCorruption* (corrupted areas, +1 monster level, xp/quantity trades) and EndgameCleansed* (cleansed areas: e.g. waystones 20-30% more prefix effect / less suffix effect) live in endgamecorruptionmods/endgamecleansedmods',
        },
        'tablets': {
            'types': types,
            'generic_mods_all_types': generic_mods,
            'unique_implicit_or_disabled_mods': special,
            'rules': {
                'uses': 'normal tablets: 10 uses; unique tablets 1-5 (implicit text)',
                'rarity': 'magic normally; rare (+1 max modifier) only with atlas nodes Reverse Transcription / Partial Translation (game data)',
                'crafting': 'Orb of Chance allowed (0.5.0); Ancient Infuser corruption (Maxroll 2026-05-24): extra mod / +10 uses / new type / destroyed',
                'gating': 'Basic (Irradiated) and Overseer tablets need atlas specialisation: Eons of Contamination / Eons of Domination (0.5.0 + data)',
                'stacking': 'same-type tablets stack (0.5.0); 0.5.5: >1 Ritual tablet adds an extra altar; Hilda Ancient Inscriptions rewards DIFFERENT types (+8% per type)',
                'temple': 'Temple tablets guarantee Vaal Beacons (0.5.0)',
                'abyss': 'Abyss tablets only enable Abyss since 2026-05-25 (no longer +1 abyss each)',
            },
            'pairing': {
                'Breach': 'Breach Tablet x2-3 (Horde / Form / Invasion)', 'Ritual': 'Ritual Tablet x2+ (Sacrifice / Omens / Prayers)',
                'Delirium': 'Delirium Tablet (Mirrors / Phobia / Simulacrum)', 'Expedition': 'Expedition Tablet (Runes / Knowledge / Power)',
                'Abyss': 'Abyss Tablet (Hollows / Schisms / Treasures) + Irradiated', 'Essence': 'Overseer (of Crystals) + Crystallised prefix',
                'Boss': 'Overseer (Hoards / Treasure / Pathways)', 'Strongbox': 'any + of the Antiquarian / of Compartments',
                'Rogue Exile': 'any + Exiled prefix / of the Exile', 'Temple': 'Temple Tablet',
                'Generic juice': 'Irradiated (area level) + any with Collector\'s / Brimming / Breeding / Abounding / of Undertaking (+1-2 map mods)'},
            'value_note': 'Tablets are items, not exchange currency: no price in the toolkit DB. Value = per-use reward x uses; price via the overlay/trade link only.',
            'source': 'game data (base_items TowerAugmentation, tablet mod domain) + 0.5.0 / 0.5.5d notes', 'confidence': 'high (mods), medium (pairing)'},
        'rolling': ROLLING,
        'search_box': SEARCH_BOX,
        'v1_watchlist': V1_WATCHLIST,
        'sources': SOURCES,
        'farming_research_overlap': 'research/farming/ had only fetch scripts + cache on 2026-11-21 (no report yet); divines/hour here are quoted guide claims only.',
    }
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    print(f'{len(ws)} waystone families, {len(types)} tablet types, strategies {len(STRATEGIES)}, missing node names: {missing}')


if __name__ == '__main__':
    main(*sys.argv[1:4])
