# PoE 2 drop rates: what the public web has (researched 2026-11-20)

Data file: `drop-rates.json` (229 entries, 64 distinct sources). Each entry has item, mechanic, rate, unit,
conditions, patch, source URL, source kind and confidence. The generator script was a one-off; the JSON is the
record.

**Short version:** GGG does not publish base drop weights for PoE 2, and nobody has datamined them, because the
weights live on the server. poe2db shows only drop levels and atlas or tablet modifier text. What exists is:
1. **Official patch-note multipliers** ("+80% delirium splinters", "doubled runes", "Divine Orbs are now more common").
   These are high confidence, but they are relative changes, not absolute rates.
2. **Per-boss unique rates** from the Prohibited Library Discord and poe2wiki samples (100 to 1,000 kills). These are
   medium confidence and are the best data in the set.
3. **Creator farming sessions** (YouTube runs logged by farmofexile.com). These give counts per N maps for one
   setup. Most of the per-map numbers come from here.
4. **Guides and forum posts.** These are low confidence and often written by currency-seller sites.

Patch labels as the sources use them: 0.2 Dawn of the Hunt (Apr 2025), 0.3 Third Edict / Rise of the Abyssal
(Aug 2025), 0.4 Fate of the Vaal (late 2025), 0.5 Return of the Ancients / Runes of Aldur (May 2026), 0.5.5
Forbidden Rites (Sept 2026). This is a little different from the timeline in the brief, where Fate of the Vaal is
~May 2026.

---

## How to use this for "profit per map"

- Use the **per-map entries from creator sessions** as a strategy-specific EV baseline, not as a universal rate.
  Each one is tied to a setup (tablets, atlas, tier).
- Treat GGG multipliers as patch-to-patch scaling only.
- Bossing entries are per kill. To turn them into per-map figures you need fragment and key sustain, and no rate
  for that exists publicly except where it is listed below.
- When several sources disagree, take the one with the biggest sample and the newest patch. That is the "best
  estimate" column below.

---

## Per mechanic

### Base currency
| Item | Best estimate | Conditions / source | Confidence |
|---|---|---|---|
| Exalted Orb | ~7.6/map (0% rarity) to ~11/map (100%); 15/map T7, 9.9/map T15 | Ronarray 0.2, 30 maps per setup; forum T7 vs T15, 20 maps each, 200% rarity, Oct 2025 | medium |
| Divine Orb | 0.13-0.35/map in normal juiced mapping (0.2-0.3); 0.62/map in 0.5.5 juiced Delirium (50 maps); ~1.5/map in Viridian Wildwood (14 maps) | farmofexile sessions | medium (counts are small) |
| Chaos Orb | ~0.8-2.2/map (0% vs 100% rarity); 2.1-3.3/map breach maps | Ronarray; forum | medium. Ronarray's 0% figure is 23 in one write-up and 43 in another |
| Vaal Orb | 2.3/map (0%), 4.2/map (100-200%) | Ronarray | medium |
| Orb of Alchemy | ~2.1-2.8/map | Ronarray | medium |
| Orb of Annulment | ~0.05-0.17/map | several | low |
| Greater/Perfect orbs | T15: Greater Exalted 0.35/map, Perfect Exalted 0.05/map | forum T15 | low |
| Mirror of Kalandra | Estimates run from 1 in 75k to 1 in 26M kills | all speculation | low (useless) |

GGG multipliers: rare currency +20-30% (0.2.0g). In 0.5.0, Divines became more common, Greater/Perfect orbs
somewhat rarer, and Transmutation/Augmentation significantly rarer. None of these came with a number. Item rarity
mostly changes **which** currency drops, not how many, and Divine gains from rarity are too small to separate from
noise at 30 maps.

### Ritual
- **Best per-map data:** 42 T15/T16 Rite of the Nameless maps in 0.5.5 (MisoxShiru). Omen of Whittling 0.31/map,
  Sinistral Annulment 0.095, Dextral Annulment 0.071, Sinistral and Dextral Erasure 0.024 each.
- **Tribute:** ~17k per non-city Rite map and 20-30k per city map. Rerolls run 10-26 per city map and cost ~1,000
  tribute each.
