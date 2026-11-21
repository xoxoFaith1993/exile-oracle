# PoE 2 market trends: league day 1 to week 10 (researched 2026-11-21)

This is research step R7 for Exile Oracle's "Oracle". The structured version for the app is `market-trends.json`
(patterns, strategies, sources, plus Divine-priced curves for 42 key items and the daily Div:Ex:Chaos ratios).
Sources are listed in `sources.md`. Tags like **[S1]** refer to that list.

**The data.** It covers the last three launches:

| League | Patch | Start |
|---|---|---|
| Fate of the Vaal (FotV) | 0.4 | 2025-12-12 |
| Runes of Aldur (RoA) | 0.5 | 2026-05-29 |
| Forbidden Rites (FR) | 0.5.5 | 2026-09-04 |

All prices come from GGG's own Currency Exchange history **[S1]**:
- **Days 0-6:** daily medians from the app's league-start pull **[S2]**. `playbook.json` already covers these days **[S3]**.
- **Days 10, 14, 21, 28, 42, 56 and 70:** one sampled hour each, 20 hourly digests fetched for this report.
- **FR days 63-77:** daily medians from the app's own hourly sync.

Day 0 is the first 24 hours on the exchange. Everything is priced **in Divine Orbs**, because Exalted Orbs lose most
of their value in the first month, so Exalted prices make almost everything look like it rises.

**Labels used below:**
- **Data:** our numbers from [S1]/[S2].
- **Web:** a published source.
- **Inference:** my reading of the data, not directly measured.
- **[seller]:** a currency or boost seller's site (low trust).

**Limits:**
- Exchange items only. Unique items never go through the exchange, so there are **no measured unique curves** (see section 3).
- Days 10-70 are single hours, so ±20% noise is normal on thin items.
- Each "3/3" means the pattern showed in all three launches.

---

## 1. The big picture in eight lines

1. **Exalted Orbs lose value fast (high confidence, 3/3).** An Ex is worth 53-79% fewer Divines by day 6 and 83-92% fewer by day 28. Don't save in Ex.
2. **Div:Ex rises 6-13x from day 0 to its peak, which comes between week 2 and week 6, then slides back 25-34%** (3/3).
3. **Chaos gains on Divine in 0.5-style leagues (2/2 in 0.5).** FR went from 29 to about 8 Chaos per Div by day 14; RoA from 26 to 8-11. In Exalt terms a Chaos went from about 2 Ex to about 57 Ex in two weeks (FR).
4. **Scarce "sink" items rise 10-90x in Divines from day 1 to day 42** (3/3). These include:
   - Hinekora's Lock, Mirror, Architect's Orb and Crystallised Corruption;
   - the top crafting omens;
   - Trialmaster Fates, Preserved Cranium and Refined catalysts;
   - Uncut Spirit gems and chase lineage gems.
5. **Common drops crash 80-99% in Divines, mostly within 2 weeks** (3/3). These include:
   - low-tier and Greater/Lesser crafting orbs;
   - Diluted and low-tier liquid emotions;
   - common and Greater essences;
   - Preserved Ribs, weak omens and non-meta lineage gems;
   - low-level Uncut Support gems.
6. **Some items spike in week 1, then fall.** Soul cores such as Tacati peak around day 10 (3-11x) and are down 58-83% by day 42. Orb of Annulment peaks on days 10-21. Uncut Skill Gem (Level 20) peaks around days 6-14 in 2 of 3 leagues.
7. **The exchange is most liquid in weeks 1-4.** By week 6-10, volume is down 65-98% from its peak.
8. **Patches move prices fast.**
   - A new drop source crashed RoA's Ancient Collarbone 88% in a week (0.5.3).
   - GGG nerfs broken farms within about 1-2 weeks and has never rolled back legitimately farmed wealth **[S5, S6, S16]**.

---

## 2. Currency ratios across a league

### Ex per Divine (Data [S1]; d = league day)

