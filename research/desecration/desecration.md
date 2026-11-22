# Desecration: bones, the Well of Souls and desecrated mods

**What this is:** how Path of Exile 2's desecration crafting works, written so the Craft lab (`poe2_craft`) can plan it,
simulate it and price it. The game's own data comes first (build 26744644, patch 0.5.x). The public web fills in what
the data can't show.

**Confidence tags:** every finding has one.
- **high:** the game files or GGG's patch notes.
- **medium:** several community sources agree, or the data strongly suggests it.
- **low:** only one source, or our own reading of an unnamed data column.

The machine-readable version is [desecration.json](desecration.json). The scripts are in [scripts/](scripts/).

## In one minute

1. Use a **bone** on a **Rare** item. The item gets one **Unrevealed Desecrated** prefix or suffix. If the item is
   already full, a random mod is removed to make room.
2. Take the item to the **Well of Souls**. You are offered **3 mods** for that side, pick **1**, and that's the mod.
3. Each choice can be a normal mod from the item's pool or an **Abyss-exclusive** mod from one of three lineages:
   Ulaman, Amanamu or Kurgal. **Omens** let you:
   - pick the side;
   - force a lineage;
   - reroll the 3 choices once;
   - remove the desecrated mod again.
4. An item can hold only **one** desecrated mod.

## 1. Bones

Bones drop from Abyss pits (the Abyssal Trove) and from the chests in the Abyssal Depths (game text, high; Maxroll,
high). Every bone has the same description, "Desecrates a Rare …". Bones stack to **20** and need a **Rare** item.

| Bone | Used on (item classes from the game data) | Limit | Exclusive-option value* | Lineage omens |
|---|---|---|---|---|
| Gnawed Jawbone | Weapons (all 1H/2H, bows, crossbows, spears, quarterstaves, flails, talismans, sceptres, wands, staves) and Quivers | **Max item level 64** | 0 | no |
| Preserved Jawbone | same | none | 0.08 | yes |
| Ancient Jawbone | same | **Min modifier level 40** | 0.08 | yes |
| Gnawed Rib | Body Armour, Helmet, Gloves, Boots, Shield, Buckler, Focus | Max item level 64 | 0 | no |
| Preserved Rib | same | none | 0.08 | no |
| Ancient Rib | same | Min modifier level 40 | 0.08 | no |
| Gnawed Collarbone | Amulet, Ring, Belt | Max item level 64 | 0 | no |
| Preserved Collarbone | same | none | 0.08 | yes |
| Ancient Collarbone | same | Min modifier level 40 | 0.08 | yes |
| Altered Collarbone | Amulet, Ring, Belt, "with a chance for otherworldly modifiers" | none | 0.08 | no |
| Preserved Cranium | Jewel (Unstable: rising chance to destroy the jewel each use) | none | 0.08 | no |
| Preserved Vertebrae | Waystone (no longer drops since 0.4.0) | none | 1.0 | no |

\* The "exclusive-option value" is an unnamed column in the game table `AbyssBenchTicketTypes`. See section 2.

**Item classes, limits, stack size and descriptions** come from `AbyssBenchTicketTypes`, `CurrencyItems` and
`BaseItemTypes` (high).

**What the limits mean in game terms** (game keyword text, high):
- **Maximum Item Level:** "You cannot use this currency on items above this level."
- **Minimum Modifier Level:** "Added random Modifiers are at least this level or higher, except if a specific
  Modifier type would be excluded entirely." Such bones also can't be used on items below that item level. So:
  - Ancient bones need item level 40 or higher.
  - They offer mods of level 40 or higher.
  - A mod type whose best tier is below 40 keeps that best tier.

**Lineage omens** need Preserved or Ancient bones on weapons, quivers or jewellery. We read this from an unnamed data
column, and it matches the omen text "Weapon or Jewellery" (medium). Using a lineage omen with any other bone gives the
in-game error "Omen is incompatible with this Desecrating item".

**What a bone does to the item** (high: game keyword text and poe2db):
- **Adds one unrevealed mod.** The game's own rule says: "Desecrating an item adds an Unrevealed Desecrated modifier.
  If modifiers are full then a random modifier is also removed."
