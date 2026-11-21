# Boss readiness (PoE 2) - research for Exile Oracle Build Lab

Researched 2026-11-21. Game version: **0.5.5** (Forbidden Rites event, live 2026-09-04, next to Runes of Aldur).

## Read this first

- **1.0 date:** the sources I found say **2026-12-11**, not 12-04 (MassivelyOP, PCGamesN). GGG says big balance changes wait for 1.0, so every number here needs a re-check after 1.0.
- **No real Uber bosses in 0.5.x.** Patch 0.5.0 removed the old Calamity (uber) fragments and gave every pinnacle a **quest** version and a harder **repeat/farm** version. Reports on 0.5.5 say Uber bosses are not being added yet. In this file, `uber` means the harder repeat/empowered version (Arbiter of Divinity harder keys, Xesht 150 splinters, empowered Kulemak, repeat Bodach).
- **No public per-hit damage numbers.** No guide I found gives 0.5.x boss hit sizes or community max-hit targets. Every `max_hit_*` check is **estimated** (confidence low). Life and DPS tiers come from community heuristics (Switchblade, Timesaver). Those sites say they are heuristics, and several of them sell carries.
- **How the checks work:** value >= `min` = **ready**; `risky_below` <= value < `min` = **risky**; value < `risky_below` = **not yet**.
- poe2wiki.net blocks automated fetches (Anubis), so wiki facts come from search-result snippets of wiki pages. poe.ninja and mobalytics returned 403 errors.

## How the estimates were made

- **Tiers.** Switchblade (verified vs 0.5.2) groups bosses as Entry (Zarokh, Trialmaster), Mid (Xesht, Olroth, Simulacrum, Kulemak), Hard (Arbiter of Ash, King in the Mists) and Apex (Arbiter of Divinity), with life 3k/4k/5k/6k (about double for ES) and DPS 200K/500K/1M/1M+. Bosses it does not list (Atziri, Aberration, Raven Trickster, Bodach) are placed using ExpCarry's 0.5.4f difficulty ranking: Kulemak < Atziri < Aberration < Bodach < Raven Trickster < Xesht < Arbiter of Ash < Arbiter of Divinity.
- **Max hit.** Guides say Arbiter of Ash combos 'chunk 50%+' of a 'comfortable' pool and that some hits 'usually kill'. I set each boss's max-hit target at about 1.5x its tier's life guideline (Mid 6k, Hard 7-8k, Apex 9k, harder Divinity 10k), on the boss's main damage types.
- **Harder versions.** One step above the base: life +500-1,000 and DPS x1.5-2. Xesht 150 splinters has ~5x the HP of the 50-splinter fight (14.5M vs 2.9M), but its DPS target is capped at 3x (1.5M) because PoB DPS against phases and uptime doesn't scale linearly.
- **Resistances.** 75% is the cap everywhere. Fire 80% for the Arbiter of Ash and cold 80% for Olroth follow Switchblade's '80-85%' / '80-82%' advice. Lightning for the Arbiter of Divinity: Switchblade says 87%+ but gives no reasoning, so I used 80% (quest) and 85% (harder) as a conservative compromise.
- **Chaos.** The wiki says the campaign penalty does not apply to chaos res, so 0% is the floor. 20-30% is suggested where chaos/'shadow' damage appears (Xesht, Bodach).

## General endgame guidelines