- 3-4 altars per Ritual map. Since 0.2.0 at least one omen always appears in favours, and 0.2.1 made the rarest
  omens 6x more frequent.
- **King in the Mists, d4 (100 runs):** Beetlebite 49%, Ingenuity 30%, Burden of Shadows 10%, Pragmatism 7%, From
  Nothing 4%. It always drops at least one omen. No rate exists for the Ritualistic Reliquary Key.
- **Gaps:** no omen chance per altar, no per-omen weights, no Audience with the King rate (only "+50%" in 0.2.0g),
  and the city-chain session counts have no stated sample.

### Breach (reworked in 0.5: Hiveblood, Wombgifts, Genesis Tree)
- **Catalysts:** ~617 per hour from ~150k Hiveblood (≈4.1 per 1,000 Hiveblood), with a full type mix in the JSON.
  Since 0.5.0 catalysts come only from the Genesis Tree.
- **Hiveblood:** ~700-800 per breach in T14-15 (one guide; low confidence).
- **Splinters:** only pre-0.5 anecdotes (20-40 per breach in 0.1, 60-80 with quantity tablets) plus 0.2.0g's +50%.
  300 splinters make a Revelatory Wombgift, which grows into a Breachstone.
- **Genesis odds (datamined text):** Breachlord Sac is 0.3% of birthed currency, a splinter stack 10%, Essence of the
  Breach 2%.
- **Gaps:** splinters or Hiveblood per breach in 0.5.x, Wombgift drop counts, Xesht's Reliquary Key (only an
  unsourced ~1.5%), and Breachstone drop chance.

### Delirium
- **Best estimate:** ~157 Simulacrum Splinters per map, or 0.52 Simulacrum per map, with a T16 waystone and one
  Delirium Tablet (50 maps, 0.5.5).
- **Heavier juice:** four tablets per map reached 1.93 Simulacrums per map over 15 maps. Splinters from tablet
  Delirium cap at 300 per map.
- **Untargeted mapping:** ~1 Simulacrum per 20-30 T11+ maps (estimate).
- **Distilled emotions (pre-0.5, 15 waves):** the weights halve per tier (Ire 50%, Guilt 25%, ... Isolation 0.1%),
  with ~60-90 emotions per Simulacrum. 0.5 cut the Simulacrum to 7 waves, so these need rescaling.
- **Liquid emotions:** one is guaranteed per Delirium boss (0.4). Ancient Liquid Emotions are 20% of finds with the
  node.
- **Tangmazu's Reliquary Key:** under 10% (upper bound only).
- **Gaps:** liquid emotion drops per map, current 7-wave emotion counts, and Grand Mirror chance.

### Expedition and Verisium
- Olroth appears in ~1 in 8 logbooks of level 79+ (older data). Styrn always drops a logbook (0.5.3).
- 0.2.0g doubled Artifacts and gave Exotic Coinage +50%.
- **Hourly sessions:** 16-27 raw Divines per hour (low confidence). One 13-hour 0.5.0 run is in the JSON with all
  its currency counts.
- **Verisium:** the only firm number is that 600 raw Verisium make one Liquid Verisium. One rough author estimate
  puts it at ~7,000 Verisium per dozen remnants.
- **Gaps:** logbook drop chance per runic monster or per expedition, artifacts per expedition, Perfect Flux rate
  (only "guaranteed from Fallen Stars rumours"), Verisium per remnant, Uhtred's Runic Fork (only "well over 100
  kills").

### Abyss
- **Best per-map data:** 35 maps in 0.5.5 (MisoxShiru, Unforeseen Consequences tablet). Omen of Light 0.29/map,
  Abyssal Echoes 0.60/map, Preserved Cranium 0.17/map, Ancient Rib 0.11/map, Ancient Jawbone 0.11/map, Kulemak's
  Invitation 0.14/map.
- **Second source:** Omen of Light 0.4-0.7/map (~30 maps, seller site). In 0.5.5 omens shifted from maps to the
  Abyssal Depths.