- **No open affix needed.** On a full item the bone acts like a Chaos Orb that leaves a hidden mod. One guide
  (poe2craft) says you need an open slot. The game text says otherwise.
- **The unrevealed mod takes a prefix or suffix slot.** The item shows it as "Desecrated Prefix" or "Desecrated
  Suffix".
  - **Which side:** random, unless an omen of Sinistral or Dextral Necromancy forces it. Random side is high
    confidence. A 50/50 split is assumed (medium).
  - **Side of the removed mod on a full item:** our best guess is that a random mod is removed first and the new mod
    goes into the freed side. Not confirmed (low).
- **One per item.** "Items with Desecrated Modifiers cannot be Desecrated again" (game text). Since 0.5.0 desecrated
  mods also no longer count as crafted mods (patch notes, high).
- **Mark of the Abyssal Lord.** Essence of the Abyss adds this mod. Desecrating an item that has it always removes the
  Mark and adds an Unrevealed mod "of a higher tier" (game text, high). Nothing public says what "higher tier" means
  (low).

## 2. The reveal (Well of Souls)

**Where:** the Well of Souls is reached from the world map pin ("Click to travel to the Well of Souls"). The game text
reads: "Place an item with an Unrevealed Desecrated Modifier into the slot to reveal its options, then select one to be
placed on the item." The 0.3.0 notes say you choose one of **three** options (high). An item sitting in the Well slot
can't be modified.

**How the 3 options are drawn: best-supported model**

| Step | What happens | Confidence |
|---|---|---|
| Side | All 3 options are on the side of the unrevealed mod. | medium (wiki snippet, logical) |
| Pool | Each option comes from the item's **normal** mod pool or from the **Abyss-exclusive** pool for that item class and side. poe2db: "may include base modifiers" unless an omen guarantees a lineage. | medium-high |
| Exclusive chance | Per option: **8%** exclusive for Preserved / Ancient / Cranium / Altered bones, **0%** for Gnawed, **100%** for Vertebrae. This is the unnamed column `_unk6` in `AbyssBenchTicketTypes`. | **low** (our reading; no public source explains it) |
| Normal draws | Normal spawn weights, filtered by item level and the bone's minimum modifier level, like an Exalted Orb. The real weights are **not** in the game files (every weight there is 1), so the app keeps its equal-weights model. | medium |
| Exclusive draws | Every exclusive mod has weight 1 in the data, so the draw is even among the ones allowed for that class and side. | medium |
| Repeats | Assumed: the 3 options are 3 different mod groups, and none shares a group with a mod already on the item. | low |

The 0% for Gnawed bones fits on its own terms: every lineage mod is **level 65** and Gnawed bones only work up to item
level 64, so Gnawed bones can never show a lineage mod. That gives the model some support.

**What the model predicts:**
- **Preserved or Ancient bone, at least one exclusive option:** 1 − 0.92³ ≈ **22%** per reveal.
- **With Omen of Abyssal Echoes (6 options seen in total):** 1 − 0.92⁶ ≈ **39%**.

Treat these as estimates. Players' impressions are that lineage mods are "rare" but not vanishingly rare, which fits.

**Omens at the reveal**
- **Omen of Abyssal Echoes** (game text, high): "the next time you reveal Desecrated modifiers you can reroll the
  options once". The UI button is "Reroll Modifier Options".
  - Guides say all 3 options are replaced and you can't go back to the first set (medium).
  - It must be active before you press Reveal.
- **No other reveal omen** exists in the game data. The other abyss omens act when the bone is used.

## 3. Desecrated mods (the exclusive pool)

All of them sit in mod domain 28 ("desecrated") in `Mods`, tagged `unveiled_mod`. There are **299** affix rows, of
which **294 can roll**. **Every exclusive mod is a single tier** with a value range (no T1/T2 ladder) and weight 1.

