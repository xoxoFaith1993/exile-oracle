# What to farm, and when: farming returns by league phase (researched 2026-11-21)

This is research for the Oracle's "what should I farm now?" answer. The structured version is `farming-returns.json`: 22
strategies, each with its outputs, investment, requirements, Divines per hour by phase, meta history, nerfs and
confidence. `scripts/` rebuilds it, so it can be re-run on 1.0 prices from day 1. Other research in the repo covers
nearby ground, and this file doesn't repeat it:
- per-item drop rates: `research/drop-rates.md`;
- price phase patterns: `research/market/market-trends.md`;
- days 1-7 per mechanic: `datapack/playbook.json`;
- the first 72 hours: `research/league-start/`.

**How the numbers are built**

| Ingredient | What it is | Label |
|---|---|---|
| Outputs | Drop counts from one recorded creator session (mostly via farmofexile.com, which turns videos into item counts) or a community boss drop table | community claim |
| Prices | The median Divine price of each item in each league phase, from GGG's public Currency Exchange history for Fate of the Vaal (0.4), Runes of Aldur (0.5) and Forbidden Rites (0.5.5). Days 0-6 and FR days 63-77 come from the app DB; 54 hourly digests were fetched for days 10-70. | data-backed |
| Pace | A normal player gets 0.45x (low), 0.70x (mid) or 1.0x (high) of the creator's items per hour | estimate |
| Not on the exchange | Tablets, sagas, waystones and uniques are valued at a fixed range: the price when the source recorded it, and the late-Forbidden-Rites price | community claim |

- **Low** = the worst of the three leagues, at low pace and high costs.
- **Mid** = the median league, at mid pace.
- **High** = the best league, at full pace, with lucky drops included.
- A dash means you can't realistically run the strategy yet in that phase.

Phases: **d0-2** = days 0-2, **wk1** = days 3-9, **wk2-3** = days 10-24, **wk4-8** = days 25-59, **late** = day 60+.

---

## 1. The answer: best strategy per phase (Divines per hour, low / mid / high)

| Phase | Best (mid) | Runner-up | Also good | Why |
|---|---|---|---|---|
| **Day 0-2** | Alch-and-go maps, **2 / 4 / 7** | Sekhemas, 1 / 4 / 8 (claim) | Essences 1 / 3 / 5; flipping 0 / 2 / 4 | No atlas yet. Raw currency is worth the most in Divines on these days. The league-start research covers this phase in detail. |
| **Week 1** | Grand Expedition remnant rush, **20 / 40 / 83** | Sacred Bloom Fracturing farm, 11 / 40 / 89 (0.5.5 event only) | Kulemak 2 / 26 / 70; Delirium boss rush 11 / 20 / 55; budget Delirium 9 / 20 / 37 | Strategies that drop raw Divines and liquid currency win while scarce items are still cheap. |
| **Weeks 2-3** | Vessel of Kulemak, **7 / 43 / 109** (0.5.3+ bones) | 200% Delirium, 19 / 42 / 79 | Grand Expedition 21 / 39 / 79; Arbiter 16 / 58 / 131 (low confidence) | Bones and Simulacrums sell well and fragments are still cheap. This is also the exchange's liquidity peak. |
| **Weeks 4-8** | **Ritual city chains, 23 / 63 / 221** | Rite of the Nameless T16, 15 / 51 / 208 | Abyss trove 12 / 37 / 171; Sacred Bloom 35 / 63 / 102; Grand Expedition 18 / 32 / 64 | The top omens (Whittling, Annulment, Erasure) and Preserved Cranium rise 5-50x in Divines by week 6, so the omen farms pull ahead. |
| **Late (60+)** | **Ritual city chains, 20 / 77 / 374** | Rite T16, 10 / 65 / 359; Abyss trove 15 / 64 / 188 | Trial of Chaos 10 / 30 / 113 (claim); 200% Delirium 21 / 38 / 62 | The scarce-item farms keep climbing. Liquidity is down 65-98%, so selling takes longer. |