| League | d0 | d2 | d6 | d10 | d14 | d21 | d28 | d42 | d56 | d70 | last |
|---|---|---|---|---|---|---|---|---|---|---|---|
| FotV 0.4 | 67 | 102 | 146 | 232 | **403** | 339 | 384 | 299 | 330 | 302 | - |
| RoA 0.5 | 41 | 66 | 87 | 105 | 132 | 235 | 387 | **553** | 464 | 375 | 506-544 (d108-119, thin) |
| FR 0.5.5 | 54 | 107 | 262 | 418 | 475 | 502 | 685 | **709** | 695 | 590 | 468 (d77) |

Cross-checks:
- **FR:** seller sites quote ~65 (Sep 5), ~180 (Sep 8), ~270 (Sep 10), ~740 (Oct 5, d31) and ~807 (Oct 16, d42) **[S10, S11 seller]**. These fit our curve within the usual single-hour noise. (Web)
- **0.3:** ~55 to ~280 in two weeks, then ~650 for a long period **[S19 seller]**. (Web)
- **0.1:** ~99 Ex per Div at day 22 (Dec 28 2024) **[S24]**. (Web)

**Pattern (3/3 in our data, and the same shape in 0.1 and 0.3 per the web):**
- The ratio roughly doubles in week 1 (FR: 4.8x).
- It doubles to triples again in weeks 2-4.
- It peaks between day 14 (FotV) and day 42 (RoA, FR).
- It then falls 25-34% by week 10-11.

Inference: late-league Ex gets scarcer relative to Div as players stop farming, and big spenders keep buying Ex for crafts.

### Chaos per Divine (Data [S1])

| League | d0 | d2 | d6 | d14 | d21 | d42 | d70 | last |
|---|---|---|---|---|---|---|---|---|
| FotV | 51 | 59 | 77 | 41 | 72 | 31 | 27 | - |
| RoA | 26 | 65 | 18 | 13 | 11 | 8 | 8 | - |
| FR | 29 | 18 | 10.5 | 8.3 | 7.2 | 8.7 | 9.9 | 11.4 |

- In both 0.5 leagues Chaos tripled against Divine in the first 1-2 weeks, then held at roughly 8-11 per Div. Web gives FR ~20 (Sep 5) and 10.8 (Oct 5) **[S10 seller]**, which agrees.
- In 0.4 Chaos was much weaker (30-80 per Div).
- **Inference:** Chaos became a premium crafting currency in 0.5, so it is a better short-term store than Ex. Check whether this holds in 1.0 during the first 48 hours before you rely on it.

### Other base and crafting currency (Divine price; Data)

**Rise and hold:**
- **Perfect Exalted:** +84% (RoA) and +62% (FR) by d6, about +90-135% by d42. In FotV it fell 56% by d42.
- **Perfect Chaos:** RoA 0.64 → 3.4, FR 0.81 → 5.4 by d21, and 12-13 Div by d70-77 in FR.
- **Greater Chaos:** about 3x by d10 in 0.5 leagues, then flat.

**Peak early, then fade:**
- **Orb of Annulment:** about 3-6x from d0 to its peak (FotV d10, FR d21, RoA d42), then 25-66% lower by the last sample.
- **Orb of Chance:** rises for 2-4 days, then falls 89-96% by d42.

**Crash:**
- **Greater Exalted:** -93/-93/-96% by d21.
- **Greater Jeweller's:** -96 to -99% by d14.
- **Perfect Jeweller's:** -73 to -85% by d28.
- **Transmutation and Augmentation lines, Regal, Alchemy:** -82 to -99% by d42.

**Volatile and patch-driven: Fracturing Orb.**
- FotV: 0.09 → 24.7 Div by d42. The 0.4 Immured Fury bug blocked its guaranteed source **[S13 seller]**.
- RoA: 1.6 → 9.2. FR: 3.1 → 4.9, then 8-9 late.
- Since 0.5.0 Fracturing needs atlas specialisation **[S4]**.

**Huge, steady risers:**