| Pool | Rows (can roll) | Notes |
|---|---|---|
| Equipment: Jawbone / Rib / Collarbone | 200 (197) | Lineage mods, all level 65: Amanamu 69, Ulaman 65, Kurgal 63 |
| Jewels: Preserved Cranium | 44 (44) | Level 1, named "Lightless" / "of the Abyss", no lineage |
| Waystones: Preserved Vertebrae | 19 (17) | Map mods (more Abyss pits, Abyss boss, etc.) |
| Altered Collarbone ("otherworldly") | 36 (36) | Breach/Genesis mods, only reachable through the bone's `breach_desecration` tag |

**Lineages** show on the item as "Ulaman's / Amanamu's / Kurgal's" (prefix) and "of Ulaman / of Amanamu / of Kurgal"
(suffix):
- Ulaman is the Sovereign, matching Omen of the Sovereign.
- Amanamu is the Liege, matching Omen of the Liege.
- Kurgal is the Blackblooded, matching Omen of the Blackblooded.

Rough themes from guides (low): Kurgal is cold and mana, Ulaman is lightning and physical, Amanamu is fire and chaos.

**Exclusive equipment mods per item class** (prefix / suffix):

| Class | P / S | Class | P / S |
|---|---|---|---|
| Amulet | 11 / 20 | Body Armour | 0 / 13 |
| Ring | 7 / 15 | Helmet | 0 / 17 |
| Belt | 9 / 12 | Gloves | 0 / 17 |
| Quiver | 3 / 5 | Boots | 0 / 15 |
| Bow | 8 / 9 | Shield | 0 / 21 |
| Crossbow | 7 / 8 | Buckler | 0 / 19 |
| Spear | 8 / 9 | Focus | 6 / 12 |
| 1H / 2H Mace | 8 / 9 | Wand | 6 / 9 |
| Talisman | 9 / 9 | Staff | 7 / 7 |
| Quarterstaff | 6 / 6 | Sword, Axe, Dagger, Claw, Flail | 3 / 3 each |
| Sceptre | 0 / 0 | | |

Some patterns in that table:
- **Armour pieces have no exclusive prefixes.** A Rib that lands on a prefix can only show normal prefixes (high:
  data and poe2db).
- **Swords, axes, daggers, claws and flails** only get the 6 generic weapon mods: elemental penetration, attack cost
  efficiency, spirit reservation and skill cost as life.
- **Sceptres** have none (poe2db agrees).

**Mods only desecration can give** include:
- +1 to Level of all Skills (amulet, Ulaman);
- +1% to all maximum Resistances (shields);
- the dual Chaos resistances;
- mods that take armour, evasion or energy shield from the equipped body armour (amulets);
- empowered-attack and totem mods;
- the jewel "damage and penetration" pairs.

The full list is in `desecration.json` (`mod_pool`), with:
- `text`;
- `side`;
- `lineage`;
- `item_classes`;
- `level`;
- `tier_group` (the mod family; normal mods in the same family block it);
- `spawnable`.

**Disabled rows** (weight 0, `spawnable: false`):
- Instant-leech gloves (removed in 0.5.0);
- reduced movement-speed penalty boots (removed in 0.4.0);
- an old quarterstaff chaos/ailment mod;
- the two "of Union" waystone mods (disabled in 0.5.0).

**Data quirks:** 14 rows have a lineage tag in the spawn table that differs from the mod's own lineage tag (for
example, the Kurgal/Amanamu mace mods carry `ulaman_mod` in their spawn tags). One talisman row is named "of Ulaman"
but tagged Kurgal. The JSON uses the **displayed name** as the lineage and lists the other tag in `lineage_conflict`.
For these rows it is unknown which lineage a lineage omen honours (low).

## 4. Omens that affect desecration

The text of each is the game's own (high). The interpretation is marked separately where needed.