**What the Oracle should take from this:**
1. **The best farm changes during the league.**
   - In weeks 1-3, farm what drops Divines or widely traded mid-value items: Expedition currency chests, Simulacrums, Kulemak bones, catalysts.
   - From week 4, farm the scarce sink items: the top omens, Preserved Cranium, Trialmaster Fates. Their Divine prices rise while common loot falls.
   - Example: one hour of the T16 Rite of the Nameless farm is worth about 22 div of omens on FR prices in week 1, 44 in weeks 2-3 and 105 late (at the source's pace, before costs).
2. **Grand Expedition is the most stable.** It sits at 32-40 div/h (mid) from week 1 to late, because about half its value is raw Divines. Use it as the default recommendation when the character is fast.
3. **Juiced maps without a league mechanic earn little.** The base currency alone is 2-4 div/h; the money comes from the mechanic stacked on top. Plain Exalted-heavy loot loses value every week (Ex fell 83-92% against Div by day 28).
4. **A highly ranked boss farm is a warning.** Arbiter of Ash shows the problem:
   - farmofexile prices it at 122 div/h;
   - it goes negative on Forbidden Rites days 42-70 prices, because its inputs (60 Crisis Fragments an hour) cost more than its outputs;
   - the Faded Crisis Fragment fell from 11.5 to 5.8 div between days 63 and 77 alone.
   
   Boss rushes depend on the spread between key price and loot price, so the Oracle must re-price them live.

---

## 2. Every strategy: outputs and value

Per-hour outputs are at the source's pace, with the sample size given. Divines per hour are low / mid / high for
d0-2 | wk1 | wk2-3 | wk4-8 | late.

| Strategy | Key outputs per hour (source pace) | Source / sample | Div/h by phase | Conf. |
|---|---|---|---|---|
| Ritual: Rite of the Nameless T16 | Whittling 3.7, Sinistral Annulment 1.15, Dextral Annulment 0.86, Sinistral and Dextral Erasure 0.29 each. In: 2 Head of the King, ~2.4 tablets. | MisoxShiru, 42 maps, ~3.5 h, 0.5.5 | – \| 2/5/17 \| 5/10/39 \| 15/51/208 \| 10/65/359 | medium |
| Ritual: city chains | Chaotic Rarity/Effectiveness/Quantity/Monsters 13-16 each, Whittling 3.5, Annulments 1.6, Erasures 1.1, Crystallisation 4.2, Bartering 35, Call of the Shadows 9.5. In: ~21 Chaotic Rarity + 21 Chaotic Effectiveness, 2 Head of the King. | XTheFarmerX, ~5.5 h, 0.5.5 | – \| 6/13/30 \| 8/17/52 \| 23/63/221 \| 20/77/374 | medium |
| Grand Expedition remnant rush | Divine 16, Chaos 23, Greater Chaos 12, Shattered Triskelion 8, Astrid's Creativity 2, Uhtred's Saga 2, Perfect Chaos 1, Olroth's Resolve 1 | KingPinUwU, 1 h, 0.5.5 | – \| 20/40/83 \| 21/39/79 \| 18/32/64 \| 17/34/74 | medium |
| Sacred Bloom Fracturing farm | Fracturing Orb 10.5, Divine 20, Annulment 3.8, Omen of the Hunt 2.9 | KingPinUwU, ~14 maps / 1 h, 0.5.5 | – \| 11/40/89 \| 20/48/94 \| 35/63/102 \| 36/67/111 | low (event-only) |
| Delirium boss rush | Simulacrum 2.7, Divine 5.4, Crisis Fragments 3.6, Origin Spark/Cradle 1.2, Breachlord Sac 0.8 (+ one Rakiata's Flow, high only) | XTheFarmerX, 5 h, 0.5.5 | – \| 11/20/55 \| 12/23/62 \| 13/27/70 \| 14/30/78 | medium |
| 200% Delirium city juicing | Simulacrum 19.3 (~580 splinters per map) | DEADRABB1T, 15 maps, 0.5.5 | – \| – \| 19/42/79 \| 19/34/54 \| 21/38/62 | medium |
| Budget Delirium (1 tablet) | Simulacrum 5.8, Divine 6.9, Annulment 1.8 | DeadRabb1t, 50 maps / 4.5 h, 0.5.5 | – \| 9/20/37 \| 10/20/33 \| 10/17/26 \| 10/18/28 | medium |
| Breach Hiveblood → catalysts | 617 catalysts, 91 of them Refined (Refined Reaver 9, Refined Esh 17); ~150k Hiveblood. In: 6 Breach tablets (3.9 div, later ~11). | Masterer Mitch, 1 h, 0.5.5 | – \| 2/9/20 \| 4/23/56 \| −2/14/45 \| −11/20/82 | medium |
| Abyss trove / Omen of Light + Cranium | Omen of Light 2.9, Preserved Cranium 1.7, Jawbone 1.1, Rib 1.1, Kulemak's Invitation 1.4, Abyssal Echoes 6 | MisoxShiru, 35 maps, 0.5.5 | – \| 1/12/19 \| 4/15/39 \| 12/37/171 \| 15/64/188 | medium |
| Vessel of Kulemak rush | Per run: Jawbone 0.36, Rib 0.35, Collarbone 0.29, Divine 0.16. 16.6 runs/h, one Invitation per run. | wiki n=100-200 table (0.5.4) via farmofexile | – \| 2/26/70 \| 7/43/109 \| 9/15/23 \| 7/22/46 | medium |
| Arbiter of Ash rush | Per run: Morior Invictus 0.48, Prism of Belief 0.23, Reliquary Key 0.005. 20 runs/h, 3 Crisis Fragments per run. | wiki 235 kills | – \| – \| 16/58/131 \| −25/−6/40 \| −52/−48/−21 | low |
| Aberration rush | Per run: Starlit Ores ~0.97, Olroth's Conviction/Hubris 0.05 each. One Triskelion Reforged per run. | wiki 562 kills | – \| – \| 3/13/30 \| 6/11/19 \| 2/8/16 | low |
| Alch-and-go mapping | Per map: Ex 7.6, Divine 0.15, Chaos 0.8, Vaal 2.3, Alch 2.1. 18 maps/h. | drop-rates.json (Ronarray 0.2, 30 maps) | 2/4/7 \| 2/4/6 \| 2/4/6 \| 2/4/6 \| 2/4/6 | medium |
| Juiced T15-16, base currency only | Per map: Ex 11, Divine 0.45, Chaos 2.2, Greater Ex 0.35, Perfect Ex 0.05. 10 maps/h. | drop-rates.json | – \| 2/4/8 \| 2/3/8 \| 0/2/6 \| 1/3/6 | low |
| Essences | ~3 essences per map (estimated mix: Greater, some Perfect, rare corrupted) plus base currency | 0.2 rates (0.96-1.2/map) + 0.5 setup [seller] | 1/3/5 \| 1/3/4 \| 1/2/4 \| 0/2/10 \| 0/2/18 | low |
| Trial of Chaos (0.5.5, 30 rooms) | 2 runs/h. Currency "5-20 div per run" [seller], about 2 Fates/h, Soul Cores. The Adorned is about a 2% jackpot (729 div). | mmoexp 50 runs, aoeah [seller] | – \| 5/18/72 \| 5/20/73 \| 10/27/85 \| 10/30/113 | low |
| Trial of the Sekhemas | 2.6 div per run (no carries), 2 runs/h | EmpyrianGaming, 20 runs, 0.1 | 1/4/8 flat | low |
| Vaal temple / Atziri | 4-5 div per Atziri kill, a kill every second run, Orbs of Sacrifice | aoeah [seller], Maxroll, YouTube titles | – \| 2/6/15 \| 2/7/16 \| 1/7/17 \| 1/7/19 | low |
| Strongboxes (Azmeri stacking) | Before the nerf, "50+ raw div" test maps [seller]. Nerfed around Sep 20 2026. After the nerf the numbers are my guess. | mmoexp, KingPinUwU title | – \| 1/8/23 \| 1/8/23 \| −2/6/22 \| −2/6/22 | low |
| Rogue exiles | No measured source | estimate | – \| 0/3/7 \| 0/3/7 \| −1/2/7 \| −1/2/7 | low |
| Crafting for profit | Margins aren't published; only seller "100-300 div a day" claims | estimate | – \| 0/5/15 flat | low |
| Exchange / gold flipping | About 1 Ex profit per 6 Ex traded (Maxroll, 0.2). Hourly low-high spreads are ~10% on liquid pairs (our data). | Maxroll, GGG data | 0/2/4 flat | low |

**Strategies the brief asked about that have no separate row:**
- **Incursion / temple loops.** In PoE 2 this is the Vaal temple row.
- **Legion-likes.** PoE 2 has no Legion mechanic up to 0.5.5. The nearest kinds of content are Abyssal Depths/Ravines and the Viridian Wildwood (disabled in 0.5.5), and those sit under Abyss and Sacred Bloom.
- **Gold-for-exchange.** Gold is only a fee on the exchange, so this is the flipping row. Seller "gold farming 200-300 div/h" claims were ignored.

---

## 3. Checking community claims against the price data

| Claim | Who | Our number | Verdict |
|---|---|---|---|
| Rite T16 105 div/h, city chains 101 div/h | farmofexile, repriced at today's prices | 93 / 109 at source pace on FR late prices | **Agrees.** Same counts, same late prices. It is only true for a creator-speed player **late** in the league. In week 1 the same hour is worth 7 / 18. |
| Ritual 90-150 div/h | iggm [seller], YouTube titles | mid 63-77 at week 4+, 13-17 in weeks 1-3 | **2-10x inflated early**, roughly right for a top player late. |
| Grand Expedition 60-150 div/h | Fubgun, Path of Evening, LLYD titles | source pace 45-57, mid 32-40 | **About 1.5-3x inflated.** farmofexile's 46 agrees with ours. |
| Breach Hiveblood 100+ div/h | SaVeQ titles | source pace 13-33 net of tablets (35-105 gross on FR) | **3-7x inflated.** The 20-26 [seller] and 32 farmofexile figures are realistic. |
| Kulemak 55-120 div/h | MazBro, SaVeQ titles (0.5.3-0.5.4) | mid 43 in weeks 2-3, 15-22 later | **True only for about two weeks** after bones were added (the 0.5.3 Collarbone crash followed). |
| Arbiter 122 div/h | farmofexile model | 83 at mid prices in weeks 2-3, negative on day 42-70 prices | **Depends entirely on fragment prices.** Re-price live. |
| Trial of Chaos 32-48 div/h | timesaver, mmoexp [seller] | mid 18-30 | About 1.5x inflated, and it has no counted sample. |
| Temple 100-120 div/h (0.5.5) | LilBotQ, OnesInTheChat titles | mid 6-7 (no counts; claim range 3-15) | **Unverifiable.** The only priced evidence is 4-5 div per Atziri. |
| 0.4 temple, "hundreds per run" | PCGamesN, finalboss | not modelled (it existed for 3 weeks) | Real (news coverage), and ended by 0.4.0c HF13 on 2026-01-02. |

**Rule for the Oracle.** Divide YouTube-title div/hour claims by about 2-3. Then re-price the creator's item counts at
the current phase instead of trusting the headline. The headline is usually priced at the item's peak, or includes a
jackpot (the Delirium boss rush made half its profit from one Rakiata's Flow).

---

## 4. What actually happened in each launch (meta farms and nerfs)

| League | Meta money farm | How long | How it ended |
|---|---|---|---|
| 0.1 Early Access (Dec 2024) | **Breach** splinters/Breachstones; Sekhemas Desperate Alliance | Breach all league; Sekhemas exploit to 2025-01-02 | Breach density cut 0.1.0e (2024-12-17) and -15% in 0.1.1 (2025-01-16). Sekhemas instance exploit closed 0.1.0e HF5. |
| 0.2 Dawn of the Hunt (Apr 2025) | **Ritual** reroll exploit, then Ritual omens, Breach and Citadels | Exploit Apr 4-7; then all league | 0.2.0d (2025-04-07) capped Freedom of Faith rerolls, with bans. 0.2.0g (≈05-01) buffed most farms (+50% Breach splinters, +80% Delirium splinters, +50% Audience). |
| 0.3 Third Edict (Aug 2025) | **Abyss** juicing (often with Breach or Delirium), then map crafting after 0.3.1 | Aug-Dec | 0.3.0 nerfed Expedition (Olroth out of logbooks) and Ritual (Audience chance). 0.3.1 (09-30) buffed juice. |
| 0.4 Fate of the Vaal (Dec 2025) | **Vaal temple**: the biggest boom so far, "hundreds" of div per run. Then the **Omen of Light** Abyss farm. | Temple 2025-12-12 to 2026-01-02; Omen of Light to 2026-02-19 | Temple diminishing returns 0.4.0c HF13 (01-02). Amanamu's Void multi-omen fix 0.4.0e HF2 (02-19). No rollback. |
| 0.5 Runes of Aldur (May 2026) | Temple room stacking (4 days), then Abyss / Omen of Light, Breach Hiveblood, **Grand Expedition** (from 0.5.3) and **Kulemak bones** (from 0.5.3) | Temple May 29-Jun 2; Expedition Jun 18-Jul 2 at its peak | 0.5.0b HF13 (06-02) temple; 0.5.1 (06-04) Elite Abyss loot; 0.5.3 (06-18) Delirium fog halved; 0.5.4 HF3 and 0.5.4b (06-25, 07-02) Grand Expedition rarity and infinite-island fixes |
| 0.5.5 Forbidden Rites (Sep 2026) | **Ritual** (league mechanic, city chains ~100 div/h), Breach Hiveblood, Grand Expedition, Sacred Bloom Fracturing, Trial of Chaos | Sep-Nov | Azmeri strongbox stacking reported nerfed around 09-20. 0.5.5c/d fixed Ritual deferral costs. No nerf found to Sacred Bloom, Genesis Tree or Omen of Light. |

**Pattern (same as market research):**
- A broken loop appears and a streamer shows it.
- GGG hotfixes it within about 4 days to 3 weeks (temple: 21 days in 0.4, 4 days in 0.5; Ritual exploit 3 days; Expedition islands 14 days).
- There is no rollback unless it was a clear exploit (0.2 Ritual bans).

**For the Oracle:** a new "too good" farm in 1.0 is worth doing immediately, and it is safest to assume it lasts
under 2 weeks. Each strategy's dated nerf list is in the JSON (`nerfs`, `meta_history`).

---

## 5. Requirements, to match a strategy to the character

These are estimates from guide rules of thumb and creator Path of Building snapshots. They are **not measured**
thresholds. EHP means PoB "Total EHP".

| Tier | DPS (PoB combined) | EHP | Strategies |
|---|---|---|---|
| Starter | 100k+ | 8k+ | Alch-and-go, low Sekhemas floors, essences |
| Mid | 300-600k | 15-25k | Budget Delirium, Delirium boss rush, Breach Hiveblood, Abyss trove, temple |
| Strong | ~1M | 25-30k | Grand Expedition (also needs speed), Rite of the Nameless, Kulemak / Arbiter / Aberration, Trial of Chaos 30 rooms |
| Juiced | 1.5M+ | 40k+ | 200% Delirium cities, strongbox stacking |

**Sources:**
- timesaver [seller]: ~100k DPS "barely clears" T15; 200-500k is comfortable; 1M+ for juiced maps and pinnacles.
- aoeah [seller]: Trial of Chaos 30 rooms needs 30k+ EHP, capped resistances and level 90.
- Creator snapshots (poebuilds.cc): KingPinUwU strongbox build at 1.5M DPS / 45k EHP; AlanStriker at 3M / 65k; a juiced Expedition build at 3M / 189k.

**Resistance and special checks:**
- All strategies: capped elemental resistances (75%).
- Arbiter of Ash: fire (fire-resistant only since 0.5.5).
- Kulemak: balanced cold, lightning, fire and physical.
- Trial of Chaos: avoid "Reduced Recovery" with flask or regen builds.
- Sekhemas: 75% honour resistance from relics.

**Speed counts as much as DPS.** Grand Expedition and Ritual city chains assume about 3-6 minutes per map. A slow
character gets roughly the "low" column.

**Investment summary:**
- **Cheap:** under 5 div/h of inputs. Alch-and-go, essences, budget Delirium, Delirium boss rush, Grand Expedition (sagas ~2-4 div/h), Trial of Chaos, Sekhemas.
- **Medium:** 5-20 div/h. Rite T16 (tablets + Head of the King), Abyss trove (tablets + Cryptic Keys), 200% Delirium.
- **Capital:** inputs bought every run. Breach (6 tablets/h: ~23 div/h at the recorded price, up to ~66 late), Kulemak (~17 Invitations/h: 1.5 div/h on RoA week 1 prices, ~80 on FR late prices), Arbiter (60 fragments/h), Aberration (24 Triskelions/h), city-chain Chaotic omens (~21 of each per hour, mostly re-supplied by the farm).

---

## 6. Caveats

1. **Drop counts are one session each**, from fast, lucky creators who publish their best runs. The 0.45 / 0.70 pace factors are my estimate.
2. **The prices are real, but they belong to past leagues.**
   - 1.0 will have its own drop changes, and Ritual and Sacred Bloom may not exist in the same form.
   - To use 1.0 prices, re-run `prices.py` and then `build.py`. The app already syncs the same GGG endpoint.
3. **Some values aren't on the exchange:**
   - uniques (Prism of Belief, Morior Invictus, Rakiata's Flow, The Adorned, Ritual chase uniques);
   - tablets, sagas and waystones.
   
   Both kinds use two farmofexile price points, which are late-Forbidden-Rites values. Arbiter is priced on FR only for this reason.
4. **Leagues are skipped where their price says nothing about the farm:**
   - Kulemak and Sacred Bloom skip Fate of the Vaal: no Kulemak bone drops in 0.4, and the bugged Fracturing supply.
   - Fate of the Vaal's week 4+ prices for omens, bones and Fates are 3-5x the other leagues', because the temple Divine flood devalued Divines. They drive most "high" values.
5. **Market impact is ignored.** Every Kulemak farmer adds ~17 bones an hour; 0.5.3 crashed Collarbone 88% in a week.
6. **Claim-only rows have no counts**, so their div/h is a discounted claim range and is flat across phases. These are Trial of Chaos, Sekhemas, temple, strongboxes, rogue exiles, crafting and flipping.
7. **Day 0-2 Divine values look high** because Divines are cheap then. Most strategies are null there on purpose, because the atlas isn't unlocked yet.
8. **Data sampling:**
   - Days 10-70 are two sampled hours per day, so ±20% noise on thin items.
   - FR "late" covers days 63-77. FotV and RoA "late" is day 70 only.
9. **Access limits:**
   - Reddit wasn't opened.
   - Mobalytics (403) and poe2wiki (bot wall) were reached only through search snippets.
   - YouTube gave titles only (no descriptions or transcripts), so title numbers are labelled creator claims.

## Sources

**Data**
- GGG Currency Exchange history: `https://web.poecdn.com/api/currency-exchange/poe2/<hour>`. 54 hours were fetched at 2.5 s spacing and cached in `scripts/cache/`.
- App DB, read-only: `<data folder>/data/poe2kit.db` (`ls_price`, `ex_price`, `patch_notes` 0.5.0-0.5.4b).

**Counts**
- farmofexile.com/poe2 strategy pages and their methodology (Rite T16, city chains, Grand Expedition, Sacred Bloom, three Delirium farms, Breach catalysts, Abyss trove, Kulemak, Arbiter, Aberration).
- `research/drop-rates.json`.

**History**
- Official patch notes on pathofexile.com, 0.1.0 to 0.5.5h (thread IDs are in the JSON).
- News: PCGamesN, finalboss.io, Gamepressure, Mein-MMO.
- Creator claims: the poebuilds.cc farming index of YouTube titles.

**Requirements and claims**
- Guides: Maxroll (temple, Sekhemas, flipping).
- Seller sites (low trust, marked [seller]): timesaver, aoeah, mmoexp, mtmmo, iggm.

The full list is in `farming-returns.json` → `sources`.

**Scripts** (`scripts/`):
- `fetch_samples.py`: the polite GGG fetch, cached.
- `prices.py`: per-phase price table → `prices_by_phase.json`.
- `strategies.py`: all strategy data, meta history and nerfs.
- `build.py`: valuation → `farming-returns.json`.