| Item | FotV | RoA | FR | Late price |
|---|---|---|---|---|
| Hinekora's Lock, d1 → d42 | 18 → 1,180 | 62 → 1,250 | 83 → 1,700 | 1,100-2,000 Div |
| Mirror of Kalandra, d2 → d42 | 194 → 6,730 | 387 → 5,310 | 985 → 5,410 | 4,500-9,000 Div |

Web Mirror prices agree: ~4,000 Div in 0.4 **[S7]** and 5,316 Div on FR Oct 5 **[S10 seller]**.

**Corruption sinks:**
- Architect's Orb, d0 → d42: 11x / 53x / 67x.
- Crystallised Corruption: 12x / 16x / 45x.
- Vaal Armourer's Infuser: 20x / 15x / 8x.

---

## 3. Item groups: what spikes, what crashes, when

All changes are in Divine terms; the ratio columns are d0 → d42 unless stated (Data [S1]).

| Group | Day 1-3 | Week 1 | Weeks 2-3 | Week 4+ | Day 1 → d42, FotV / RoA / FR | Confidence |
|---|---|---|---|---|---|---|
| Top crafting omens (Whittling, Light, Sinistral/Dextral Annulment and Erasure) | up | up | up | **up** (peaks d42-70) | Whittling 49x / 3x / 15x; Sinistral Annulment 32x / 2.9x / 13.5x (d1 start); Light 91x / 4.6x / 5.5x | high |
| Weak omens (Liege, Putrefaction, Sinistral Necromancy) | **crash** (-82%) | down | down | flat at the floor | -98 / -98 / -99% | high |
| Omen of Chaotic Quantity | up 4-26x by d6 | peak d6-21 | flat | down a little (FR -45% from peak) | | medium |
| Common soul cores (e.g. Tacati) | up | **peak about d10** (3-11x) | **crash** | low | peak → d42: -83 / -76 / -58% | high |
| Liquid emotions (Diluted and low tiers) | **crash** (-54 to -88%) | down | -96 to -99% by d14 | floor | Delirium category -27 / -98 / -95% | high |
| Simulacrum | flat or down | down | RoA -50%, FR +45% | FR up late (4.7 at d56) | mixed | low |
| Common and Greater essences | down (-42 to -47%) | down | down | flat | category +38 / -90 / -89% | high |
| Essence of Delirium, Perfect Essence of the Infinite | flat | up | up | **up** | Delirium 12x / 8x / 24x | high |
| Runes (category) | down (-25 to -35%) | down | down (FotV and RoA) | partial rebound (+50 to +220%) | **-53% in all three** | high |
| Lineage gems, chase/meta | up | up | **up** | up or plateau | Uhtred's Exodus 1.1 → 59 / 7 → 335 / 14 → 280 Div (FR 457 at d77) | high |
| Lineage gems, non-meta | down (-30 to -41%) | down | down | floor | e.g. -95 to -100% | high |
| Uncut Spirit gems, level 7+ | up | up | up | up | Level 20: 110x / 5.4x / 5.7x (d1 start) | high |
| Uncut Skill Gem (Level 20) | up | **peak d6-14** (3-7x) | flat or down | FotV -77%, FR +67% | | medium |
| Low-level Uncut Support/Skill gems | down | down | -74 to -82% by d14 | floor | Skill (Level 18): -96 / -99 / -95% | high |
| Trialmaster Fates (Ultimatum pinnacle) | up | up | up | **up** | Victorious Fate 42x / 29x / 53x | high |
| Refined Breach catalysts | up | up | up | up | Sibilant: RoA 44x, FR 42x (d1 start) | high |
| Breachstone and splinters | flat | flat | up in FR | FR Breachstone 4.5 Div by d70; RoA -36% | splinter FR 10x, RoA flat | low |
| Abyss: Preserved Cranium | up | up | up | up (FR peak 33 Div at d56) | 19x / 71x / 88x | high |
| Abyss: Preserved Rib and Gnawed bones | down | **down** (-48 to -63%) | down | floor | Rib -94 / -100 / -98% | high |
| Abyss: Ancient bones | up | up | up, **unless a patch adds a source** | up | Collarbone 52x / +124% (after an 88% crash on d14-21) / 6.7x | medium |
| Verisium (RoA mechanic) | down | mixed | RoA -61%, FR +2% | | -63% (RoA) / -56% (FR) | low |