| Check | Threshold | Why | Source |
|---|---|---|---|
| fire_res / cold_res / lightning_res | >= 75 (capped) (%) | Default max resistance is 75%; maps and bosses are balanced around capped elemental resistance. | Maxroll: PoE2 Defence guide (updated 2026-09-18) <https://maxroll.gg/poe2/getting-started/defence-guide>; Timesaver: T15 map DPS requirement (0.5.5, 2026-09-08) <https://timesaver.gg/blog/poe2-t15-dps-requirement-0-5-5> |
| max resistance hard cap | 90 (%) | Max-res modifiers can raise the cap to at most 90%. Overcapping max fire/lightning helps for the Arbiters. | Maxroll: PoE2 Defence guide (updated 2026-09-18) <https://maxroll.gg/poe2/getting-started/defence-guide> |
| campaign resistance penalty | -10% per act step: Act 2 -10, Act 3 -20, Act 4 -30, interludes -40 / -50, endgame (area level 65+) -60 (% to all elemental res) | PoB already includes the penalty for the chosen act/endgame setting; check PoB is set to endgame. (0.4/0.5 campaign layout; 1.0 adds campaign content, so re-check after 1.0.) | PoE2 Wiki: Maximum Resistances (act penalty table; read via search snippet, site blocks bots) <https://www.poe2wiki.net/wiki/Maximum_Resistances> |
| chaos_res | >= 0 always; 20-30% for mixed or chaos fights (%) | The wiki says campaign negative resistance is not applied to chaos res, and chaos res is consistent across the endgame. Chaos damage removes twice as much ES, so ES builds need it more. 20-30% figure is an estimate. | PoE2 Wiki: Chaos resistance <https://www.poe2wiki.net/wiki/Chaos_resistance>; Maxroll: PoE2 Defence guide (updated 2026-09-18) <https://maxroll.gg/poe2/getting-started/defence-guide>; 20-30% is estimated |
| campaign resistances | >= 30 (%) | Maxroll: stay above at least 30% elemental res during the campaign. | Maxroll: PoE2 Defence guide (updated 2026-09-18) <https://maxroll.gg/poe2/getting-started/defence-guide> |
| dps for T15 maps | 100K barely / 200K-500K comfortable / 1M+ juiced and pinnacle prep (PoB DPS (single target)) | Timesaver's own estimates; GGG publishes no figure. | Timesaver: T15 map DPS requirement (0.5.5, 2026-09-08) <https://timesaver.gg/blog/poe2-t15-dps-requirement-0-5-5> |
| dps for pinnacle bosses | 200K entry / 500K mid / 1M+ hard and apex (PoB DPS) | Community heuristics (Switchblade tiers, verified vs 0.5.2). | Switchblade Gaming: Pinnacle boss minimum HP and DPS thresholds (verified vs 0.5.2) <https://www.switchbladegaming.com/path-of-exile-2/endgame-boss-guide/> |
| life_es for pinnacle bosses | 3,000 entry / 4,000 mid / 5,000 hard / 6,000 apex (life); about double as ES (life (+ES)) | Switchblade tiers; Switchblade itself calls them heuristics. | Switchblade Gaming: Pinnacle boss minimum HP and DPS thresholds (verified vs 0.5.2) <https://www.switchbladegaming.com/path-of-exile-2/endgame-boss-guide/> |
| life_es for red maps (T15-16) | >= 4,000 (risky below 3,000) (life+ES) | Timesaver gives ~3,000+ EHP as a bare minimum; raised to 4,000 to be conservative. Players report juiced T15-16 trash hitting for 3-5k. | Timesaver: T15 map DPS requirement (0.5.5, 2026-09-08) <https://timesaver.gg/blog/poe2-t15-dps-requirement-0-5-5>; Steam community discussion: juiced T15-16 hits (anecdotes) <https://steamcommunity.com/app/2694490/discussions/0/598514944991864195>; 4,000 is estimated |
| max hit per type for red maps | >= 5,000 each (risky below 3,500) (damage) | Estimated from player reports of 3-5k hits from juiced trash; no published guideline exists. | estimated |
| armour vs physical hits | armour = 12x the hit for 50% reduction (6x: 33%, 36x: 75%; max 90%) (ratio) | Damage Reduction = Armour / (Armour + 12 x hit). Use PoB's max physical hit, which already includes this. | Maxroll: PoE2 Defence guide (updated 2026-09-18) <https://maxroll.gg/poe2/getting-started/defence-guide> |

## Bosses

### Zarokh, the Temporal (Trial of the Sekhemas)  [normal]  (source version 0.5.4)

**Unlock:** Clear the final floor of the endgame Trial of the Sekhemas. Hardest clear uses the 'Last Flame' relic with Honour at 1 (Timesaver 0.5.4).

**Dangerous hits:**
- Hourglass / time mechanics (unknown): Telegraphed arena mechanics (Timesaver). Damage types not verified. Sekhemas damage also drains Honour, which PoB does not model.

