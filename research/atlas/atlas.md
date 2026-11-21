# Atlas war room research (PoE 2 0.5.5, for PLAN R15)

Written 2026-11-21. Game data from client build **26744644** (0.5.5) plus the repoe export of 2026-11-20.
PoE 2 1.0 launches 2026-12-11, and the atlas will probably change, so re-run `scripts\` on the 1.0 client.

**Confidence tags:**
- **[data]**: read from the game files. High confidence.
- **[GGG]**: official patch notes or announcements.
- **[guide]**: a community site, dated. Seller sites (AOEAH, U4N, MMOexp) are marked as such.
- **[est]**: my own analysis.

**Files in this folder:**
- `atlas.json`: the machine-readable version of this report (all sections).
- `atlas-tree-26744644.json`: the whole live atlas tree. It has 575 nodes with x/y, English text, choice options and gates, plus 586 links.
- `scripts\atlas_tree.py`: reads the tree graph (`.psg`) and the tables, and writes the tree JSON.
- `scripts\csd.py`: a small reader for stat-description files (stat ids to English text).
- `scripts\build_atlas_json.py`: rebuilds `atlas.json` from the mod data, plus the annotations stored in it.

The farming research in `research\farming\` only held fetch scripts and cache today, with no report yet. The
divines/hour figures below are therefore quoted guide claims only.

---

## 1. Atlas passive tree (0.5.x)

### How it works
- **Points [GGG 0.5.0]:**
  - Maps inside the **Fortress** grant 1 or more points each. This replaced the old ways of earning points.
  - Killing the Arbiter of Divinity 5 times also completes Fortress maps.
  - Completing every Fortress map gives enough points for the **whole tree**, so respec is gone. Only the
    multi-choice nodes can still be switched, at any time.
  - [guide, domistae 0.5.5] Precursor Towers give +4 points and a pinnacle gives 6+. These are not confirmed by GGG.
- **Size [data]:** 575 live nodes. GGG says "over 300".
  - Main tree: 375 nodes, of which 38 are mastery art only.
  - Six subtrees: Ritual 37, Temple (Incursion) 37, Abyss 36, Breach 33, Delirium 32, Expedition 25.
  - In all, 224 notables and 44 "keystones". All 44 keystones are **choice nodes** ("Select a bonus").
- **Subtrees [data + guide]:**
  - Each subtree's points come from its own mechanic. The table text reads "Grants Breach Atlas passive points on
    completion".
  - Expedition's 24-node tree (0.5.4) gets its points from the Grand Expedition bosses.
- **Gates [data]:**
  - Each node may need a specific Fortress map done (`Requirement`, which points at an `AtlasInsideFortress…` node).
  - Each node may also need an area level: 70 for 141 nodes, 75 for 127 nodes. That gives three "sections", which
    matches [guide, domistae]: section 2 at AL70+, section 3 at AL75+.
- **Atlas Masters [GGG + data]:** Jado, Doryani and Hilda each have 12 keystones. You can have 4 active per master,
  you can change them any time, and the rows unlock through each master's missions. All 36 texts are in
  `atlasclasspassives.json`. Useful ones:
  - **Doryani:**
    - Stitch the Flesh: +1 revival, up to 6.
    - Evolutionary Pressure: rarity, effectiveness and rare-mod chance per map mod.
    - Improved Calibration: 25% more prefix **or** suffix effect.
    - Disengaged Safeties: maps are Irradiated.
    - Volatile Connection: 15% chance areas are Cleansed or Corrupted.
    - Head of the Snake: Citadel reveal and an extra pinnacle unique.
  - **Hilda:**
    - Breeding Season: 15% more rares and +25% rare-mod chance.
    - Ancient Inscriptions: +8% tablet effect for each *different* tablet type.
    - Mighty Prey: 25% chance of Powerful bosses.
    - Patient Battue: rares replaced by map bosses.
    - Claimed Territories: Overlord nodes add twice the content.
  - **Jado:**
    - Trove Seekers: unique strongboxes.
    - In The Wrong Hands: Powerful bosses drop +1 unique.
    - Unexpected Missions: corrupted waystones get +1 mod.
    - Partial Translations: 0-40% tablet effect.
    - Long Days: 20% more random extra content.

### Key nodes per strategy [data names; picks are est.]
All names below were checked against the **live 0.5.5 graph** (none missing). The full lists with reasons are in
`atlas.json → strategies`.

| Strategy | Core nodes (0.5.5) | Tablets | Guide tier 0.5.4 [guide, Timesaver 2026-06-28] |
|---|---|---|---|
| **Juiced generic** | The Journey Ahead (choice: 6% pack / 15% eff / 10% rarity), Rising Danger, Bountiful Bloodlines, Expanding Hordes, Multiplying Monstrosities, Twin Threats, Adaptive Biology + Mutating Monsters (+1 rare mod, ≥100% rarity per mod), No Simple Battles, Nemesis Rising, To the Strong Go the Spoils, Risk and Reward, Enigmatic Intensification, Controlled Climates, Industrial Improvements (4th tablet on City maps), Grass/Swamp Mastery | generic Collector's / Brimming / Breeding / Abounding, Irradiated | B (6-20 div/h "if sustained") |
| **Breach** | Shape the Chains (Grow Quantity), Swelling Hives, Moment of Risk, Frantic Invasion, Study the Chains, Breeding Program, Growing Wealth, Reactive Hiveseeding | Breach: of the Horde / Form / Invasion | B (3-7) |
| **Ritual** | Tempting Offers, Magnanimous Offerings, Patient Devotion, From the Mists, Reborn in Shadow, Mysterious Rites, Traveller's Woe, Royal Tithe, Prayer and Pledge, Hour of the Nameless | Ritual: of Sacrifice / Omens / Prayers. In 0.5.5, more than one Ritual tablet adds an extra altar | A (4-12) |
| **Delirium** | The mirrors... the mirrors!, Is that the best you've got?!, Come on! Face me!, Get out of my head!, These demons are all your own..., I know your childhood fears..., You can't scare me anymore!, Is this about me... or you?, Recurring Nightmares | Delirium: of Mirrors / Phobia / Simulacrum | C (3-9, spiky) |
| **Expedition** | Calculated Investment (Quantity), Double or Nothing, Expanding Territory, Steady Development, Strategic Advantage, Sown Seeds, Gaining Traction, Feeling Lucky?, The Quest Continues | Expedition: of Runes / Knowledge / Power | S (10-20; 50 = ceiling) |
| **Abyss** | Balance of Power (Ulaman), Strange Aversions, From Below, Dark Depths, Sprawling Rupture, Lord of the Pit, Vile Treasures, Rotting Bones, Close to the Surface, Shadow of Undeath | Abyss: of Hollows / Schisms / Treasures | A (4-10) |
| **Essence** | The Chosen Path (Essences), Essence Dowsing, Crystalline Patterns, Inexplicable Alchemy, Crystalline Overgrowth, Intensifying Energies, Flawless Patterns, Corrupted Lattices, Harmonic Corruption, Overlord's Domain | Overseer (of Crystals), Crystallised prefix | n/a |
| **Boss / Citadel** | Fit for a King, Hard-Won Treasures, Pathkeepers, Overlord's Domain/Influence, Fabled Showdown (Favour the Villain), Eons of Domination, Runic Flare, Memories of the Vaal/Maraketh/Ezomytes/Karui, Warlord's Vendetta, Bring Me Your Leader | Overseer: of Hoards / Treasure / Pathways | n/a |
| **Strongbox** | The Chosen Path (Strongboxes), Intriguing Designs, Specialised Containers, Enchanted Locks, Inlaid Inscriptions, Bardiyan/Royal Craftsmanship, An Appropriate Vault, Hidden Compartments, Craftsman's Creed | of the Antiquarian, of Compartments | n/a (no 0.5 guide found) |
| **Rogue Exile** | The Chosen Path (Exiles), Wealthy Exiles, Here for the Same Reason, Uncommon Alliances, Famous Locals, The Deadliest Hunt, Legendary Duels, Competing Explorers, Competitive Archaeology, Man Trap | Exiled prefix, of the Exile | n/a |
| **Temple** | Atziri's Assets, Training and Preparation, Transcendent Progress, Power Relays, Efficient Arteries, Xipocado's Machinations, Expanded Designs, Riches of the Empire, Stolen Authority | Temple (guarantees Vaal Beacons) | S (3-8, steady) |

**Warning on guides [est.]:** several popular 0.5 guides use node names that are **not in the 0.5.5 tree**:
- Constant Crossroads: a legacy row that isn't in the graph.
- Deadly Evolution, Crystalline Growth, Ominous Portents, Promised Devotion and Wandering Path: not in the data.
- AOEAH also gives Spreading Darkness the wrong effect.

The app should only trust names from the extracted tree.

### How to build the tree from the game files [data]
1. **Graph:** `metadata/atlasskillgraphs/atlasskillgraph.psg` sits in the bundles, not in `tables\`. Extract it with
   `poe2x extract <Bundles2\_.index.bin> <out> metadata/atlasskillgraphs`. The Fortress layout is the second file,
   `endgamemaplayoutgraph.psg`.
2. **PSG v3 layout:**
   - u8 version, u8, then u8 orbit count, then the skills per orbit (1, 12, 24, 24, 72, 72, 72, 24, 72, 144);
   - roots: u32 count, then (u32 id, u32 0) each;
   - groups: u32 count, then per group f32 x, f32 y, u32 flags, u32, u8, u32 node count;
   - per node: u32 graph_id, u32 orbit, u32 orbit_index, u32 link count, then (u32 target, i32 curvature) each.
   - `graph_id` = `PassiveSkills.PassiveSkillGraphId`.
3. **Nodes:** the `passiveskills.json` rows with `SkillType == 1` give the name, icon, stats (indices into
   `stats.json`), IsNotable/IsKeystone, AtlasSubTree (an index into `atlaspassiveskillsubtrees.json`),
   IsRootOfAtlasTree, Requirement (the Fortress node gate) and `_unk67` (the area-level gate).
4. **Text:** `data/statdescriptions/atlas_stat_descriptions.csd` (+ endgame_map, map, atlas_variant), read with `scripts\csd.py`.
5. **Choice keystones:** `passiveskillvarianttypes.json` (whose Id is the keystone Id) plus `passiveskillvariants.json`
   (Type to Variant, where Variant is a PassiveSkills row) give the options.
6. **Position:** node = group xy + orbit radius at angle 2π·index/skills-per-orbit. The radii are assumed to be the
   character tree's. A test render came out correct: a symmetric main tree plus 6 separate subtree islands.
7. **Allocation:** links are undirected. A node must connect back to its own tree's root (7 roots). Skip the
   `AtlasGenericMastery*` decor nodes.

---

## 2. Waystone modifiers [data]

**How rewards work in 0.5:**
- **[GGG 0.5.0]** Each mod carries its own reward: always "X% more Waystones found", plus **one** of the following:
  - pack size;
  - item rarity;
  - monster rarity (more magic/rare monsters **and** the same % more rare-mod chance);
  - monster effectiveness.
- **[GGG 0.5.0]** Rewards add up between waystone mods and multiply with atlas bonuses.
- **[GGG 0.5.0]** Prefixes are monster offence; suffixes are player or monster defences.
- **[GGG 0.5.0]** Effectiveness now gives only half its quantity/XP bonus.
- **[data]** Tiers come from item tags:
  - T1-5 "low" (area level 65-69);
  - T6-10 "medium";
  - T11-15 "high";
  - T16 "highest" (AL80).
- **[data]** Every mod has spawn weight 1. There are 108 mods in 27 families, cross-checked 108/108 against the
  client Mods table.

| Mod (T16 value) | P/S | Reward per mod | Danger [est.] | Answered by |
|---|---|---|---|---|
| Penetrating: pen 14-16% ele res | P | 20% wayst, 16% rarity | **deadly** | max res / ele max hit |
| of Exposure: -8 to -10% max res | S | 25% wayst, 10% pack | **deadly** | max res |
| of Smothering: 36-40% less life/ES recovery | S | 20% wayst, 15% rarity | **deadly** (leech/regen/recoup) | recovery/s |
| Destructive: +260-300% crit chance, +26-30% crit dmg | P | 15% wayst, 9% pack | risky (glass builds: deadly) | max hit incl. crits |
| Painful: 20-24% monster damage | P | 20% wayst, 25% monster rarity | risky | max hit |
| Profane / Frostbitten / Infernal / Thunderous: 20-24% extra chaos / cold / fire / lightning | P | 15% wayst + 15% rarity / 14% rarity / 16% eff / 8% pack | risky | that res + max hit |
| Shattering: break armour 30-45% of phys | P | 10% wayst, 19% monster rarity | risky (armour) | armour, phys max hit |
| Impacting: 100-110% stun buildup | P | 15% wayst, 13% eff | risky (low-life casters) | stun threshold |
| Fleeting: 10-15% attack/cast/move speed | P | 25% wayst, 9% pack | risky | max hit, mobility |
| of Overpowering: 120-130% ele ailment application | S | 15% wayst, 11% rarity | risky | ailment threshold / immunities |
| of Fatigue: 25-30% less cooldown recovery | S | 15% wayst, 12% rarity | risky (cooldown builds) | cooldown reliance |
| Shocking (ground) | S | 15% wayst, 7% pack | risky | shock immunity |
| Tough: 26-30% more monster life | P | 15% wayst, 23% monster rarity | fine (time) | DPS |
| Precise: 40-50% accuracy | P | 10% wayst, 7% pack | fine (evasion: risky) | evasion/deflect |
| Puncturing (bleed) / Venomous (poison) | P | 10% wayst + 13% eff / 7% pack | fine | ailment immunity |
| of the Prism: +35-40% monster ele res | S | 10% wayst, 14% rarity | fine (ele DPS tax) | pen/exposure |
| of the Unwavering: stun/ailment threshold | S | 10% wayst, 13% eff | fine (ailment builds lose DPS) | |
| of Obstruction: 26-30% less crit damage taken by monsters | S | 10% wayst, 18% monster rarity | fine (crit DPS tax) | |
| of Hexwarding: 40-50% less curse effect | S | 10% wayst, 10% rarity | fine (curse builds lose; note for **Blood Mage**) | |
| of Drought: 30-35% reduced flask charges | S | 15% wayst, 7% pack | fine | flask charge gain |
| Flaming / Sleet (ground) | S | 15% wayst + 15% eff / 12% rarity | fine | |
| Enervating (steal charges) | (unique) | 10% wayst, 7% pack | legacy: GGG says it no longer rolls | |

**Deadly for most builds [est.]:**
- **of Exposure**, **Penetrating** and **of Smothering**.
- The killer combinations:
  - Exposure + Penetrating + an "extra element" prefix;
  - T4 Destructive + Painful;
  - Smothering on sustain builds;
  - desecrated **of Cycling** (no damage for 3 of every 10 s) for bossing.
- GGG cut monster damage, penetration and -max-res values on 2026-05-25 because they were too strong [GGG].

**Expected reward per random mod at T16 [data, equal weights]:**
- A prefix averages 15.0% waystones, 2.9% pack, 3.2% rarity, 4.8% monster rarity and 3.0% effectiveness.
- A suffix averages 14.6% waystones, 2.0% pack, 6.2% rarity, 1.5% monster rarity and 2.3% effectiveness.
- A 3P+3S rare therefore averages about **89% more waystones, 15% pack, 28% rarity, 19% monster rarity and 16% effectiveness**.

**Other waystone layers:**
- **Instilled [data]:** each Liquid Emotion adds deliriousness plus one bonus:
  - Ire: 20% magic monsters;
  - Guilt: 8% pack;
  - Greed: 8% rarity;
  - Paranoia: 15% rare monsters;
  - Envy: 30% waystones;
  - Disgust: 30% tablets;
  - Despair: splinter stacks;
  - Fear: rare extra mod;
  - Suffering: unique extra mod;
  - Isolation, Melancholy, Ferocity and Contempt: 50% delirious, no bonus.
- **Desecrated waystone mods [data, 17]:**
  - Abyssal prefixes: extra abysses, overrun, Depths, magic pits, guaranteed pit rewards.
  - Suffixes: of Siphoning, Consumption, Grasping, Deceleration, Cycling, Retribution.
- **Removed in 0.5.0 [GGG]:** Baron's, Beastly, Brambled, Doryani's, Enervating, Faridun's, Hallowed, of Nemeses,
  Perennial's, Rusted and Sacrificial. Extra projectiles were disabled 2026-05-25.
- **Revivals:**
  - [poe2db] More mods means fewer revivals.
  - [data] Doryani adds +1, up to 6.
  - The exact formula is **unverified**.

---

## 3. Tablets [data + GGG]

**The 8 types:** Breach, Expedition, Delirium, Ritual, Abyss, Temple, Overseer (empowers the map boss) and
Irradiated (raises area level). Each has **10 uses**; unique tablets have 1-5.

**Mods:**
- 13 generic prefixes:
  - Collector's 8-12% rarity, Breeding 5-7% pack, Brimming 25-35% rares, Teeming 30-40% magic,
    Abounding 15-20% monster rarity, Challenger's effectiveness;
  - one extra essence / exile / circle / spirit;
  - gold, XP, rare chests.
- 11 generic suffixes:
  - of Undertaking (+1-2 random map mods), of the Cartographer (30-40% waystones), of the Nemesis, of Contest;
  - extra shrine/strongbox, and chance for content.
- 7-13 suffixes per mechanic tag. The full lists are in `atlas.json → tablets`.

**Rules:**
- Up to **3 tablets per map** [0.5.5d], plus one more on City maps with Industrial Improvements [data].
- Empty slots add random league content.
- Same-type tablets stack [GGG 0.5.0].
- Orb of Chance works on tablets [GGG].
- Rare tablets (+1 mod) only come with Reverse Transcription / Partial Translation [data].
- Irradiated and Overseer tablets have to be unlocked on the atlas (Eons of Contamination / Eons of Domination).
- Since 2026-05-25, Abyss tablets only enable Abyss; they no longer add +1 abyss.

**Pairing and value:** the pairing per strategy is in the strategies table above.
- Tablets are items, not exchange currency, so the toolkit DB has no price for them. The calculator should value a
  tablet as (reward per use × uses), with the price from the overlay or trade link [est.].

---

## 4. Map rolling

Prices are a snapshot from the toolkit DB: poe.ninja, Forbidden Rites, late league, 2026-11-21 08:40 UTC,
1 div = 473 ex. League-start prices will differ.

| Method | Cost | What you get | When [est.] |
|---|---|---|---|
| White | 0 | no mods, most revives | weak build / sustain only |
| Magic (Transmute + Aug) | ~2 ex | about 30% waystones, 5% pack, 9% rarity | early maps |
| **Alchemy (4 mods) + 2 Exalted** | ~6 ex | about 89% waystones, 15% pack, 28% rarity, 19% monster rarity | **default** on every kept T15/16 your build survives |
| Chaos Orb | ~41 ex | swaps 1 mod | only to remove a deadly mod on an invested stone |
| Chaos + Omens of Chaotic Rarity/Quantity/Monsters/Effectiveness (up to 3) | 37-350 ex each | rerolls **all** mods while **excluding** that reward type [GGG 0.5.0]; 3 omens force the 4th type | top juicers only |
| Vaal Orb | ~9 ex | [guide, U4N/Maxroll] about 25% each: nothing / tier ±1 rerolled / one side kept, other reforged / both kept + 0-4 extra mods (up to 10) | finished 6-mod T15/16; the odds are **not confirmed for 0.5** |
| Instill Liquid Emotions | 0.3-11 ex | see above | cheap: almost always worth it |
| Desecrate (bones) | varies | Abyssal prefix or a nasty suffix | Abyss farming |

**Note:** "Quantity = pack size" for the omen is my inference. Every waystone mod carries waystone chance, so the
omen can't mean that.

**What top players do [guide, low]:**
- Alchemy + Exalt to 6, avoid the deadly mods with a search string, instill, then Vaal the best.
- Run 3 tablets of one mechanic, or mix types for Hilda's bonus.
- Expedition and Temple were the steadiest earners in 0.5.4.
- **Re-roll vs run [est.]:** reroll only while the cost is small next to the map's yield (it is, at ~6 ex). Never
  Chaos/Annul a plain stone; buy or run a new one.

---

## 5. The in-game search box

- **Max length: 250 characters [GGG 0.5.0 notes].** It was 50 before. Some mid-2026 guides still say 50. Check it in
  the client.
- **Matched text [GGG 0.5.0]:** since 0.5.0 the search matches the **advanced** item text (the Ctrl+Alt+C format).
- **Syntax [forum guide 2025-09 + Maxroll]:**
  - space-separated terms are AND;
  - "quotes" make one term with spaces;
  - `!` at the start of a term excludes;
  - `|` is OR inside a term, and `( )` groups;
  - regex tokens work: `.`, `.+`, `[a-z]`, `[0-9]`, `\` escape.
- **Case:** case-insensitive [est., PoE 1 behaviour].
- **Quirks:**
  - quotes, spaces and `!` all count toward the limit;
  - numbers have to be built from digit classes;
  - short fragments can hit other mods, so the generator must test each fragment for uniqueness against all 108 mod texts;
  - property lines on waystones (revives, totals) were matched in 0.4; confirm the 0.5 line names from a copied waystone.
- **Common patterns (described, not copied):**
  - one negated alternation of short unique fragments of the avoid-list;
  - positive fragments for the reward type you want;
  - a "revives 0" match to find 6-mod stones.
- **Licence:** poe.re / poe2.re are AGPL. Copy nothing; link only.

---

## 6. 1.0 watch-list

- **2026-11-06 [GGG]:**
  - 1.0 launches 2026-12-11; patch notes come about a week earlier.
  - Conquerors of Wraeclast adds castles and factions, and commanders who can be **delegated Atlas progression**.
  - Re-export the tree, mods and tablets after the patch.
- **2026-11-09 [Maxroll ExileCon recap]:**
  - "No plans for major difficulty increase in the endgame".
  - Multi-choice atlas nodes stay.
  - Fewer deaths per area and more waystone mods is the liked direction.
  - Questline teleports.
  - Hunting-ground maps reset when a castle changes hands.
  - Champion Rares "might be added to the endgame".
- **2026-11-15 [UnGeek interview, Rogers]:** the late endgame was "getting stale". The passive tree rework moves
  jewel sockets into clusters.
- **Not found:** any statement about waystone or tablet mod changes for 1.0.

---

## What I couldn't verify
- Vaal Orb outcome odds on waystones in 0.5.x (the guides are from 2025 and contradict each other on tier-up odds).
- Exactly what "Omen of Chaotic Quantity" excludes (pack size inferred).
- The revival formula.
- The number of Liquid Emotions per waystone.
- The 0.5 property-line names on waystones.
- The tablet-slot rule (3 max is confirmed; what decides 1-3 isn't).
- Main-tree points per Precursor Tower or pinnacle (guides only).
- Case-insensitivity of the search.
- That `_unk67` is the area-level gate (inferred from its 70/75 values plus a guide).
- Divines/hour figures: guide claims, some from seller sites.
- Tablet prices: not in the local DB.
- Mobalytics, the PoE 2 wiki, the poe2db property lines and vulkk were blocked (403 / bot wall).