**Notes on the table:**
- **The playbook's "hold" list needs a timing caveat.** It flags Soul Core of Tacati (+752% by day 7) and Uncut Skill Gem (Level 20) as holds. Both peak around days 6-14 and then fall hard, so they are **"hold to about day 10, then sell"**, not long holds. (Data)
- **RoA bone crash.** Ancient Collarbone went 13.0 Div (d14) → 1.6 Div (d21), -88%. Patch 0.5.3 (Jun 18, RoA day 20) added: "Conquering the Vessel of Kulemak now has a chance to drop Ancient Jawbones, Ancient Ribs and Ancient Collarbones" **[S4]**. (Data + Web)
- **Why FotV's week 4+ numbers are so big.**
  - FotV's Div:Ex fell from its d14 peak, and 0.4 temples produced huge Divine income.
  - Every scarce item there rose much more in Divines (e.g. omens 10-50x) than in the 0.5 leagues.
  - **Inference:** strong Divine-producing farms devalue the Divine against scarce items. Watch for the same thing if 1.0 has a Divine-rich farm.

### Chase uniques (no measured curve)

The exchange has no uniques, and the app's poe.ninja snapshots are current-only, so there's no day 1 → week 6 unique curve. Here's what the web has:
- **0.4 temple boom:** one player's weapons went from 70-90 Div to about 200 Div in a single day after the temple videos **[S5]**.
- **0.4 gear prices:** players quoted 200/400/800 Div for non-best-in-slot gear in late December 2025 **[S7]**.
- **0.5 Mageblood:** about 500 Div two weeks in, and about 379 Div later in 0.5.4 (both [seller], low confidence).
- **General advice:** unique prices are "most irrational in the first 72 hours", so wait until day 4-5 to buy **[S8, low]**.
- **Inference:** the exchange pattern above probably carries over. Scarce, build-defining chase items climb in Divines through week 4-6. Common uniques act like common currency and fall.

**To build real unique curves, Exile Oracle should start storing its poe.ninja unique snapshots daily from 1.0 day 0.**

---

## 4. Patterns that repeated, and what PoE 1 adds

**What repeated across PoE 2 leagues (3/3 in our data unless noted):**
- **Ex deflation against Div.** The web shows the same in 0.1 and 0.3 **[S19, S24]**.
- **Div:Ex peak, then a late slide.** The peak comes in weeks 2-6, followed by a slide of 25-34%.
- **Scarcity sinks rise steadily for 6-8 weeks.** These are Mirror, Hinekora's Lock, corruption currencies, top omens and pinnacle fragments.
- **Common drops halve within about 3 days and floor within about 2 weeks.**
- **Week-1 spikes reverse by week 3.** These are common soul cores and some uncut gems.
- **Liquidity has a hump.** It peaks in weeks 1-4 and collapses after week 6.
- **Buff, exploit and nerf cycles.** A strong loop appears, a streamer shows it, GGG patches it within about 1-2 weeks, and there is no rollback unless it was an outright exploit:
  - 0.2: the Breach nerf at launch **[S22]** and the Ritual tablet exploit (0.2.0d) **[S23]**;
  - 0.4: temples, Dec 2025 to Jan 3 2026 **[S5, S6, S16]**;
  - 0.5: the early-June temple fix **[S12, seller iGGM]**.

**PoE 1 (weak evidence, mostly inference):**
- A seller-site study of RMT prices across PoE 1 leagues 3.23-3.29 found:
  - the Divine's real-money price drops about 97% over four weeks;
  - day-3 price is a median 28% of launch price;
  - about 50% of all orders happen in the first 2 weeks, and 77% in the first 4.
- Source: **[S20 seller, search snippet only]**.
- That matches PoE 2's early crash of common goods and its liquidity hump. **Inference: the timing rules transfer.** The specific currencies don't, because PoE 2's Ex/Div/Chaos roles differ from PoE 1's Chaos/Div.