| Omen | Effect | effect_type | When |
|---|---|---|---|
| Omen of Sinistral Necromancy | next Desecration adds only a prefix | `force_side` prefix | bone use |
| Omen of Dextral Necromancy | next Desecration adds only a suffix | `force_side` suffix | bone use |
| Omen of the Sovereign | next Weapon or Jewellery Desecration guarantees a random **Ulaman** mod | `force_lineage` | bone use |
| Omen of the Liege | same for **Amanamu** | `force_lineage` | bone use |
| Omen of the Blackblooded | same for **Kurgal** | `force_lineage` | bone use |
| Omen of Putrefaction | next Desecration replaces **all** mods with up to **6** Unrevealed mods and **corrupts** the item | `replace_all_unrevealed_and_corrupt` | bone use |
| Omen of Abyssal Echoes | reroll the reveal options once | `reveal_reroll` | reveal |
| Omen of Light | next Orb of Annulment removes only the Desecrated mod | `annul_only_desecrated` | annul |
| Omen of Whittling (general) | next Chaos Orb removes the lowest-level mod; an unrevealed mod counts as level 1 | `chaos_remove_lowest` | chaos |

Notes on the omens:
- **Lineage omens:** the wording ("guarantee a random Ulaman modifier") promises at least one option of that lineage.
  Whether all 3 options become that lineage isn't published (low). Model them as "1 of the 3 options is a random
  exclusive mod of that lineage for the class and side; the other 2 are drawn normally." They don't work with Ribs,
  Crania, Vertebrae, Altered or Gnawed bones.
- **Abyss omens and drop areas:** since 0.5.0 they drop only in areas of level 65 or higher.
- **The Necromancy omen and Putrefaction** happen when the bone is used. They can be combined with a lineage omen,
  presumably (low).

## 5. Items with an unrevealed mod

- **It counts as an affix:** yes. It fills a prefix or suffix slot and counts toward the 3/3 limit (high).
- **Desecrate again:** no, the game says "This item already has a Desecrated Modifier" (high).
- **Chaos / Annulment:** they can hit it like any other mod. Omen of Light aims Annulment at it. Whittling + Chaos
  removes it as a level-1 mod (medium). This is how you undo a bad desecration before revealing.
- **Exalted Orb:** fills any other free slot (medium).
- **Divine Orb:** nothing to reroll on an unrevealed mod (low).
- **Fracturing Orb, Vaal Orb:** no source either way (unknown). Omen of Putrefaction leaves a corrupted item with
  unrevealed mods that can still be revealed, so corruption probably doesn't block the reveal (low).
- **Recombinator:** carries at most one desecrated mod ("Can only select one Desecrated modifier", game text, high).
- **Trading:** no rule against trading or listing an unrevealed item was found (low). Don't assume a market price for
  unrevealed items.

## 6. What a desecration step consumes (for pricing)

| Step | Items used |
|---|---|
| Desecrate | 1 bone: the right body part for the class, and the tier for the item level and floor you want. Gnawed for ilvl ≤ 64. Ancient for a level-40 floor. |
| Pick the side | + 1 Omen of Sinistral or Dextral Necromancy |
| Force a lineage | + 1 Omen of the Sovereign, Liege or Blackblooded (Preserved or Ancient Jawbone / Collarbone only) |
| Reveal | free; + 1 Omen of Abyssal Echoes for one reroll |
| Undo | Orb of Annulment + Omen of Light, or Chaos Orb + Omen of Whittling (unrevealed only) |
| Lottery | Omen of Putrefaction + bone (corrupts; up to 6 unrevealed mods) |

All the bones and omens above are Currency Exchange items, so the app can price them from its database.

## 7. Patch history

| Patch | Change | Confidence |
|---|---|---|
| 0.3.0 (Aug 2025) | Abyss league adds bones, the Well of Souls, desecrated mods and the abyss omens (omens now stack to 10). | high |
| 0.3.1 | Whittling highlights desecrated mods. The Unstable Desecration keyword is added for jewels. The Well shows more detail. | high |
| 0.4.0 (Dec 2025) | Abyss moves into the core game. Preserved Vertebrae no longer drop. The movement-penalty mod is removed and the staff ailment-magnitude mod is buffed. Altered Collarbone (Breach) appears in the data around then (source and patch not confirmed, low). | high |
| 0.5.0 (May 2026) | Instant-leech desecrated mods can no longer roll. Abyss omens drop only in level 65+ areas. The waystone "of Union" mod is disabled. Desecrated mods no longer count as crafted, and an item can have only 1. | high |
| 1.0 (2026-12-11) | Nothing desecration-specific announced. Re-run the scripts on the 1.0 game files. | medium |