- **Vessel of Kulemak (100 runs):** one Ancient bone per run (Jawbone 36%, Rib 35%, Collarbone 29%), Divine 16%.
- Kulemak's Invitation drops 100% from Tasgul or Vandroth. The bottleneck is their rare Depths variant.
- **Gaps:** bones per Abyss pit or trove, Depths spawn chance, Gnawed and Preserved bone rates.

### Ultimatum / Trial of Chaos
- At least one Soul Core per completed run; guides say 1-3. Each of the three wave-10 bosses drops one Trialmaster
  fragment.
- **Gaps:** per-core weights, Inscribed Ultimatum drops, the Trialmaster's Reliquary Key, and The Adorned (one
  uncited ~2% claim, not recorded).

### Essences, runes, idols
- **Essences (0.2):** 0.96/map with atlas passives only (50 maps), 1.2/map with tablets (20 maps). Greater
  essences ran 0.09/map and corrupted 0 in 70 maps. 0.5.0 lowered base spawn chances.
- **Runes:** only "doubled drop rate" in 0.2.0. No absolute rate.
- **Idols (0.4 augment items):** nothing published.

### Bossing (per kill, see JSON for every unique)
- **Arbiter of Ash (235 kills, wiki):** Morior Invictus 48%, Prism of Belief 23%, Sacred Flame 12%, Arbiter's
  Reliquary Key 0.5%. One other source says the key is 1%.
- **Xesht (~1,000 runs):** Beyond Reach 22-25%, Skin of the Loyal 6% at d4.
- **Aberration (562 kills) and Bodach (100 kills):** full tables in the JSON.
- **Reliquary keys** have *dynamic* rates, driven by the rarity of the supporter foil pool. Every key figure is
  low confidence.

### Waystones and tablets
- All of this is official mechanics. T1 final bosses drop a waystone 100% of the time, and the chance scales down
  by tier.
- **Boss waystone chance:** Radiant Waystones +15%, small nodes +6%, Overseer tablet +5-8%. Since 0.5.0b,
  Pathkeepers gives +15% boss waystone quantity and three other nodes give +10% each.
- **Corrupting a waystone:** 25% chance of ±1 tier. One 0.1 sample of 387 corruptions had 10.8% reach T16.
- **Gaps:** there is **no measured sustain rate per tier** for 0.5. Tablet drops only have 0.1 anecdotes (~1 in
  100+ maps). Farm setups use 0.1-0.3 tablets per map (10-use tablets), which helps the cost side.

---

## The biggest gaps (nothing public found)
1. Absolute base currency weights (per 1,000 drops or per monster) for any orb.
2. Waystone sustain percentage by tier for 0.5.x.
3. Omen chance per Ritual altar, and per-omen weights.
4. Breach splinters, Hiveblood and Wombgifts per breach in 0.5.x.
5. Expedition logbook, artifact and Perfect Flux rates, and Verisium per remnant.
6. Soul Core, rune and idol drop rates. Essences only have 0.2 data.
7. Audience with the King, Twilight Reliquary Key and most other Reliquary Keys (dynamic by design).
8. Liquid emotion drops per map, and current 7-wave Simulacrum emotion counts.

## Which sources to trust
- **Trustworthy:**
  - GGG patch notes (pathofexile.com forum, mirrored on poe2db `Version_x.y.z` pages);
  - poe2db modifier text (what a node or tablet does, exactly);
  - Prohibited Library samples summarised by Mobalytics (100-1,000 boss runs);
  - poe2wiki boss tables (via farmofexile).
- **Useful but setup-bound:**
  - farmofexile.com strategy pages. They are AI-parsed and then human-checked from creator videos. Counts are
    session totals. Check the stated map count; some tables have no sample stated.
  - Ronarray's 0.2 rarity tests.
  - The forum T7 vs T15 run.
- **Anecdotal / be careful:**
  - mmoexp, aoeah, timesaver, boostmatch, levelupper, sportskeeda. Several are currency or boost sellers, and their
    numbers are often unsourced or inconsistent.
  - Single forum posts.
  - All Mirror figures.