---

## 5. League-start money strategy (days 0-3)

1. **Convert spare Ex into Divines (and Chaos, if 1.0 follows 0.5) as you get them.** Keep only the Ex you will spend this week. Ex loses half its Divine value by day 6 in every launch. (Data, high)
2. **Sell the crash group on the day you loot it.** The playbook's `sell_day1` list covers it, and section 3 above extends it to week 6. Each day you wait on these costs roughly 20-40% of their value in the first 72 hours. (Data, high)
3. **Don't dump the riser group for pocket change.** That's top omens, Hinekora's Lock, Architect's Orb, Crystallised Corruption, Preserved Cranium, Trialmaster Fates, Refined catalysts, Uncut Spirit gems level 7+ and chase lineage gems. They went up 5-90x by day 42.
   - **Exception:** if selling one lets you finish your atlas or buy your build's key piece sooner, sell it. Early farming speed compounds. (Inference, medium)
4. **Spend early currency only on farming speed:** your league-start build, atlas, tablets and waystones. Don't buy luxury gear in the first 48-72 hours.
   - Fubgun's approach: rush the campaign and atlas, sell tradeables at once, and pick a build that clears pinnacles for 10 Div or less **[S14, S15]**. (Web, medium)
5. **If you buy Divines with Ex, do it on day 0-2.** Div:Ex was 41-67 on day 0 and 87-262 by day 6. (Data, high)

## 6. Mid-league (weeks 1-3) and late-league (week 4+) strategy

**Week 1 (days 3-6)**
- **Sell the week-1 spikes into demand, around days 5-14:** common soul cores (peak about d10), Uncut Skill Gem (Level 20) (peak d6-14), Omen of Chaotic Quantity (peak d6-21), Orb of Chance (peak d2-4). (Data, high)
- **Buy the expensive inputs you will need later now, while they're cheap in Divines:** pinnacle fragments for bossing, Hinekora's Lock, top omens for planned crafts. (Data + inference)

**Weeks 2-3**
- **This is the liquidity peak.** Sell bulk stacks and big-ticket items, and buy your main upgrades. (Data, medium)
- **Sell Orb of Annulment** during its d10-21 peak. (Data)
- **Read every patch for "now also drops from" lines,** and sell that item before or right after the patch goes live (the 0.5.3 bone crash). (Data + [S4], high)
- **Be early to new or broken-but-legal farms.** They get nerfed within about 1-2 weeks with no rollback, so the money goes to the first farmers **[S5, S6, S16]**. (Web, medium)

**Week 4+**
- **Sell held risers between about day 35 and day 60.** Many plateau or dip after that. For example, FotV Omen of Light went 34.5 → 18.7 Div from d56 to d70. Volume is also falling by then. (Data, medium)
- **Div:Ex slides 25-34% late.** Keep some Ex for crafting and don't turn everything into Divines after about week 6. (Data, medium)
- **Spend or convert everything before the league ends.**
  - 1.0 is reported for **Dec 11 2026**, not Dec 4 **[S17]**. Check the official announcement.
  - Forbidden Rites was still trading heavily on day 77, so it is not a short one-month event, whatever some guides say.

## 7. Currency Exchange flipping and its real limits

- **How it works:**
  - You post a ratio and pay a gold fee.
  - Orders fill against counter-orders, partially over time.
  - The market ratio is global for the league.
  - Hold Alt to see competing orders and their stock **[S18]**. (Web, high)
- **Measured margins (0.2, Maxroll [S18]):**
  - A single-pair catalyst flip made about 1 Ex per 6 Ex of volume.
  - Tightening the ratios raised profit 60%.
  - A three-currency loop (Ex → catalyst → Div) roughly doubled the per-trade profit.
  - Divine-tier markets are thin.