## What the app should model

**Firm rules (high):**
1. A bone needs a Rare item of its classes.
   - Gnawed: item level ≤ 64.
   - Ancient: item level ≥ 40, and offered mods are level ≥ 40 (except a mod type whose best tier is lower, which
     keeps that tier).
2. Using a bone adds 1 unrevealed mod, prefix or suffix. The side is random, or forced by a Necromancy omen. If that
   side is full, a random existing mod is removed. *Simplest model:* remove a random mod first if the item has 6, then
   add on a free side.
3. Only 1 desecrated mod per item, revealed or not. No second bone until it is removed.
4. The reveal shows 3 options of the same side. The player picks 1. Abyssal Echoes swaps all 3 for a new 3, once.
5. The exclusive pool is `mod_pool` filtered by class and side and `spawnable`:
   - every exclusive mod is a single tier, weight 1;
   - lineage mods are level 65;
   - armour slots have no exclusive prefixes;
   - sceptres have none.
6. Omen of Light + Annul removes the desecrated mod. Whittling + Chaos removes an unrevealed one.
7. Putrefaction: wipe the item, add up to 6 unrevealed mods, corrupt it.

**Odds model:**

```
for each of 3 options:
    if random() < bone.exclusive_option_chance:   # 0.08 Preserved/Ancient, 0 Gnawed, 1.0 Vertebrae
        pick uniformly from exclusive mods for (class, side)
    else:
        pick from the normal pool for (class, side, ilvl, min_modifier_level) with the app's usual weights
options are 3 different mod groups, none blocked by mods already on the item
lineage omen: replace one option with a uniform pick from that lineage's exclusive mods for (class, side)
```

**Uncertain, so label it in the UI:**
- the 8% per-option chance (our reading of a data column);
- whether options repeat groups;
- whether a lineage omen makes 1 or all 3 options that lineage;
- the real normal-pool weights (not in the game files);
- fracturing, Vaal and trading with an unrevealed mod;
- the lineage of the 14 data-quirk rows;
- what Altered Collarbone's "chance for otherworldly modifiers" is (it uses the same 0.08 column, so probably the
  same per-option model with the Genesis pool).

## Sources

- **Game files, build 26744644** (read-only, in `<data folder>\gamefiles\26744644\tables`):
  - Mods
  - Tags
  - ModFamily
  - ModType
  - BaseItemTypes
  - CurrencyItems
  - AbyssBenchTicketTypes
  - ItemClasses
  - KeywordPopups
  - ClientStrings

  The stat text comes from the RePoE export (`<data folder>\data\repoe\mods.min.json`, `base_items.min.json`).
- **GGG patch notes:**
  - 0.3.0: https://www.pathofexile.com/forum/view-thread/3826682
  - 0.3.1: https://www.pathofexile.com/forum/view-thread/3862213
  - 0.4.0: https://www.pathofexile.com/forum/view-thread/3883495
  - 0.5.0: https://www.pathofexile.com/forum/view-thread/3932540
- **poe2db:**
  - https://poe2db.tw/us/Desecrated_Modifiers
  - https://poe2db.tw/us/Omen_of_Abyssal_Echoes
  - https://poe2db.tw/us/Omen_of_Putrefaction
  - https://poe2db.tw/us/Altered_Collarbone
- **vaal.tools:** https://www.vaal.tools/mechanics/desecrated_modifiers/
- **Maxroll Abyss guide:** https://maxroll.gg/poe2/resources/abyss
- **poe2craft:** https://poe2craft.com/guides/abyss-well-of-souls. Low confidence; it disagrees with the game on open
  slots and on desecrating twice.
- **poe-vault:** https://www.poe-vault.com/poe2/news/this-poe2-crafting-mistake-could-ruin-your-best-items
- **Not reachable:** poe2wiki.net blocked automated reading, so its claims here come from search snippets only.

**Re-run on a new build:**

```
python scripts/extract_desecration.py <tables_dir> --repoe <repoe_dir> --out scripts/desecration-data.json
python scripts/build_json.py scripts/desecration-data.json --out desecration.json
```