| Stat | Ready at | Risky below | Unit | Confidence | Why / source |
|---|---|---|---|---|---|
| fire_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| cold_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| lightning_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| life_es | 3,000 | 2,500 | life+ES | medium | Entry-tier pinnacle (Switchblade tier 'Entry': 3,000+ life). ES-only builds: the source suggests roughly double the number in ES (chaos hits remove double ES). (Switchblade Gaming) |
| dps | 200,000 | 100,000 | PoB combined DPS | medium | Switchblade 'Entry' tier: 200K+ sustained DPS. Risky band = T15 'barely clears' figure. (Switchblade Gaming + more) |
| chaos_res | 0 | -20 | % | low | Never go into a boss with negative chaos res; there is no campaign penalty on chaos res in PoE2, so 0% is the floor. (estimated) |
| max_hit_physical | 4,000 | 3,000 | damage | low | Entry-tier boss (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |

### The Trialmaster (Trial of Chaos)  [normal]  (source version 0.5.5)

**Unlock:** Clear the endgame Trial of Chaos. In 0.5.5 Trials can run to 30 rooms and later rooms can drop all three Trialmaster Fragments in one run (GGG 0.5.5).

**Dangerous hits:**
- Sunder (physical): Big telegraphed physical hit (Timesaver Trialmaster guide, search snippet).
- Mortar (elemental): Elemental bombardment (same source).
- Room afflictions / Wager modifiers (varies): 0.5.5 Wager Modifiers can 'substantially increase a Trial's danger' (GGG).

| Stat | Ready at | Risky below | Unit | Confidence | Why / source |
|---|---|---|---|---|---|
| fire_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| cold_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| lightning_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| life_es | 3,000 | 2,500 | life+ES | medium | Entry-tier pinnacle (Switchblade tier 'Entry': 3,000+ life). ES-only builds: the source suggests roughly double the number in ES (chaos hits remove double ES). (Switchblade Gaming) |
| dps | 200,000 | 100,000 | PoB combined DPS | medium | Switchblade 'Entry' tier: 200K+ sustained DPS. Risky band = T15 'barely clears' figure. (Switchblade Gaming + more) |
| chaos_res | 0 | -20 | % | low | Never go into a boss with negative chaos res; there is no campaign penalty on chaos res in PoE2, so 0% is the floor. (estimated) |
| max_hit_physical | 4,000 | 3,000 | damage | low | Sunder is the big physical hit (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |

### Olroth (Expedition)  [normal]  (source version 0.5.2)

**Unlock:** Excavate the Kalguuran Tomb in an Expedition Logbook of area level 79+. In 0.5 Olroth drops the Shattered Triskelion that leads to The Aberration.

**Dangerous hits:**
- Cold attacks (cold): Switchblade: 75%+ cold res mandatory; 80-82% if under 5,000 life.

| Stat | Ready at | Risky below | Unit | Confidence | Why / source |
|---|---|---|---|---|---|
| fire_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| lightning_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| life_es | 4,000 | 3,000 | life+ES | medium | Mid-tier pinnacle (Switchblade tier 'Mid': 4,000+ life). ES-only builds: the source suggests roughly double the number in ES (chaos hits remove double ES). (Switchblade Gaming) |
| dps | 500,000 | 200,000 | PoB combined DPS | medium | Switchblade 'Mid' tier: 500K+ sustained. Risky band = the T15 'comfortable farming' floor. (Switchblade Gaming + more) |
| chaos_res | 0 | -20 | % | low | Mixed-damage fight; keep chaos res at least non-negative (estimated). (estimated) |
| effective_hp | 15,000 | 10,000 | PoB total EHP | low | Mid-tier pool (Estimated: example T15 build in search results had 7.2k ES / 16.6k EHP; scaled up per tier.) (estimated) |
| cold_res | 80 | 75 | % | medium | Switchblade: cold 75% mandatory, 80-82% suggested below 5,000 life. Conservative: 80% = ready. (Switchblade Gaming) |
| max_hit_cold | 6,000 | 4,500 | damage | low | Cold is the main threat (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |

### Omniphobia, Fear Manifest (Simulacrum / Delirium)  [normal]  (source version 0.5.5)

**Unlock:** Simulacrum (Delirium) waves; Omniphobia appears from around wave 3 (Timesaver). 0.5.5 removed its all-elemental resistance (GGG notes).

**Dangerous hits:**
- Wave pressure + boss hits (unknown): Specific hits and damage types not verified for 0.5.x.

| Stat | Ready at | Risky below | Unit | Confidence | Why / source |
|---|---|---|---|---|---|
| fire_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| cold_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| lightning_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| life_es | 4,000 | 3,000 | life+ES | medium | Mid-tier pinnacle (Switchblade tier 'Mid': 4,000+ life). ES-only builds: the source suggests roughly double the number in ES (chaos hits remove double ES). (Switchblade Gaming) |
| dps | 500,000 | 200,000 | PoB combined DPS | medium | Switchblade 'Mid' tier: 500K+ sustained. Risky band = the T15 'comfortable farming' floor. (Switchblade Gaming + more) |
| chaos_res | 0 | -20 | % | low | Mixed-damage fight; keep chaos res at least non-negative (estimated). (estimated) |
| effective_hp | 15,000 | 10,000 | PoB total EHP | low | Mid-tier pool (Estimated: example T15 build in search results had 7.2k ES / 16.6k EHP; scaled up per tier.) (estimated) |
| max_hit_physical | 6,000 | 4,500 | damage | low | Mid-tier boss, damage types unverified; physical used as the generic check (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |

### Vessel of Kulemak (Abyss)  [normal]  (source version 0.5.4)

**Unlock:** Kulemak's Invitation (from Tasgul/Vandroth per Timesaver) used at the Well of Souls, leading to the Black Cathedral (ExpCarry).

**Dangerous hits:**
- Physical attacks / teleport slams (physical): ExpCarry 0.5.4f.
- Lightning beams (lightning): ExpCarry.
- Cold damage + mines (cold): ExpCarry.
- Lightless Serpent Burning Ground (fire): Damage reduced in 0.5.4 (patch-note summary).

| Stat | Ready at | Risky below | Unit | Confidence | Why / source |
|---|---|---|---|---|---|
| fire_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| cold_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| lightning_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| life_es | 4,000 | 3,000 | life+ES | medium | Mid-tier pinnacle (Switchblade tier 'Mid': 4,000+ life). ES-only builds: the source suggests roughly double the number in ES (chaos hits remove double ES). (Switchblade Gaming) |
| dps | 500,000 | 200,000 | PoB combined DPS | medium | Switchblade 'Mid' tier: 500K+ sustained. Risky band = the T15 'comfortable farming' floor. (Switchblade Gaming + more) |
| chaos_res | 0 | -20 | % | low | Mixed-damage fight; keep chaos res at least non-negative (estimated). (estimated) |
| effective_hp | 15,000 | 10,000 | PoB total EHP | low | Mid-tier pool (Estimated: example T15 build in search results had 7.2k ES / 16.6k EHP; scaled up per tier.) (estimated) |
| max_hit_physical | 6,000 | 4,500 | damage | low | Slams (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |
| max_hit_lightning | 6,000 | 4,500 | damage | low | Beams (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |

### Vessel of Kulemak - empowered  [uber]  (source version 0.5.4)

**Unlock:** Same fight after empowering via Kurgal, Ulaman and Amanamu / Lich power (Timesaver, ExpCarry). GGG has not added true Uber bosses in 0.5.5.

**Dangerous hits:**
- Same kit, more damage and life (physical/lightning/cold): No numbers published.

| Stat | Ready at | Risky below | Unit | Confidence | Why / source |
|---|---|---|---|---|---|
| fire_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| cold_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| lightning_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| life_es | 5,000 | 4,000 | life+ES | medium | Hard-tier pinnacle (Switchblade tier 'Hard': 5,000+ life; poe2path also says 5,000+ for Arbiter of Ash). ES-only builds: the source suggests roughly double the number in ES (chaos hits remove double ES). (Switchblade Gaming + more) |
| dps | 1,000,000 | 500,000 | PoB combined DPS | medium | Switchblade 'Hard' tier and Timesaver: pinnacle bosses usually want 1M+ single-target with good uptime. (Switchblade Gaming + more) |
| chaos_res | 0 | -20 | % | low | Keep chaos res at least non-negative (estimated). (estimated) |
| effective_hp | 20,000 | 14,000 | PoB total EHP | low | Hard-tier pool (Estimated: example T15 build in search results had 7.2k ES / 16.6k EHP; scaled up per tier.) (estimated) |
| max_hit_physical | 8,000 | 6,000 | damage | low | Empowered slams (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |
| max_hit_lightning | 8,000 | 6,000 | damage | low | Empowered beams (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |

### Xesht, We That Are One (Breach) - 50/100 splinters  [normal]  (source version 0.5.4c)

**Unlock:** 0.5 'Waking the Dreamer': Breach Splinters -> Wombgift -> Breachstone; clear the Hive ladder, beat It That Was Tul and It That Was Esh for the Breachlord key, then the Twisted Domain (Timesaver, ExpCarry). HP ~2.9M (50 splinters) / ~6.5M (100).

**Dangerous hits:**
- Summon Tul: ice cones (cold): Freeze risk; bring freeze mitigation (Timesaver).
- Summon Esh: expanding explosion (lightning): Timesaver.
- Hand Smash / Burrow / Arm Slams (physical): Tracking slams, below ~60% HP the arm combo (Timesaver).
- Sun Orb (fire): Slow fire projectile (Timesaver).
- Mixed chaos threats (chaos): ExpCarry lists chaos among his damage.

| Stat | Ready at | Risky below | Unit | Confidence | Why / source |
|---|---|---|---|---|---|
| fire_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| cold_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| lightning_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| life_es | 4,000 | 3,000 | life+ES | medium | Mid-tier pinnacle (Switchblade tier 'Mid': 4,000+ life). ES-only builds: the source suggests roughly double the number in ES (chaos hits remove double ES). (Switchblade Gaming) |
| dps | 500,000 | 200,000 | PoB combined DPS | medium | Switchblade 'Mid' tier: 500K+ sustained. Risky band = the T15 'comfortable farming' floor. (Switchblade Gaming + more) |
| effective_hp | 15,000 | 10,000 | PoB total EHP | low | Mid-tier pool (Estimated: example T15 build in search results had 7.2k ES / 16.6k EHP; scaled up per tier.) (estimated) |
| chaos_res | 20 | 0 | % | low | ExpCarry lists chaos among Xesht's damage; 20%+ is a conservative estimate. (estimated) |
| max_hit_cold | 6,000 | 4,500 | damage | low | Tul cones (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |
| max_hit_lightning | 6,000 | 4,500 | damage | low | Esh explosion (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |
| max_hit_physical | 6,000 | 4,500 | damage | low | Slams (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |

### Xesht, We That Are One (Breach) - 150 splinters  [uber]  (source version 0.5.4c)

**Unlock:** Same entry with 150 splinters; ~14.5M HP, the 'toughest pure DPS check' of the three tiers (Timesaver 0.5.4).

**Dangerous hits:**
- Same kit as above (cold/lightning/physical/chaos): Higher HP; damage scaling not published.

| Stat | Ready at | Risky below | Unit | Confidence | Why / source |
|---|---|---|---|---|---|
| fire_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| cold_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| lightning_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| life_es | 5,000 | 4,000 | life+ES | low | Estimated one tier above the 50/100 version. ES-only builds: the source suggests roughly double the number in ES (chaos hits remove double ES). (estimated) |
| dps | 1,500,000 | 700,000 | PoB combined DPS | low | Estimated: HP is ~5x the 50-splinter fight (14.5M vs 2.9M, Timesaver); scaled from the mid-tier 500K guideline and capped at 3x because DPS checks are not linear. (estimated) |
| chaos_res | 30 | 0 | % | low | Estimated. (estimated) |
| effective_hp | 20,000 | 14,000 | PoB total EHP | low | Hard-tier pool (Estimated: example T15 build in search results had 7.2k ES / 16.6k EHP; scaled up per tier.) (estimated) |
| max_hit_cold | 8,000 | 6,000 | damage | low | Tul cones (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |
| max_hit_lightning | 8,000 | 6,000 | damage | low | Esh explosion (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |
| max_hit_physical | 8,000 | 6,000 | damage | low | Slams (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |

### Atziri, the Red Queen (Vaal Temple)  [normal]  (source version 0.5.4)

**Unlock:** Build Atziri's Temple, kill the Royal Architect, reach the Royal Access Chamber (area level 75+) (Timesaver, ExpCarry).

**Dangerous hits:**
- Flesh Bubble (physical): Lethal physical spell explosion in the second arena (ExpCarry).
- Fire rings / Fire runes (fire): ExpCarry.
- Lightning runes / storm markers (lightning): ExpCarry.
- Blood projectiles (physical): ExpCarry.

| Stat | Ready at | Risky below | Unit | Confidence | Why / source |
|---|---|---|---|---|---|
| fire_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| cold_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| lightning_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| life_es | 4,000 | 3,000 | life+ES | medium | Mid-tier pinnacle (Switchblade tier 'Mid': 4,000+ life). ES-only builds: the source suggests roughly double the number in ES (chaos hits remove double ES). (Switchblade Gaming) |
| chaos_res | 0 | -20 | % | low | Mixed-damage fight; keep chaos res at least non-negative (estimated). (estimated) |
| effective_hp | 15,000 | 10,000 | PoB total EHP | low | Mid-tier pool (Estimated: example T15 build in search results had 7.2k ES / 16.6k EHP; scaled up per tier.) (estimated) |
| dps | 1,000,000 | 500,000 | PoB combined DPS | low | A guide quoted in search results says 1.5M+ DPS for kills under 3 minutes (older Fate of the Vaal numbers); 1M used as 'ready'. Expcarry ranks her 2nd easiest. (Search-result summary of Atziri guides (game8 / mmojugg), Fate of the Vaal era + more) |
| max_hit_physical | 7,000 | 5,000 | damage | low | Flesh Bubble is the lethal hit (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |
| max_hit_fire | 6,000 | 4,500 | damage | low | Fire rings (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |

### The Aberration (Expedition / Verisium)  [normal]  (source version 0.5.4f)

**Unlock:** The Triskelion Reforged, made from Olroth's Shattered Triskelion through Expedition + Runeforging (ExpCarry 0.5.4f).

**Dangerous hits:**
- Mortar impacts / leg stomps (physical): ExpCarry.
- Verisium storm (unknown): ExpCarry.
- Cold and lightning beams (cold/lightning): ExpCarry.
- Web sequence (mechanic): Large web mechanic (ExpCarry).

| Stat | Ready at | Risky below | Unit | Confidence | Why / source |
|---|---|---|---|---|---|
| fire_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| cold_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| lightning_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| life_es | 4,000 | 3,000 | life+ES | medium | Mid-tier pinnacle (Switchblade tier 'Mid': 4,000+ life). ES-only builds: the source suggests roughly double the number in ES (chaos hits remove double ES). (Switchblade Gaming) |
| dps | 500,000 | 200,000 | PoB combined DPS | medium | Switchblade 'Mid' tier: 500K+ sustained. Risky band = the T15 'comfortable farming' floor. (Switchblade Gaming + more) |
| chaos_res | 0 | -20 | % | low | Mixed-damage fight; keep chaos res at least non-negative (estimated). (estimated) |
| effective_hp | 15,000 | 10,000 | PoB total EHP | low | Mid-tier pool (Estimated: example T15 build in search results had 7.2k ES / 16.6k EHP; scaled up per tier.) (estimated) |
| max_hit_physical | 6,000 | 4,500 | damage | low | Mortars/stomps (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |
| max_hit_cold | 6,000 | 4,500 | damage | low | Beams (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |
| max_hit_lightning | 6,000 | 4,500 | damage | low | Beams (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |

### The Raven Trickster, Tangmazu (Delirium)  [normal]  (source version 0.5.5)

**Unlock:** Grand Mirror -> Trial of Madness fog banks; full Deliriousness opens the quest Simulacrum, which gives Raven's Reflection; repeat with Raven's Reflections at the broken mirror in the Withered Willow (ExpCarry). 0.5.5 removed its all-elemental resistance (GGG notes).

**Dangerous hits:**
- Cold shards and walls (cold): ExpCarry.
- Lightning strikes (lightning): ExpCarry.
- Fire projectiles (fire): ExpCarry.
- Pillar attacks (physical): ExpCarry.
- Refraction beams (unknown): ExpCarry.

| Stat | Ready at | Risky below | Unit | Confidence | Why / source |
|---|---|---|---|---|---|
| fire_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| cold_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| lightning_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| life_es | 5,000 | 4,000 | life+ES | medium | Hard-tier pinnacle (Switchblade tier 'Hard': 5,000+ life; poe2path also says 5,000+ for Arbiter of Ash). ES-only builds: the source suggests roughly double the number in ES (chaos hits remove double ES). (Switchblade Gaming + more) |
| dps | 1,000,000 | 500,000 | PoB combined DPS | medium | Switchblade 'Hard' tier and Timesaver: pinnacle bosses usually want 1M+ single-target with good uptime. (Switchblade Gaming + more) |
| chaos_res | 0 | -20 | % | low | Keep chaos res at least non-negative (estimated). (estimated) |
| effective_hp | 20,000 | 14,000 | PoB total EHP | low | Hard-tier pool (Estimated: example T15 build in search results had 7.2k ES / 16.6k EHP; scaled up per tier.) (estimated) |
| max_hit_cold | 7,000 | 5,000 | damage | low | Ranked 5th of 8 by ExpCarry; between mid and hard (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |
| max_hit_lightning | 7,000 | 5,000 | damage | low | Lightning strikes (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |
| max_hit_fire | 7,000 | 5,000 | damage | low | Fire projectiles (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |

### The King in the Mists (Ritual)  [normal]  (source version 0.5.2)

**Unlock:** Offer Tribute until the Audience bar fills, then 'An Audience with the King' (Timesaver). In 0.5 his head (Head of the King) starts the Rite of the Nameless chain to The Bodach.

**Dangerous hits:**
- Boss kit (unknown): Damage types for 0.5.x not verified. Switchblade puts him in the 'Hard' tier with the Arbiter of Ash.

| Stat | Ready at | Risky below | Unit | Confidence | Why / source |
|---|---|---|---|---|---|
| fire_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| cold_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| lightning_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| life_es | 5,000 | 4,000 | life+ES | medium | Hard-tier pinnacle (Switchblade tier 'Hard': 5,000+ life; poe2path also says 5,000+ for Arbiter of Ash). ES-only builds: the source suggests roughly double the number in ES (chaos hits remove double ES). (Switchblade Gaming + more) |
| dps | 1,000,000 | 500,000 | PoB combined DPS | medium | Switchblade 'Hard' tier and Timesaver: pinnacle bosses usually want 1M+ single-target with good uptime. (Switchblade Gaming + more) |
| chaos_res | 0 | -20 | % | low | Keep chaos res at least non-negative (estimated). (estimated) |
| effective_hp | 20,000 | 14,000 | PoB total EHP | low | Hard-tier pool (Estimated: example T15 build in search results had 7.2k ES / 16.6k EHP; scaled up per tier.) (estimated) |
| max_hit_physical | 7,000 | 5,000 | damage | low | Hard tier, damage types unverified (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |

### The Bodach (Ritual) - quest  [normal]  (source version 0.5)

**Unlock:** Head of the King on the Effigy -> Rite of the Nameless (5 maps) -> 5 Call of the Shadows at Caer Tarth (Timesaver). Quest kill during 'Legacy of the Maji' has unlimited revivals (ExpCarry).

**Dangerous hits:**
- Fireball Drop / Rain of Fireballs / Flame Barrage (fire): Phase 1 (Timesaver).
- Shadow Beam / darkness corridor ground (chaos (likely)): 'Shadow' damage; the darkness ground damages and slows (ExpCarry). Chaos type is an assumption.
- Body Slam / teleporting hand / meteor slams (physical): Phase 3 (Timesaver, ExpCarry).

| Stat | Ready at | Risky below | Unit | Confidence | Why / source |
|---|---|---|---|---|---|
| fire_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| cold_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| lightning_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| life_es | 5,000 | 4,000 | life+ES | medium | Hard-tier pinnacle (Switchblade tier 'Hard': 5,000+ life; poe2path also says 5,000+ for Arbiter of Ash). ES-only builds: the source suggests roughly double the number in ES (chaos hits remove double ES). (Switchblade Gaming + more) |
| dps | 1,000,000 | 500,000 | PoB combined DPS | medium | Switchblade 'Hard' tier and Timesaver: pinnacle bosses usually want 1M+ single-target with good uptime. (Switchblade Gaming + more) |
| effective_hp | 20,000 | 14,000 | PoB total EHP | low | Hard-tier pool (Estimated: example T15 build in search results had 7.2k ES / 16.6k EHP; scaled up per tier.) (estimated) |
| chaos_res | 20 | 0 | % | low | Estimated: 'shadow' damage is probably chaos. (estimated) |
| max_hit_fire | 7,000 | 5,000 | damage | low | Fireball rain (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |
| max_hit_physical | 7,000 | 5,000 | damage | low | Meteor-style slams (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |

### The Bodach (Ritual) - repeat  [uber]  (source version 0.5)

**Unlock:** Repeat fights after the quest via 5 Call of the Shadows; later kills are at higher difficulty (Timesaver).

**Dangerous hits:**
- Same kit as the quest version (fire/chaos/physical): Harder; numbers not published.

| Stat | Ready at | Risky below | Unit | Confidence | Why / source |
|---|---|---|---|---|---|
| fire_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| cold_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| lightning_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| life_es | 5,500 | 4,500 | life+ES | low | Estimated one step above the quest version. ES-only builds: the source suggests roughly double the number in ES (chaos hits remove double ES). (estimated) |
| dps | 1,500,000 | 700,000 | PoB combined DPS | low | Estimated. (estimated) |
| chaos_res | 30 | 0 | % | low | Estimated. (estimated) |
| effective_hp | 22,000 | 16,000 | PoB total EHP | low | Hard-tier pool (Estimated: example T15 build in search results had 7.2k ES / 16.6k EHP; scaled up per tier.) (estimated) |
| max_hit_fire | 8,000 | 6,000 | damage | low | Fireball rain (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |
| max_hit_physical | 8,000 | 6,000 | damage | low | Slams (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |

### The Arbiter of Ash  [normal]  (source version 0.5.5)

**Unlock:** Burning Monolith inside the Precursor Fortress (Tier 6+ Waystones; Enigma Chambers Tier 10+). Quest: Crisis Fragments from the Enigma Chambers. Repeat: Ancient, Faded and Weathered Crisis Fragments from three different Citadels (Timesaver, ExpCarry). Old Calamity (uber) fragments can no longer be obtained in 0.5 (patch 0.5.0 notes).

**Dangerous hits:**
- Hallways (flame blasts with one gap) (fire): 'The killer' (Timesaver).
- Flame Seeds / Cascading Seeds (fire): Explode everywhere outside the safe circle (Timesaver).
- Baiting Flame Seeds + Ground Sunder (fire + physical): 'Either hit usually kills' (Timesaver).
- Phase 2 sword combo (physical): 'Deletes squishy characters'; combos and Diving Slam can 'chunk 50%+' (Timesaver).
- Blackflame (fire): Can block life and ES recovery (ExpCarry).

| Stat | Ready at | Risky below | Unit | Confidence | Why / source |
|---|---|---|---|---|---|
| cold_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| lightning_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| life_es | 5,000 | 4,000 | life+ES | medium | Hard-tier pinnacle (Switchblade tier 'Hard': 5,000+ life; poe2path also says 5,000+ for Arbiter of Ash). ES-only builds: the source suggests roughly double the number in ES (chaos hits remove double ES). (Switchblade Gaming + more) |
| dps | 1,000,000 | 500,000 | PoB combined DPS | medium | Switchblade 'Hard' tier and Timesaver: pinnacle bosses usually want 1M+ single-target with good uptime. (Switchblade Gaming + more) |
| chaos_res | 0 | -20 | % | low | Keep chaos res at least non-negative (estimated). (estimated) |
| effective_hp | 20,000 | 14,000 | PoB total EHP | low | Hard-tier pool (Estimated: example T15 build in search results had 7.2k ES / 16.6k EHP; scaled up per tier.) (estimated) |
| fire_res | 80 | 75 | % | medium | Switchblade: fire 75% mandatory, 80-85% recommended; Timesaver: overcap if possible. 0.5.5: boss now has fire resistance and cold vulnerability (GGG notes). (Switchblade Gaming + more) |
| max_hit_fire | 8,000 | 6,000 | damage | low | Most one-shots are fire (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |
| max_hit_physical | 7,000 | 5,000 | damage | low | Phase 2 sword combo (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |

### The Arbiter of Divinity - quest  [normal]  (source version 0.5.5)

**Unlock:** After the Arbiter of Ash: Patriarch Hall (Phya drops the Origin Spark) and Matriarch Hall (Phyx drops the Origin Cradle), both Tier 15 Waystones with limited attempts; combine into an Origin Core at the Origin Tower (Timesaver). Added in 0.5.0 (patch notes).

**Dangerous hits:**
- Divine Electrical Orbs / Chest Beam (lightning): Phase 1 (Timesaver, poe2path).
- Rain of Divine Lightning (lightning): Phase 2 AoE from ~40% HP; boss becomes much faster (Timesaver).
- Spear combos / Super Dash Thrust / Triple Spinning Slash (physical): ExpCarry: 'physical spear combinations'.
- Aspects of Divinity clones (mechanic): Collect Divine Power orbs for temporary immunity (Timesaver).

| Stat | Ready at | Risky below | Unit | Confidence | Why / source |
|---|---|---|---|---|---|
| fire_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| cold_res | 75 | 65 | % | medium | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| lightning_res | 80 | 75 | % | medium | Lightning is most of the damage (Timesaver, poe2path). Switchblade asks for 87%+ lightning (low confidence, unexplained); conservative compromise: 80% = ready for the quest fight, 85% for the harder version; under 75% = not yet. (Switchblade Gaming + more) |
| life_es | 6,000 | 5,000 | life+ES | medium | Switchblade 'Apex' tier: 6,000+ life or ~12,000 ES, plus 2+ defensive layers. ES-only builds: the source suggests roughly double the number in ES (chaos hits remove double ES). (Switchblade Gaming) |
| dps | 1,000,000 | 600,000 | PoB combined DPS | medium | Switchblade 'Apex': 1M+ sustained. Phase 2 speeds up, so a short phase 2 matters. (Switchblade Gaming + more) |
| chaos_res | 0 | -20 | % | low | No chaos threat documented; keep it non-negative (estimated). (estimated) |
| effective_hp | 25,000 | 18,000 | PoB total EHP | low | Apex pool (Estimated: example T15 build in search results had 7.2k ES / 16.6k EHP; scaled up per tier.) (estimated) |
| max_hit_lightning | 9,000 | 7,000 | damage | low | Most damage is lightning (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |
| max_hit_physical | 8,000 | 6,000 | damage | low | Spear combos (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |

### The Arbiter of Divinity - harder version  [uber]  (source version 0.5.5)

**Unlock:** 0.5.5: after the main Arbiter questline you can farm another set of Matriarch and Patriarch Halls for keys to 'an even more formidable version' (GGG 0.5.5 announcement). 0.5.5 gave the boss lightning resistance and fire vulnerability (patch notes).

**Dangerous hits:**
- Same kit, stronger (lightning/physical): No numbers published.

| Stat | Ready at | Risky below | Unit | Confidence | Why / source |
|---|---|---|---|---|---|
| fire_res | 75 | 65 | % | low | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| cold_res | 75 | 65 | % | low | Endgame content is balanced around capped (75%) elemental resistance; every 1% under cap is ~4% more damage taken at the cap. (Switchblade Gaming + more) |
| lightning_res | 85 | 75 | % | low | Lightning is most of the damage (Timesaver, poe2path). Switchblade asks for 87%+ lightning (low confidence, unexplained); conservative compromise: 80% = ready for the quest fight, 85% for the harder version; under 75% = not yet. (Switchblade Gaming + more) |
| life_es | 7,000 | 6,000 | life+ES | low | Estimated one step above the Apex tier (Switchblade gives 6,000+ for the base fight). ES-only builds: the source suggests roughly double the number in ES (chaos hits remove double ES). (estimated) |
| dps | 2,000,000 | 1,000,000 | PoB combined DPS | low | Estimated: 2x the base Apex guideline. (estimated) |
| chaos_res | 0 | -20 | % | low | Estimated. (estimated) |
| effective_hp | 30,000 | 22,000 | PoB total EHP | low | Above-apex pool (Estimated: example T15 build in search results had 7.2k ES / 16.6k EHP; scaled up per tier.) (estimated) |
| max_hit_lightning | 10,000 | 8,000 | damage | low | Most damage is lightning (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |
| max_hit_physical | 9,000 | 7,000 | damage | low | Spear combos (Estimated: no public per-hit numbers for 0.5.x; derived from the tier's life guideline and guide notes that big hits 'chunk 50%+' of a ~5k pool, so a max hit near 1.5x the life guideline survives one heavy hit.) (estimated) |

## What could not be verified

- Per-hit damage of any 0.5.x boss, and any community max-hit target. All max-hit numbers are estimates.
- Damage types for King in the Mists, Omniphobia and Zarokh in 0.5.x, and whether the Bodach's 'shadow' damage is chaos.
- Boss HP, except Xesht (Timesaver 0.5.4) and an older Arbiter of Ash figure (~5M normal / ~22.6M old uber, from before 0.5; the old uber is gone).
- The poe2wiki act penalty table could only be read as search snippets. It describes the 0.4/0.5 campaign (4 acts + interludes), and 1.0 may change it.
- What exactly the 0.5.5 'harder Arbiter of Divinity' changes.
- Sources left out: lootlore.online lists bosses that don't exist (for example 'Scion of the Vaal' and 'Storm Herald'), so it's unreliable.

## Sources

- [GGG forum: Forbidden Rites & 0.5.5 announcement (2026-08-27)](https://www.pathofexile.com/forum/view-thread/3999865)
- [Kami-Labs: PoE2 patch notes 0.5.5 (2026-09-03, mirrors GGG notes)](https://kami-labs.fr/en/path-of-exile-2/patch-notes-0-5-5-path-of-exile-2-forbidden-rites/)
- [Kami-Labs: PoE2 patch notes 0.5.0 Return of the Ancients (full notes, 2026-05-22)](https://kami-labs.fr/en/path-of-exile-2/poe2-patch-0-5-return-of-the-ancients-notes-complet-en/)
- [IGGM: 0.5.5 patch notes summary (Arbiter resist/vulnerability)](https://www.iggm.com/news/poe-2-0-5-5-patch-notes-how-ritual-expedition-reshape-forbidden-rites-farming)
- [PoE2 Wiki: Maximum Resistances (act penalty table; read via search snippet, site blocks bots)](https://www.poe2wiki.net/wiki/Maximum_Resistances)
- [PoE2 Wiki: Chaos resistance](https://www.poe2wiki.net/wiki/Chaos_resistance)
- [Maxroll: PoE2 Defence guide (updated 2026-09-18)](https://maxroll.gg/poe2/getting-started/defence-guide)
- [Maxroll: PoE2 Pinnacle bosses (Early Access, updated 2025-09-11; older roster)](https://maxroll.gg/poe2/resources/pinnacle-bosses)
- [ExpCarry: PoE2 pinnacle boss difficulty ranking (0.5.4f, rechecked 2026-08-13)](https://expcarry.com/poe-2-pinnacle-boss-difficulty-ranking)
- [Timesaver: Arbiter of Divinity guide (0.5)](https://timesaver.gg/blog/poe2-arbiter-of-divinity-guide)
- [Timesaver: Arbiter of Ash guide (0.5)](https://timesaver.gg/blog/poe2-arbiter-of-ash-guide)
- [Timesaver: Xesht guide (0.5.4c)](https://timesaver.gg/blog/poe2-xesht-guide)
- [Timesaver: The Bodach guide (0.5)](https://timesaver.gg/blog/poe2-bodach-guide)
- [Timesaver: PoE2 pinnacle bosses guide (0.5.4 roster)](https://timesaver.gg/blog/poe2-pinnacle-bosses-guide)
- [Timesaver: T15 map DPS requirement (0.5.5, 2026-09-08)](https://timesaver.gg/blog/poe2-t15-dps-requirement-0-5-5)
- [Timesaver: Trialmaster guide (0.5) - search-result snippet only](https://timesaver.gg/blog/poe2-trialmaster-guide)
- [Switchblade Gaming: Pinnacle boss minimum HP and DPS thresholds (verified vs 0.5.2)](https://www.switchbladegaming.com/path-of-exile-2/endgame-boss-guide/)
- [poe2path: Endgame bosses guide (0.5, June 2026)](https://poe2path.com/guides/poe2-endgame-bosses-guide/)
- [Search-result summary of Atziri guides (game8 / mmojugg), Fate of the Vaal era](https://game8.co/games/Path-of-Exile-2/archives/574807)
- [Steam community discussion: juiced T15-16 hits (anecdotes)](https://steamcommunity.com/app/2694490/discussions/0/598514944991864195)
- [MassivelyOP: Forbidden Rites (Sept 4) and 1.0 preview (2026-08-28)](https://massivelyop.com/2026/08/28/path-of-exile-2-previews-september-4s-forbidden-rites-league-and-1-0s-new-duelist-class/)
- [PCGamesN: Forbidden Rites league update](https://www.pcgamesn.com/path-of-exile-2/update-forbidden-rites-league)