- **What our data can and can't show:**
  - GGG's hourly digests give each market's highest and lowest traded ratio per hour, but no order book.
  - On liquid pairs the gap between those two is about 10% (Chaos/Div 11%, Omen of Light/Div 10%, Fracturing/Chaos 10%). Divine/Ex shows 43%, which must include junk trades.
  - **So the real executable spread can't be measured from public data.** Treat any "flip X for Y% profit" claim as unverified. (Data, medium)
- **Real limits:**
  - **Fills take time.** Your capital is tied up while the trend moves underneath you. In week 1, Ex loses about 10-20% a day against Div.
  - **Gold fees:** older wiki figures are 50 gold per Transmutation, 120 per Exalted and 800 per Divine, but the current values couldn't be verified.
  - **Thin markets** for expensive items.
  - **Competition from bots** (forum complaints only).
- **The best "flip" is the time trend, not the spread.**
  - Ex → Div in week 1 was worth 2-5x.
  - Holding risers from week 1 to weeks 5-8 was worth 5-50x.
  - Spread-flipping gives about 10-20% per cycle on liquid pairs.
  - (Data + [S18], inference)

## 8. What top players do differently

**From the web:**
- **They rush.** Campaign, atlas and the first profitable farm come first; tradeables are sold at once; they start on a cheap league-starter build and play expensive builds only as a second character **[S14, S15]**.
- **They move first on new farms.** Fubgun's 0.4 temple-snaking videos started the boom, and early farmers made hundreds of Div per run before the nerf **[S5, S6]**.
- **They farm for value, not clear speed,** in juiced Expedition, Ritual and Abyss **[S15]**.

**From the data (inference):**
- **They respect the clock.** Dump decaying drops immediately, sell week-1 spikes around day 10, hold scarce sinks to weeks 5-8, and finish big trades before liquidity dries up after week 6.
- **They price everything in Divines** and never save in Exalted.
- **They watch patch notes for supply changes** (the 0.5.3 bones).

**Not found:** specific economy advice from Mathil, ZiggyD, Ghazzy, Palsteron, Imexile, Ventrua or Mr.Doggy, and any top-1% versus average comparison.

## 9. Risks

**Nerfs and hotfixes**
- Strong loops are nerfed within about 1-2 weeks: Breach at the 0.2 launch, the 0.2.0d Ritual tablet, the 0.4 temples (Jan 3 2026, runs went from "hundreds of Div" to about 20), and the 0.5 temple fix.
- Exploit abusers were banned and had items removed in 0.2.0d **[S23]**. Legal farming was never rolled back.
- Sources: **[S5, S6, S16, S22, S23]**.

**New drop sources and mechanic changes**
- The 0.5.3 Kulemak bones crashed one item 88% in a week **[S4]**.
- The 0.5.0 changes rewired whole markets **[S4]**:
  - The Recombinator was removed and its omen deleted.
  - The Chaotic omens were inverted.
  - Catalysts became Genesis Tree only.
  - Fracturing and Exceptional items now need atlas specialisation.
  - Ritual endgame rewards became uniques or omens only.

**Loot-table changes**
- **0.2.0g:** +20-30% high-value currency from high-rarity monsters; Breach splinters +50% **[S21]**.
- **0.5.0:** "Divine Orbs are now more common", with no number given, and Perfect and Greater orbs became rarer **[S12]**. Our data shows no clear slowdown of the week-1 Div:Ex rise afterwards (RoA 2.1x, FR 4.8x, against FotV 2.2x).

**Specific to 1.0 (inference)**
- New mechanics and possibly a much bigger player base, so early ratios will differ.
- Treat the first 24-48 hours of 1.0 data as a check on which of these patterns still hold, especially Chaos's role.

## 10. What this could not verify

- Chase unique price curves (no exchange data; only seller-site snapshots).
- Real exchange spreads, order-book depth, and the current gold-fee formula.
- Any 0.1-0.3 data from GGG's exchange history; we only pulled 0.4 onward.
- Whether the Chaos premium of 0.5 (8-11 Chaos per Div) will carry into 1.0.
- What the digest's volume numbers mean in absolute units (used as a relative index only).
- Advice from named top streamers, beyond Fubgun summaries.