- **Could not be read:**
  - Reddit is blocked for this agent.
  - poe2wiki.net is behind Anubis bot protection.
  - Mobalytics returns 403.
  - archive.org was refused.
  - The Prohibited Library data and the wiki tables were only reachable through search snippets or secondary
    pages. Reading Reddit threads, the poe2wiki boss and Simulacrum pages, and Mobalytics' drop-rate tables in a
    normal browser would probably add numbers, especially the full emotion table and the Xesht table.

## Video sources worth watching (numbers not in text form)
- Slipperyjim8's rarity study, ~1,800 rares, 0.1: youtube `G8MMJJDF86Q`
- Ronarray's rarity tests, 0.2: youtube `fgMnNTjKSS0`, `k0ioI_k2-o8`
- Creator sessions behind farmofexile:
  - MisoxShiru: `a_O5tamDhR4`, `_Ig-0iiksAU`
  - DeadRabb1t: `2Xa4IBd11f0`
  - XTheFarmerX: `9geBdXsPi0A`, `PK_GubzWCXM`
  - Masterer Mitch: `BIxn4Vz_6LY`
  - KingPinUwU: `dxJBGuX01u8`, `5J_UrM9pdYo`

## Added 2026-11-20 (sites the research agent couldn't reach)

101 more entries, tagged `browser-2026-11-20` in the notes and added by `research/add_browser_rates.py` (safe to re-run).
- **Mobalytics guides by sirgog**, built from Prohibited Library run logs. These are 0.1-era pages, updated Feb–Mar 2025:
  - Xesht at difficulty 0–1 and 4, from about 1,000 runs.
  - Arbiter of Ash at difficulty 2–3 and 4 with Witness to History, from hundreds of runs (1.2 items per run).
  - The King in the Mists at difficulty 1 and 4 (100 runs).
  - The 150-splinter Simulacrum's emotions per run. Weights halve at each tier: about 35 Ire, 18 Guilt, 9 Greed,
    9 Paranoia ... 0.14 Isolation. Not auto-priced, because the emotion names and tiers changed after 0.3.
- **poe2wiki boss drop tables** give the unique chance per kill for:
  - Olroth (0.3.0);
  - Zarokh;
  - the Trialmaster;
  - Xesht;
  - the Arbiter of Divinity;
  - the King in the Mists;
  - the Arbiter of Ash;
  - the Simulacrum.
  They include each Reliquary Key at about 0.5–1.5%. The Aberration (n=562), Vessel of Kulemak (0.5.4, n=200),
  Bodach and Atziri pages say they have tables, but the tables don't use % cells, so they weren't read.
- **Reddit** was blocked by the Claude in Chrome extension's safety rules, so nothing from there.
- **Caution:** priced today, Olroth comes to about 83 div per kill (Uhtred's Exodus at 18% × ~440 div) and the wiki's Xesht
  table to about 43 div per kill (Uul-Netol's Embrace ~3%). Those chances come from old or approximate tables, and
  today's high prices suggest the items are rarer now, so treat both as optimistic.
- **Later the same day:** the remaining four wiki boss pages turned out to be lists ("Item (x%)"), not tables, and
  were read:
  - **Aberration** (0.5.0, n=562): always one Starlit Ore (Venerable/Warding 37%, Veridical 15%, Revered 8%) or
    Twisted Empyrean 3%. It can also drop Olroth's Conviction/Hubris (5% each) and the Emergent runes (0.7–3.5%).
  - **Vessel of Kulemak** (0.5.4, n=200, ring taken immediately): The Unborn Lich ~38%, Undying Hate ~4%, The Master's
    Reach ~2%.
  - **Bodach** (0.5.0, n=100): Vestige of Darkness 56%, Forgotten Warden 26% ... It can also drop Carved Majesty 2%,
    Carved Tenacity 1%, Carved Cunning under 1%.
  - **Atziri's Vault** (0.4.0, n=100): Atziri's Step 35%, Drillneck 32%, Atziri's Rule 12% ... plus Zerphi's Infamy 11%
    and Atziri's Impatience 8%.
- **Ritual uniques:** players report uniques, including Mageblood, from Ritual rewards. No public rate exists anywhere,
  so this is a qualitative entry. The Farming tab shows it as upside ("also") without changing the numbers.
