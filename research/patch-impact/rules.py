"""Exile Oracle: patch-note line -> expected price impact (stdlib only).

    import rules
    rules.classify("Conquering the Vessel of Kulemak now has a chance to drop Ancient Jawbones ...")
    -> [{'rule': 'drop_source_added', 'class': 'drop_source', 'affected_group': 'Ancient Jawbone',
         'expected_move_pct': -40, 'window': 'd7', 'confidence': 'medium', ...}]

    rules.classify_notes(full_text)   # every line of a pasted / fetched patch post

How it works:
1. Each line is matched against RULES (regex triggers, most specific first). One line can hit several rules.
2. The affected group is worked out from the line: named exchange items (built-in families, plus the exact
   exchange names in scripts/cache/exchange_names.json when present, or a `names` list you pass), else the league
   mechanic the line (or its section heading) talks about, mapped to that mechanic's outputs.
3. expected_move_pct / window / confidence come from MEASURED (generated from patch-impact.json by
   scripts/build_outputs.py: medians of the measured, drift-adjusted cases). Rules with too few measured cases keep
   the hand-set PRIOR numbers and say 'estimated'.

Moves are in Divine Orbs, net of the league's drift for the same hours (see patch-impact.md). They are what
happened on average in PoE 2 0.1-0.5, not a promise: the spread is wide and single cases ran from -90% to +300%.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

# ----------------------------------------------------------------------------------------------------------------
# Mechanics and what they produce (exchange-tradeable outputs). Keys are matched in the line or its section.
MECHANICS = {
    'breach': {'words': r'breach(?:es|stone|lord)?|xesht|wombgift|hive', 'outputs': 'Breach splinters/Breachstones/catalysts/wombgifts'},
    'delirium': {'words': r'deliri(?:um|ous)|simulacr(?:um|a)|liquid emotion|distilled|mirror of delirium', 'outputs': 'Simulacrum/Simulacrum Splinter/Liquid emotions'},
    'ritual': {'words': r'ritual|tribute|omen|king in the mists|altars?\b', 'outputs': 'Omens/Petition Splinter/An Audience with the King'},
    'expedition': {'words': r'expedition|logbook|remnants?|artifact|olroth|exotic coinage|grand expedition', 'outputs': 'Expedition artifacts/Logbooks/Sagas'},
    'abyss': {'words': r'abyss(?:al)?|kulemak|bones?\b|jawbone|collarbone|cranium|lightless|amanamu|kurgal|ulaman', 'outputs': 'Abyssal bones (Gnawed/Preserved/Ancient)'},
    'essence': {'words': r'essences?', 'outputs': 'Essences'},
    'vaal_temple': {'words': r"temple|atziri|vaal|soul cores?|architect|crystallised corruption|infuser|sacred water", 'outputs': "Soul cores/Vaal currency (Architect's Orb, Crystallised Corruption, Infusers)"},
    'ultimatum': {'words': r'ultimatum|trial of chaos|trialmaster|fates?\b|inscribed', 'outputs': 'Trialmaster Fates/Inscribed Ultimatum'},
    'sekhemas': {'words': r'sekhemas|djinn barya|barya|sanctum|relic', 'outputs': 'Djinn Barya/relics'},
    'runes_of_aldur': {'words': r'runeforg|runic|verisium|aldur|runes?\b', 'outputs': 'Runes/Verisium/Runic Splinter'},
    'strongbox': {'words': r'strongbox', 'outputs': 'general currency'},
    'waystones': {'words': r'waystones?|map tier|atlas passive|tablet', 'outputs': 'Waystones/tablets/all map loot'},
    'pinnacle': {'words': r'arbiter|pinnacle|uber|citadel|burning monolith', 'outputs': 'pinnacle fragments and boss uniques'},
}

# Exchange item families that can be named in notes (singular form; plural 's' tolerated).
FAMILIES = [
    (r"divine orbs?", 'Divine Orb'), (r"exalted orbs?", 'Exalted Orb'), (r"chaos orbs?", 'Chaos Orb'),
    (r"orbs? of annulment", 'Orb of Annulment'), (r"fracturing orbs?", 'Fracturing Orb'),
    (r"mirrors? of kalandra", 'Mirror of Kalandra'), (r"hinekora's locks?", "Hinekora's Lock"),
    (r"orbs? of chance", 'Orb of Chance'), (r"vaal orbs?", 'Vaal Orb'), (r"regal orbs?", 'Regal Orb'),
    (r"orbs? of alchemy", 'Orb of Alchemy'), (r"jeweller'?s orbs?", "Jeweller's Orbs"),
    (r"gemcutter'?s prisms?", "Gemcutter's Prism"), (r"glassblower'?s baubles?", "Glassblower's Bauble"),
    (r"artificer'?s orbs?", "Artificer's Orb"), (r"architect'?s orbs?", "Architect's Orb"),
    (r"crystallised corruption", 'Crystallised Corruption'), (r"(?:vaal )?\w+ infusers?", 'Vaal infusers'),
    (r"omens? of [\w' ]+?(?=[,.;)]|\s(?:now|no|is|are|can|has|have|will|and|or|from|to|in|on|when)\b|$)", 'Omen'),
    (r"omens?", 'Omens'),
    (r"(?:lesser |greater |perfect |corrupted )?essences? of [\w ]+?(?=[,.;)]|\s(?:now|no|is|are|can|has|have|will|and|or|from|to|in|on)\b|$)", 'Essence'),
    (r"essences?", 'Essences'), (r"soul cores?(?: of \w+)?", 'Soul cores'),
    (r"(?:\w+ )?catalysts?", 'Catalysts'), (r"breach splinters?", 'Breach Splinter'), (r"breachstones?", 'Breachstone'),
    (r"simulacrum splinters?", 'Simulacrum Splinter'), (r"simulacr(?:um|a)\b", 'Simulacrum'),
    (r"(?:diluted |distilled |concentrated )?liquid \w+|liquid emotions?", 'Liquid emotions'),
    (r"(?:gnawed|preserved|ancient) (?:jawbone|rib|collarbone|cranium|bone)s?", 'Abyssal bones'),
    (r"(?:\w+ )?fates?\b(?! of)", 'Trialmaster Fates'), (r"inscribed ultimatums?", 'Inscribed Ultimatum'),
    (r"djinn baryas?|baryas?", 'Djinn Barya'), (r"petition splinters?", 'Petition Splinter'),
    (r"expedition logbooks?|logbooks?", 'Expedition Logbook'), (r"exotic coinage|(?:\w+ )?artifacts?", 'Expedition artifacts'),
    (r"uncut (?:skill|support|spirit) gems?", 'Uncut gems'), (r"lineage (?:support )?gems?", 'Lineage support gems'),
    (r"(?:lesser |greater |perfect )?\w+ runes?\b", 'Runes'), (r"verisium", 'Verisium'), (r"waystones?", 'Waystones'),
    (r"(?:precursor )?tablets?", 'Precursor tablets'), (r"idols? of \w+", 'Idols'), (r"wombgifts?", 'Wombgifts'),
    (r"splinters?", 'Fragments/splinters'), (r"fragments?", 'Fragments/splinters'),
]
_FAM = [(re.compile(r'(?<![\w])(' + p + r')', re.I), g) for p, g in FAMILIES]

# ----------------------------------------------------------------------------------------------------------------
# Triggers. class: drop_source | drop_rate | farm (mechanic reward / farm strategy) | crafting | skill | ascendancy |
# unique | league_mechanic | vendor_recipe | exploit_fix. direction: the expected move of the affected group's price.
NUM = r'(?:\d+(?:\.\d+)?%?)'
RULES = [
    # --- supply: sources and drop rates ---
    {'id': 'drop_source_removed', 'class': 'drop_source', 'direction': 'up', 'target': 'named',
     're': r"\b(?:no longer|can no longer|cannot|will no longer|won't) (?:drop|be found|appear|spawn|be obtained)|\bremoved (?:\w+ ){0,6}from (?:the )?(?:drop|loot|reward)"},
    {'id': 'drop_source_added', 'class': 'drop_source', 'direction': 'down', 'target': 'named',
     're': r"\b(?:now|can now|will now|also|now also|now additionally)\s+(?:always |guaranteed to |additionally |has a (?:small |low |rare )?chance to |have a (?:small |low |rare )?chance to |can |)(?:drop|be found|appear|be obtained|be dropped|spawn)|\bcan (?:now )?drop from\b|\bnow drops?\b|\badded (?:\w+ ){0,6}to (?:the )?(?:drop|loot|reward) (?:pool|table)|\bcan now be found\b"},
    {'id': 'drop_rate_up', 'class': 'drop_rate', 'direction': 'down', 'target': 'named',
     're': r"\b(?:greatly |significantly |slightly |)(?:increased|improved|raised|doubled|tripled|boosted) (?:the )?(?:(?:drop|spawn|find) (?:rate|chance|frequency)s?|(?:chances?|frequency) of (?:finding|dropping|spawning|getting|obtaining)|(?:quantity|amount|number) of (?:items|currency|\w+ (?:orbs|omens|essences|splinters|fragments|catalysts|cores|runes|logbooks|baryas)))\b|\b(?:drop|spawn) (?:rate|chance)s? (?:\w+ ){0,6}(?:have|has) been (?:greatly |significantly |slightly |)increased|\b(?:are|is) (?:now )?(?:significantly |much |considerably |)(?:more common|more frequent|more likely to (?:drop|appear))|\b(?:drop|appear|spawn)s? (?:significantly |much |considerably |\d+(?:\.\d+)?% |)more (?:often|frequently)|\bnow drop more\b|\bmore (?:\w+ ){0,3}(?:will|now) drop|\b(?:\d+(?:\.\d+)?)% (?:more|increased) (?:chance|likely) to (?:drop|appear|spawn|contain)"},
    {'id': 'drop_rate_down', 'class': 'drop_rate', 'direction': 'up', 'target': 'named',
     're': r"\b(?:greatly |significantly |slightly |)(?:reduced|lowered|decreased|halved) (?:the )?(?:(?:drop|spawn|find) (?:rate|chance|frequency)s?|(?:chances?|frequency) of (?:finding|dropping|spawning|getting|obtaining)|(?:quantity|amount|number) of (?:items|currency|\w+ (?:orbs|omens|essences|splinters|fragments|catalysts|cores|runes|logbooks|baryas)))\b|\b(?:drop|spawn) (?:rate|chance)s? (?:\w+ ){0,6}(?:have|has) been (?:greatly |significantly |slightly |)(?:reduced|decreased|lowered)|\b(?:are|is) (?:now )?(?:significantly |much |considerably |)(?:rarer|less common|less frequent|less likely to (?:drop|appear))|\b(?:drop|appear|spawn)s? (?:significantly |much |considerably |\d+(?:\.\d+)?% |)less (?:often|frequently)|\b(?:\d+(?:\.\d+)?)% (?:less|reduced) (?:chance|likely) to (?:drop|appear|spawn|contain)"},
    # --- farm strategies / mechanic rewards ---
    {'id': 'exploit_fix', 'class': 'exploit_fix', 'direction': 'up', 'target': 'mechanic',
     're': r"\b(?:exploit|duplicat(?:e|ed|ion)|infinite(?:ly)?|unlimited|indefinitely|repeatedly|could be (?:re-?used|reused|rerolled) (?:infinitely|repeatedly|indefinitely))\b|fixed (?:a |an )?(?:bug|issue) where (?:\w+ ){0,12}(?:excessive|far more|significantly more|much more|more than intended|additional|extra|multiple times)"},
    {'id': 'farm_nerf', 'class': 'farm', 'direction': 'up', 'target': 'mechanic',
     're': r"\bdiminishing returns\b|\b(?:reduced|lowered|decreased|halved) (?:the )?(?:\w+ ){0,5}(?:rewards?|loot|quantity|rarity|number of (?:items|chests|monsters|currency)|currency|items? dropped|drops?|item quantity|pack size|frequency)\b|\b(?:rewards?|loot) (?:\w+ ){0,3}(?:reduced|lowered|less)|\bno longer (?:stack|guarantee|grant)|\bnow (?:has|have) a (?:maximum|cap|limit)|\bcapped\b"},
    {'id': 'farm_buff', 'class': 'farm', 'direction': 'down', 'target': 'mechanic',
     're': r"\b(?:greatly |significantly |substantially |)(?:increased|improved|doubled|tripled|raised|boosted) (?:the )?(?:\w+ ){0,5}(?:rewards?|loot|quantity|rarity|number of (?:items|chests|monsters|remnants|currency)|currency|drops?|item quantity|pack size)\b|\brewards? (?:\w+ ){0,4}(?:greatly |significantly |)(?:increased|improved|more significantly)|\b(?:have|has) been (?:greatly |significantly |)improved\b|\bnow (?:drops?|grants?|contains?|gives?) (?:more|additional|significantly more|an additional)"},
    # --- crafting ---
    {'id': 'crafting_new_use', 'class': 'crafting', 'direction': 'up', 'target': 'named',
     're': r"\b(?:can now be used|now (?:also )?(?:works|applies|affects|can be applied|be applied)|can now (?:also )?(?:be )?(?:applied|used|target)|now (?:adds|removes|upgrades|grants|guarantees|allows)|new (?:omens?|currency|crafting))\b|\badded (?:a |an |)(?:new )?(?:omen|currency|catalyst|essence|crafting)"},
    {'id': 'crafting_use_removed', 'class': 'crafting', 'direction': 'down', 'target': 'named',
     're': r"\b(?:can no longer be used|no longer (?:works|applies|affects|can be applied|be applied|adds|removes|guarantees)|can no longer (?:be )?(?:applied|used|target)|has been removed|have been removed|removed the (?:omen|currency|recombinator))\b"},
    {'id': 'crafting_changed', 'class': 'crafting', 'direction': 'volatile', 'target': 'named',
     're': r"\b(?:omens?|orbs? of|catalysts?|essences?|recombinat\w+|reforging bench|currency) (?:\w+ ){0,8}(?:now|instead|changed|reworked|inverted|swapped)\b"},
    # --- socketables (soul cores, runes, talismans, idols): the item's own stats changed ---
    {'id': 'socketable_change', 'class': 'crafting', 'direction': 'by_direction', 'target': 'named',
     're': r"(?:soul core|\brune\b|talisman|idol)\w* of [\w' ]+? (?:now|no longer|instead|grants?|has been|have been)|\b(?:soul cores?|runes|talismans|idols) (?:\w+ ){0,6}(?:now grant|no longer grant|have been (?:buffed|changed|reworked))"},
    # --- vendor / recipes ---
    {'id': 'vendor_recipe', 'class': 'vendor_recipe', 'direction': 'volatile', 'target': 'named',
     're': r"\b(?:vendor(?:s|ed|ing)?|recipe|can be purchased|purchas(?:e|ed|able) from|sold (?:by|from)|gold cost|reforging bench|currency exchange|alva|doryani|una|hooded one)\b"},
    # --- builds (second-order: uniques, lineage supports, base types) ---
    {'id': 'ascendancy_change', 'class': 'ascendancy', 'direction': 'by_direction', 'target': 'build',
     're': r"\b(?:ascendancy|bloodmage|blood mage|infernalist|lich|stormweaver|chronomancer|titan|warbringer|smith of kitava|witchhunter|gemling legionnaire|tactician|invoker|acolyte of chayula|deadeye|pathfinder|amazon|ritualist|oracle|shaman|disciple of varashta|abyssal lich|spirit walker)\b"},
    {'id': 'unique_change', 'class': 'unique', 'direction': 'by_direction', 'target': 'build',
     're': r"(?-i:\b[A-Z][\w']+(?: (?:of |the )?[A-Z][\w']+){0,3}) (?-i:Unique|unique) (?:amulet|ring|belt|helmet|gloves|boots|body armour|shield|buckler|focus|quiver|bow|crossbow|staff|quarterstaff|wand|sceptre|spear|mace|flail|axe|sword|claw|dagger|charm|flask|jewel|tablet|relic)"},
    {'id': 'skill_change', 'class': 'skill', 'direction': 'by_direction', 'target': 'build',
     're': r"\b(?:skill|support|spell|attack|minion|totem|herald|aura|curse|warcry|meta[- ]gem|persistent buff|invocation|gem)s?\b(?! points)"},
    # --- league mechanic catch-all (direction unclear) ---
    {'id': 'league_mechanic_change', 'class': 'league_mechanic', 'direction': 'volatile', 'target': 'mechanic',
     're': r"(?!)"},   # assigned when nothing above hit but the line/section names a mechanic
]
for _r in RULES:
    _r['_re'] = re.compile(_r['re'], re.I)

REWARDISH = re.compile(r"\b(?:rewards?|drops?|dropped|loot|currency|quantity|rarity|chests?|chance to (?:drop|spawn|contain|find)|spawn chance|guaranteed|number of (?:items|chests|rewards|maps|encounters)|delirious|juic\w*|value of)\b", re.I)
COSMETIC = re.compile(r'\b(?:visual|tooltip|text|description|display(?:ed)?|ui|icon|crash|audio|sound|animation|performance|typo|incorrectly (?:shown|stated)|localis\w+)\b', re.I)
BUFF = re.compile(r'\b(increased|more|now (?:also )?(?:grants|gains|deals|has)|higher|faster|added|no longer (?:has|requires|costs|consumes)|improved|reduced (?:cost|cooldown|mana cost|reservation|spirit|requirement))', re.I)
NERF = re.compile(r'\b(reduced|less|lower|slower|removed|no longer|now requires|decreased|can no longer)\b', re.I)
_PREV = re.compile(r'(\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?\s*%?[^()]{0,80}?\((?:previously|from|was)\s*\+?(\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?', re.I)
_WORSE_UP = re.compile(r'cost|cooldown|reservation|requirement|damage taken|delay|duration of .*debuff', re.I)

# What a direction means for the build-related classes.
BUILD_EFFECTS = {
    'skill': {'buff': "its lineage support gems, the uniques its builds use and its key rare base types rise; the uncut gem level it needs rises a little",
              'nerf': "the uniques/lineage supports its builds used fall (players respec); the replacement skill's key items rise"},
    'ascendancy': {'buff': "uniques and gems the ascendancy's main builds use rise",
                   'nerf': "those uniques/gems fall; items for the builds players move to rise"},
    'unique': {'buff': 'that unique rises (most in the first 24-72 h); a cheap unique can 3-10x',
               'nerf': 'that unique falls; legacy copies of the old version may rise if they keep the old stats'},
}

# ----------------------------------------------------------------------------------------------------------------
# PRIOR: hand-set starting numbers (estimates, before measurement). MEASURED overrides them where n_cases >= 3.
PRIOR = {
    'drop_source_added': {'typical_move_pct': -40, 'window': 'd7', 'confidence': 'medium'},
    'drop_source_removed': {'typical_move_pct': 40, 'window': 'd7', 'confidence': 'low'},
    'drop_rate_up': {'typical_move_pct': -30, 'window': 'd7', 'confidence': 'medium'},
    'drop_rate_down': {'typical_move_pct': 30, 'window': 'd7', 'confidence': 'low'},
    'exploit_fix': {'typical_move_pct': 15, 'window': 'h72', 'confidence': 'low'},
    'farm_nerf': {'typical_move_pct': 15, 'window': 'd7', 'confidence': 'low'},
    'farm_buff': {'typical_move_pct': -15, 'window': 'd7', 'confidence': 'low'},
    'crafting_new_use': {'typical_move_pct': 50, 'window': 'h72', 'confidence': 'low'},
    'crafting_use_removed': {'typical_move_pct': -50, 'window': 'h72', 'confidence': 'low'},
    'crafting_changed': {'typical_move_pct': 0, 'window': 'h72', 'confidence': 'low'},
    'vendor_recipe': {'typical_move_pct': 0, 'window': 'h72', 'confidence': 'low'},
    'ascendancy_change': {'typical_move_pct': 0, 'window': 'h72', 'confidence': 'low'},
    'unique_change': {'typical_move_pct': 0, 'window': 'h72', 'confidence': 'low'},
    'skill_change': {'typical_move_pct': 0, 'window': 'h72', 'confidence': 'low'},
    'league_mechanic_change': {'typical_move_pct': 0, 'window': 'd7', 'confidence': 'low'},
}

# --- BEGIN MEASURED (generated by scripts/build_outputs.py; do not edit by hand) ---
MEASURED = {
    "crafting_changed": {
        "typical_move_pct": -2.1,
        "window": "h24",
        "n_cases": 2,
        "spread": [
            -2.9,
            -1.4
        ],
        "confidence": "low",
        "hit_rate": None,
        "phase_adjusted_move_pct": None,
        "phase_n": 0
    },
    "crafting_new_use": {
        "typical_move_pct": 8.4,
        "window": "h72",
        "n_cases": 2,
        "spread": [
            -29.1,
            45.8
        ],
        "phase_hit_rate": 0.5,
        "confidence": "low",
        "hit_rate": 0.5,
        "source": "hand-reviewed family crafting_use"
    },
    "crafting_use_removed": {
        "typical_move_pct": -8.4,
        "window": "h72",
        "n_cases": 2,
        "spread": [
            -45.8,
            29.1
        ],
        "phase_hit_rate": 0.5,
        "confidence": "low",
        "hit_rate": 0.5,
        "source": "hand-reviewed family crafting_use"
    },
    "drop_rate_down": {
        "typical_move_pct": 51.2,
        "window": "d7",
        "n_cases": 4,
        "spread": [
            -20.0,
            163.3
        ],
        "phase_hit_rate": 1.0,
        "confidence": "medium",
        "hit_rate": 0.75,
        "source": "hand-reviewed family supply_down_named"
    },
    "drop_rate_up": {
        "typical_move_pct": -9.8,
        "window": "h72",
        "n_cases": 18,
        "spread": [
            -37.5,
            25.4
        ],
        "phase_hit_rate": 0.58,
        "confidence": "medium",
        "hit_rate": 0.61,
        "source": "hand-reviewed family supply_up_named"
    },
    "drop_source_added": {
        "typical_move_pct": -9.8,
        "window": "h72",
        "n_cases": 18,
        "spread": [
            -37.5,
            25.4
        ],
        "phase_hit_rate": 0.58,
        "confidence": "medium",
        "hit_rate": 0.61,
        "source": "hand-reviewed family supply_up_named"
    },
    "drop_source_removed": {
        "typical_move_pct": 51.2,
        "window": "d7",
        "n_cases": 4,
        "spread": [
            -20.0,
            163.3
        ],
        "phase_hit_rate": 1.0,
        "confidence": "medium",
        "hit_rate": 0.75,
        "source": "hand-reviewed family supply_down_named"
    },
    "exploit_fix": {
        "typical_move_pct": 41.5,
        "window": "d7",
        "n_cases": 8,
        "spread": [
            5.4,
            99.2
        ],
        "phase_hit_rate": 0.71,
        "confidence": "medium",
        "hit_rate": 0.75,
        "source": "hand-reviewed family farm_nerf_outputs"
    },
    "farm_buff": {
        "typical_move_pct": -11.6,
        "window": "h72",
        "n_cases": 3,
        "spread": [
            -21.6,
            -8.2
        ],
        "phase_hit_rate": 1.0,
        "confidence": "low",
        "hit_rate": 1.0,
        "source": "hand-reviewed family farm_buff_outputs"
    },
    "farm_nerf": {
        "typical_move_pct": 41.5,
        "window": "d7",
        "n_cases": 8,
        "spread": [
            5.4,
            99.2
        ],
        "phase_hit_rate": 0.71,
        "confidence": "medium",
        "hit_rate": 0.75,
        "source": "hand-reviewed family farm_nerf_outputs"
    },
    "league_mechanic_change": {
        "typical_move_pct": -5.1,
        "window": "d7",
        "n_cases": 48,
        "spread": [
            -37.2,
            14.7
        ],
        "confidence": "low",
        "hit_rate": None,
        "phase_adjusted_move_pct": -19.1,
        "phase_n": 43
    },
    "socketable_change": {
        "typical_move_pct": 31.4,
        "window": "h24",
        "n_cases": 8,
        "spread": [
            -43.5,
            61.2
        ],
        "phase_hit_rate": None,
        "confidence": "medium",
        "hit_rate": 0.62,
        "source": "hand-reviewed family socketable_stats"
    },
    "vendor_recipe": {
        "typical_move_pct": 2.2,
        "window": "d7",
        "n_cases": 7,
        "spread": [
            -43.0,
            19.4
        ],
        "confidence": "low",
        "hit_rate": None,
        "phase_adjusted_move_pct": -30.4,
        "phase_n": 5
    },
    "drop_source_added:big": {
        "typical_move_pct": -4.8,
        "window": "h72",
        "n_cases": 14,
        "spread": [
            -33.9,
            25.4
        ],
        "phase_hit_rate": 0.64,
        "confidence": "low",
        "hit_rate": 0.57,
        "source": "hand-reviewed family supply_up_named:big"
    },
    "drop_rate_up:big": {
        "typical_move_pct": -4.8,
        "window": "h72",
        "n_cases": 14,
        "spread": [
            -33.9,
            25.4
        ],
        "phase_hit_rate": 0.64,
        "confidence": "low",
        "hit_rate": 0.57,
        "source": "hand-reviewed family supply_up_named:big"
    },
    "drop_source_added:small": {
        "typical_move_pct": -34.9,
        "window": "h24",
        "n_cases": 4,
        "spread": [
            -40.0,
            -30.5
        ],
        "phase_hit_rate": None,
        "confidence": "medium",
        "hit_rate": 1.0,
        "source": "hand-reviewed family supply_up_named:small"
    },
    "drop_rate_up:small": {
        "typical_move_pct": -34.9,
        "window": "h24",
        "n_cases": 4,
        "spread": [
            -40.0,
            -30.5
        ],
        "phase_hit_rate": None,
        "confidence": "medium",
        "hit_rate": 1.0,
        "source": "hand-reviewed family supply_up_named:small"
    },
    "farm_nerf:early": {
        "typical_move_pct": 19.8,
        "window": "d7",
        "n_cases": 4,
        "spread": [
            5.4,
            33.7
        ],
        "phase_hit_rate": 0.75,
        "confidence": "medium",
        "hit_rate": 0.75,
        "source": "hand-reviewed family farm_nerf_outputs:early"
    },
    "exploit_fix:early": {
        "typical_move_pct": 19.8,
        "window": "d7",
        "n_cases": 4,
        "spread": [
            5.4,
            33.7
        ],
        "phase_hit_rate": 0.75,
        "confidence": "medium",
        "hit_rate": 0.75,
        "source": "hand-reviewed family farm_nerf_outputs:early"
    },
    "farm_nerf:mid_late": {
        "typical_move_pct": 124.8,
        "window": "d7",
        "n_cases": 4,
        "spread": [
            49.2,
            179.8
        ],
        "phase_hit_rate": 0.67,
        "confidence": "medium",
        "hit_rate": 0.75,
        "source": "hand-reviewed family farm_nerf_outputs:mid_late"
    },
    "exploit_fix:mid_late": {
        "typical_move_pct": 124.8,
        "window": "d7",
        "n_cases": 4,
        "spread": [
            49.2,
            179.8
        ],
        "phase_hit_rate": 0.67,
        "confidence": "medium",
        "hit_rate": 0.75,
        "source": "hand-reviewed family farm_nerf_outputs:mid_late"
    }
}
# --- END MEASURED ---

_names_cache = {}


def _load(fname, default):
    if fname not in _names_cache:
        try:
            _names_cache[fname] = json.load(open(os.path.join(HERE, 'scripts', 'cache', fname), encoding='utf-8'))
        except Exception:
            _names_cache[fname] = default
    return _names_cache[fname]


def _exchange_names():
    return _load('exchange_names.json', {})


def _name_hits(text, names, min_len=5):
    low, out = text.lower(), []
    for n in sorted(names, key=len, reverse=True):
        nl = n.lower()
        if len(nl) < min_len:
            continue
        i = low.find(nl)
        if i >= 0 and (i == 0 or not low[i - 1].isalnum()) and (i + len(nl) >= len(low) or not low[i + len(nl)].isalnum()):
            if not any(nl in o.lower() for o in out):
                out.append(n)
    return out


def gems_named(text):
    """Skill / support gem names in the line (from the game data cache)."""
    return _name_hits(text, _load('gem_names.json', {}), 4)


def uniques_named(text):
    return _name_hits(text, _load('unique_names.json', []), 5)


_BIGWORDS = re.compile(r'\b(?:significantly|greatly|massively|heavily|vastly|much (?:more|less|rarer)|always|guaranteed|doubled|tripled|halved)\b', re.I)


def magnitude(text, rule_id=''):
    """'big' or 'small' shock. Big = a brand-new source, strong wording, or a stated change of 50% or more."""
    if rule_id in ('drop_source_added', 'drop_source_removed'):
        return 'big'
    if _BIGWORDS.search(text):
        return 'big'
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*%', text):
        if float(m.group(1)) >= 50:
            return 'big'
    return 'small'


def direction_of(text):
    """'buff' / 'nerf' / 'change' for a build-related line ('X (previously Y)' first, then wording)."""
    m = _PREV.search(text)
    if m:
        a1, a2, b1, b2 = m.groups()
        new, old = (float(a1) + float(a2 or a1)) / 2, (float(b1) + float(b2 or b1)) / 2
        if new != old:
            up = new > old
            if _WORSE_UP.search(text[:m.end()]) and not re.search(r'efficiency|recovery', text[:m.end()], re.I):
                up = not up
            return 'buff' if up else 'nerf'
    if re.search(r'now (?:has|have) a (?:\w+ )?requirement|now requires?', text, re.I):
        return 'nerf'
    b, n = len(BUFF.findall(text)), len(NERF.findall(text))
    return 'buff' if b > n else 'nerf' if n > b else 'change'


def named_items(text, names=None):
    """Exchange items / families named in the text. names: optional iterable of exact exchange item names
    (default: scripts/cache/exchange_names.json). Returns a list of (name or family, kind)."""
    out, seen = [], set()
    exact = names if names is not None else _exchange_names()
    low = text.lower()
    if exact:
        for n in sorted(exact, key=len, reverse=True):
            nl = n.lower()
            if len(nl) < 5 or nl in seen:
                continue
            i = low.find(nl)
            if i < 0 and not nl.endswith('s'):
                i = low.find(nl + 's')
            if i >= 0 and (i == 0 or not low[i - 1].isalnum()):
                if any(nl in s for s in seen):   # 'Breach Splinter' inside 'Breachlord ...'
                    continue
                seen.add(nl)
                out.append((n, 'item'))
    for rx, fam in _FAM:
        for m in rx.finditer(text):
            frag = m.group(1).lower().rstrip('s')
            if any(frag in s or s in frag for s in seen):
                continue
            seen.add(frag)
            out.append((m.group(1) if fam in ('Omen', 'Essence') else fam, 'family'))
    return out


def mechanics_of(text, section=''):
    hits = []
    for k, v in MECHANICS.items():
        if re.search(r'(?<![\w])(?:' + v['words'] + r')(?![\w])', text, re.I):
            hits.append(k)
    if not hits and section:
        for k, v in MECHANICS.items():
            if re.search(r'(?<![\w])(?:' + v['words'] + r')(?![\w])', section, re.I):
                hits.append(k)
    return hits


def _numbers(rule_id, text='', league_day=None):
    """Measured numbers for the most specific key that has >= 3 cases: rule:big / rule:small (shock size),
    rule:early / rule:mid_late (farm nerfs, when league_day is known), then the rule itself; else PRIOR."""
    keys = []
    if rule_id in ('drop_source_added', 'drop_rate_up', 'drop_source_removed', 'drop_rate_down'):
        keys.append(rule_id + ':' + magnitude(text, rule_id))
    if rule_id in ('farm_nerf', 'exploit_fix'):
        if league_day is None:   # the measured sign flips with league timing: don't guess
            return dict(PRIOR[rule_id], basis='estimated (pass league_day for the measured early / mid_late numbers)',
                        n_cases=MEASURED.get(rule_id, {}).get('n_cases', 0))
        keys.append(rule_id + (':early' if league_day < 15 else ':mid_late'))
    keys.append(rule_id)
    n_seen = 0
    for k in keys:
        m = MEASURED.get(k)
        if m:
            n_seen = max(n_seen, m.get('n_cases', 0))
        if m and m.get('n_cases', 0) >= 3:
            return dict(m, basis='measured', key=k)
    return dict(PRIOR.get(rule_id, {'typical_move_pct': 0, 'window': 'd7', 'confidence': 'low'}), basis='estimated', n_cases=n_seen)


def classify(line_text, section='', names=None, league_day=None):
    """One patch-note line -> list of {rule, class, affected_group, expected_move_pct, window, confidence, ...}.
    league_day (optional): days since the league started; farm nerfs read differently before / after day 15.
    Empty list: nothing here should move exchange prices."""
    text = line_text.strip()
    if not text:
        return []
    items = named_items(text, names)
    mechs = mechanics_of(text, section)
    out = []
    hit_ids = []
    for r in RULES:
        if r['_re'].search(text):
            hit_ids.append(r['id'])
    gems, uqs = gems_named(text), uniques_named(text)
    if uqs and 'unique_change' not in hit_ids:
        hit_ids.append('unique_change')
    if gems and 'skill_change' not in hit_ids:
        hit_ids.append('skill_change')
    # precedence: a specific supply/crafting rule wins over the generic ones on the same line
    if 'drop_source_removed' in hit_ids and 'drop_source_added' in hit_ids:
        hit_ids.remove('drop_source_added')
    if 'crafting_use_removed' in hit_ids or 'crafting_new_use' in hit_ids:
        hit_ids = [h for h in hit_ids if h != 'crafting_changed']
    if 'exploit_fix' in hit_ids:
        hit_ids = [h for h in hit_ids if h not in ('farm_buff',)]
    if 'drop_rate_up' in hit_ids or 'drop_rate_down' in hit_ids:
        hit_ids = [h for h in hit_ids if h != 'drop_source_added']
    if any(h in hit_ids for h in ('drop_source_added', 'drop_source_removed', 'drop_rate_up', 'drop_rate_down')):
        hit_ids = [h for h in hit_ids if h not in ('farm_buff', 'farm_nerf', 'skill_change')]
    if any(h.startswith('crafting') for h in hit_ids) and not items:
        hit_ids = [h for h in hit_ids if not h.startswith('crafting')]
    if 'unique_change' in hit_ids or 'ascendancy_change' in hit_ids:
        hit_ids = [h for h in hit_ids if h != 'skill_change']
    if 'socketable_change' in hit_ids:
        hit_ids = [h for h in hit_ids if not h.startswith('crafting_') and h not in ('farm_nerf', 'farm_buff', 'skill_change')]
    if not hit_ids and mechs and REWARDISH.search(text) and not COSMETIC.search(text):
        hit_ids = ['league_mechanic_change']
    for rid in hit_ids:
        r = next(x for x in RULES if x['id'] == rid)
        nums = _numbers(rid, text, league_day)
        if r['target'] == 'named' and items:
            groups = [n for n, _ in items]
        elif r['target'] in ('named', 'mechanic') and mechs:
            groups = [MECHANICS[m]['outputs'] for m in mechs]
        elif r['target'] == 'named':
            groups = ['(item not named: read the line)']
        elif r['target'] == 'mechanic':
            groups = ['general currency (mechanic unclear)']
        elif rid == 'unique_change' and uqs:
            groups = uqs
        elif rid == 'skill_change' and gems:
            groups = gems
        else:
            groups = ['build items: uniques / lineage supports / bases used by the builds named']
        groups = list(dict.fromkeys(groups))
        d = direction_of(text) if r['direction'] == 'by_direction' else r['direction']
        move = nums.get('typical_move_pct', 0)
        if r['direction'] == 'by_direction':
            move = abs(move) if d == 'buff' else -abs(move) if d == 'nerf' else 0
        entry = {'rule': rid, 'class': r['class'], 'direction': d, 'affected_group': ', '.join(groups[:6]),
                 'expected_move_pct': move, 'window': nums.get('window', 'd7'),
                 'confidence': nums.get('confidence', 'low'), 'basis': nums['basis'], 'n_cases': nums.get('n_cases', 0)}
        if r['class'] in BUILD_EFFECTS and d in ('buff', 'nerf'):
            entry['second_order'] = BUILD_EFFECTS[r['class']][d]
        if r['class'] in ('farm', 'exploit_fix'):
            entry['second_order'] = ('supply of the farm\'s outputs falls -> outputs rise; the farm\'s inputs '
                                     '(fragments, tablets, waystones) fall' if d == 'up' else
                                     'outputs get more common -> fall; inputs needed to run it rise')
        if r['class'] in ('drop_source', 'drop_rate'):
            entry['second_order'] = ('the item falls toward the cost of the new source; things it crafts into '
                                     'or gates (fragments, boss entries) get cheaper to run' if d == 'down' else
                                     'remaining stock rises; substitutes rise less')
        if 'spread' in nums:
            entry['spread'] = nums['spread']
        if 'key' in nums:
            entry['measured_key'] = nums['key']
        if r['class'] in ('drop_source', 'drop_rate'):
            entry['magnitude'] = magnitude(text, rid)
        out.append(entry)
    return out


def split_lines(text):
    """Plain text / forum copy -> [(section, line)]: short lines without a full stop are headings."""
    out, section = [], ''
    for raw in text.splitlines():
        l = raw.strip(' \t-•*')
        if not l:
            continue
        if len(l) < 70 and not l.endswith('.') and not l.endswith(':'):
            section = l
            continue
        out.append((section, l))
    return out


def classify_notes(text, names=None, only_price=True, league_day=None):
    """A whole patch post -> [{'section', 'line', 'hits': [...]}] (only lines with a price-relevant hit)."""
    res = []
    for section, line in split_lines(text):
        hits = classify(line, section, names, league_day)
        if only_price:
            hits = [h for h in hits if h['class'] not in ('skill',) or h['direction'] in ('buff', 'nerf')]
        if hits or not only_price:
            res.append({'section': section, 'line': line, 'hits': hits})
    return res


if __name__ == '__main__':
    import sys
    txt = sys.stdin.read() if len(sys.argv) < 2 else ' '.join(sys.argv[1:])
    for r in (classify_notes(txt) if '\n' in txt else [{'section': '', 'line': txt, 'hits': classify(txt)}]):
        print(r['line'][:120])
        for h in r['hits']:
            print('   ', h['rule'], h['direction'], '|', h['affected_group'][:70], '|', h['expected_move_pct'], '%', h['window'], h['confidence'], h['basis'])
