# PoE 2 patch notes → price impact (researched 2026-11-21)

Research for Exile Oracle: when GGG posts patch notes (the 1.0 notes before the 2026-12-11 launch, and every
hotfix after it), predict which exchange prices move, which way, how far and how fast.

**Files in this folder:**
- `patch-impact.json`: all 276 posts, the classified lines and what was measured for each, plus the rules and the checklist.
- `rules.py`: `classify(line)` for the app. Standard library only.
- `scripts/`: the scripts and the cache that rebuild everything (the order is at the end of this report).

Market phase patterns (how prices drift over a league with no patch) are in `research/market/` and are not repeated
here. This report is about the patch itself.

**Labels used below:**
- **Data:** measured from GGG's exchange history.
- **Notes:** quoted from GGG's patch notes.
- **Inference:** my reading of the data.
- **Estimated:** a hand-set number in `rules.py` that has not been measured.

---

## 1. The short version

1. **Most patch lines don't move prices beyond normal noise.** Over the same hours, a random single exchange item
   moves a median of **24% in 24 h, 38% in 72 h and 49% in 7 days** against its league's drift. Only 7-25% of the
   cases I measured moved more than that (Data).
2. **The few lines that do move prices are supply shocks to one specific item.** The clearest case:
   - 0.5.3 (2026-06-18, league day 20) added the Vessel of Kulemak as a new source of Ancient bones (Notes).
   - Ancient Jawbone, Rib and Collarbone fell **79% in 24 h** and **72% in 72 h** against other Abyss items (Data).
   - Measured against the same bones on the same league day in two other leagues, they fell **77%** (72 h) (Data).
3. **Named supply increases, 18 hand-reviewed cases:**
   - The item fell in **61%** of cases. The median drop was **17%** over 72 h against its group, or **10%** after the
     cross-league check.
   - **The effect peaks at 24-72 h, then partly reverses by day 7.**
   - Confidence is medium. Sell within the first day; don't wait for the floor.
4. **Farm nerfs and exploit fixes raise the farm's outputs, but with a lag** (8 cases).
   - The 72-hour reading is flat (+0%).
   - By day 7 the median is **+42%**: 75% of cases rose, and 71% still rose after the cross-league check.
   - Biggest case: the 0.4.0c Hotfix 13 temple diminishing-returns nerf (2026-01-03).
     - Vaal currency and soul cores were **-32% at 72 h**, then **+136% at day 7** against their group, or **+176%**
       after the cross-league check (Data).
5. **Farm buffs lower the farm's outputs.** 3 of 3 cases fell, by a median of **-12% at 72 h** and **-39% at day 7**.
   - Example: 0.4.0c Hotfix 12 (2025-12-30) doubled temple runs.
   - Temple outputs were -30% at 72 h and **-60% at day 7** against their group (-59% after the cross-league check)
     (Data).
6. **Stat changes to soul cores and runes ("socketables") are a coin flip with big swings.**
   - Buffs and limit changes went the expected way in 5 of 8 cases (median **+31%** in the expected direction, 24 h).
   - 0.5.5's buffs to the Soul Cores of Citaqualotl and Tacati: **+69% / +55%** in 24 h. Two other "buffs" fell 50-90%
     (Data, Runes of Aldur, which was a dying league by then).
7. **A change in what a crafting item can be used on causes dumping, whichever way it goes.**
   - Transcendent Alloy fell **76%** in 72 h when 0.5.2 removed its Foci/Wand use (Data).
   - It fell **75%** again when 0.5.3 restored it a week later, because the same patch doubled Remnant rewards
     (Data + Notes).
   - Treat these as volatility, not a direction.
8. **Making a mechanic more rewarding did not raise its entry item** (0 of 4 cases rose).
   - Example: 0.5.2 guaranteed a Grand Expedition per Logbook section, and Expedition Logbook went **-63%** in 72 h
     (Data).
   - Inference: the same patches added more sources of the entry item, and players sold their stock into the hype.
9. **Supply cuts ("no longer drops", "lowered the drop rate") are weak and rare** (4 cases).
   - The expected rise showed up only at day 7, in 3 of 4 cases.
   - The clearest: 0.1.0c lowered Chaos Orb drops, and Chaos was **+139%** in 72 h against other currency (Data, 0.1).
10. **The early-league trap.** Patches in league days 0-14 sit on top of a large normal drift:
    - After the 0.4.0c farm nerf on day 6, temple outputs looked **+53%** at day 7. After the cross-league check it
      was only **+14%**.
    - After 0.5.1 Hotfix 4 re-enabled a Hinekora's Lock source on day 7, Hinekora's Lock rose **236%** in 72 h, the
      opposite of the expected drop. It is the normal early-league climb (market-trends: 20-66x by day 42).
    - Use the net (`abnormal`) move, never the raw chart.
11. **The automated classifier** (all 2,499 lines it flagged, 160 measured cases) only gives base rates:
    - "now drops / can now drop" lines: median **-19%** at day 7 against their group, 82% fell (n=17).
    - Farm buffs: **-18%** (n=12).
    - The generic "league mechanic changed" bucket: **-5%** with a spread of -37% to +15%, which is noise.
    - The app should flag lines automatically, and the Oracle should judge the shock size.
12. **Unique items: nothing measurable yet.**
    - poe.ninja's history only reaches back about 120 days.
    - Only 3 small unique changes fall in that window.
    - Skill-buff → unique effects are inference only (section 5).
    - Exile Oracle should store daily unique snapshots from 1.0 day 0.

---

## 2. Data and method

**Patches (Data, official).**
- I read every first post in GGG's Early Access Patch Notes forum (forum 2212): **276 threads**, from the 0.1.0
  Hotfix on 2024-12-06 to 0.5.5h on 2026-11-17.
  - 0.1: 48 posts. 0.2: 43. 0.3: 31. 0.4: 61. 0.5: 83. Also 10 server-maintenance posts.
- **Timestamps:**
  - Forum times are US Pacific for logged-out readers. I converted them to UTC with US daylight-saving rules.
  - Check: 0.1.0d at 18:47 PST matches Steam's 02:47 UTC exactly.
- **Cross-checks:**
  - The wiki's Version history (Cargo `versions` table) gives a date for 265 posts.
  - The Steam announcements API matched 19 posts.
  - The app's own `patch_notes` table only holds 0.5.0-0.5.4b, all from Steam.

**Prices (Data).**
- **Source:** GGG's public Currency Exchange hourly digests, the same endpoint and volume-weighted pricing as
  `poe2kit/leaguestart.py`. Fetched 2.5 s apart, 496 hourly pages (547 league-hour price tables), cached gzipped. Hours the app DB already holds
  (`ex_price`, Nov 6-21 2026) were read from the DB.
- **Unit:** everything is in Divine Orbs. Divine itself is priced in Exalted.
- **League:** the main softcore league for that hour. In 0.1 that is Standard.

**Measurement windows.**
- **Base:** the two full hours before the post.
- **After:** +24 h, +72 h and +7 days.
- **Before (pre7):** the 7 days before the post, so you can see whether the item was already moving.

**Removing the drift.** Patches land on league days that have their own drift, so I report three numbers:
1. **Group-adjusted:** the item against the median of the other items in its exchange group over the same hours.
2. **Cross-league (difference in differences):** the item against the same item over the same league-day window in
   two other leagues. Each league's whole-market move over those hours is netted out first. This removes the normal
   league-life curve, which matters most when a patch hits a whole group at once.
3. **Placebo:** for each case, I drew 200-300 random sets of unaffected items of the same size over the same hours.
   A case is "beyond noise" only if its move is bigger than the placebo's 90th percentile.

**Cases.**
- **Hand-reviewed:** 52 lines I read and judged as clear supply or demand changes. For each, the exchange items and
  the expected direction were written down first (`scripts/cache/curated.json`). These give the main rules.
- **Automated:** every line `rules.py` flags, measured the same way. These give base rates.

---

## 3. The rulebook (hand-reviewed cases)

How to read the table:
- **Move** is the signed price change: negative means the price fell. For the bottom rows it is measured in the
  direction each case expected.
- **Hit** is how often the price moved the expected way.
- **Phase-hit** is the same after the cross-league check.
- **Beyond noise** is the share of cases that moved more than the placebo band.
- `rules.py` uses these numbers.

| When the notes say… | Affected group | Typical move (window) | n | Spread (p25-p75) | Hit / phase-hit / beyond noise | Confidence |
|---|---|---|---|---|---|---|
| A named item gets a new or bigger source ("now has a chance to drop", "always drops", "increased the drop rate", "+50%") | that item | **-10% at 72 h** (group-adjusted -17%); peak at 24-72 h, partly back by day 7 | 18 | -38% to +25% | 61% / 58% / 11% | medium |
| … and the line states no size (plain "increased the drop rate", drop weight moved) | that item | **-35% at 24 h** | 4 | | 100% / - / 25% | medium (small n) |
| … and the line uses strong words ("significantly", "+50%", a new source) | that item | -5% at 72 h | 14 | | 57% / 64% / 7% | low |
| A named item gets a smaller source ("no longer drops", "lowered the drop rate") | that item | **+51% at day 7**; nothing at 24-72 h | 4 | -20% to +163% | 75% / 100% (n=1) / 50% | medium (small n) |
| A farm is nerfed or an exploit fixed (diminishing returns, caps, "infinitely", "multiple additional") | the farm's outputs | **+42% at day 7**; flat at 72 h | 8 | +5% to +99% | 75% / 71% / 75% | medium |
| … same, from league day 15 on | the farm's outputs | +125% at day 7 | 4 | +49% to +180% | 75% / 67% / 50% | medium (small n) |
| … same, in league days 0-14 | the farm's outputs | +20% at day 7, mostly normal drift | 4 | | 75% / 75% / 100% | medium (small n) |
| A farm is buffed ("greatly improved", "double the runs", more rarity per depth) | the farm's outputs | **-12% at 72 h, -39% at day 7** | 3 | -22% to -8% (72 h) | 100% / 100% / 33% | low (n=3) |
| A soul core or rune's own stats change ("now grants X (previously Y)", "Limit of 1") | that socketable | +31% in the expected direction at 24 h | 8 | -44% to +61% | 62% / - / 12% | medium |
| A crafting use is removed or restored ("can no longer / can once again be applied to") | that item | -60% to -76% in 24-72 h **both times** | 2 | | 50% | low: read as volatility |
| A mechanic gets more rewarding (check its entry item: Logbook, Simulacrum) | the entry item | **fell in 4 of 4 cases**: -25% at 24 h, -62% at 72 h | 4 | | 0-25% | low: the expected rise did not happen |

### Second-order effects (how the rules chain)
- **A new drop source crashes that item.** It also makes whatever the item gates cheaper to run.
  - Measured: Ancient bones (pinnacle drop) -72 to -79% in 24-72 h; Expedition Logbook (guaranteed boss drop) -51%
    in 72 h; Breach Splinter (+50% drops) -48% in 72 h; Lesser Jeweller's Orb (given the Artificer's drop weight)
    -73% in 72 h (Data).
  - That the gated content then gets cheaper is inference.
- **A farm nerf raises its outputs.** The rise came after a dip: the temple diminishing-returns nerf was -32% at 72 h,
  then +136% at day 7 (Data). Inference: holders panic-sell on the news, then supply dries up.
  - The farm's inputs should lose value. Temple medallions and crystals were not tradeable, so this could not be
    measured.
- **A farm buff lowers its outputs.** 3 of 3 cases fell, and the fall continued through day 7 (Data).
- **A skill or ascendancy buff should raise its key uniques, lineage supports and bases.** This could not be measured
  (no unique history before July 2026, and the builds API is off limits).
  - The market research has one web data point: during the 0.4 temple boom, weapons went from 70-90 Div to about
    200 Div in a day (market-trends S5).
  - Treat this as a rule of thumb. For each buffed skill, price-check its 2-3 key uniques and lineage gems on day 0
    and day 3.

---

## 4. Case studies

**A. 0.5.3, 2026-06-18 23:30 UTC, Runes of Aldur day 20: "Conquering the Vessel of Kulemak now has a chance to drop
Ancient Jawbones, Ancient Ribs and Ancient Collarbones."**
- Ancient Collarbone: **-88% in 24 h** against its group (-87% at 72 h).
- Cross-league check: -92% at 72 h and -91% at day 7.
- Jawbone -78% and Rib -78% in 24 h.
- No move before the post (pre7: -0%).
- This is the textbook case: a rare item gets a new source from a farmable pinnacle. Sell at once. The market
  re-priced within the first day.

**B. Same patch: "Styrn … now always drops an Expedition Logbook."**
- Expedition Logbook: -34% in 24 h and -51% in 72 h against its group.
- Cross-league check: -79% at 72 h and -70% at day 7.
- The same patch also "greatly improved" Grand Expedition chests, which should have raised Logbook demand. Supply won.

**C. 0.2.0g, 2025-05-01, Dawn of the Hunt day 26: drop-rate buffs with numbers.**
- "Breach splinter drop rates increased by +50%": Breach Splinter -48% in 72 h (cross-league -38%).
- "Delirium splinter +80%": Simulacrum Splinter flat (+4%).
- "Exotic Coinage +50%": Exotic Coinage rose (+124% in 72 h against its group, +42% cross-league).
  - Inference: the same patch fixed Expedition chest rarity, which made coinage worth more to spend.
- Lesson: **the stated percentage did not predict the move.** Read the other lines that touch the item's demand.

**D. 0.4.0c Hotfix 12 → Hotfix 13/14, Fate of the Vaal days 17-21 (the temple boom and its end).**
- Hotfix 12 (2025-12-30 09:05 UTC): "Map Areas now grant additional Energized Crystals… double the number of temple
  runs."
  - The 43 Vaal-group and soul-core items: -24% in 24 h, -30% in 72 h, -60% at day 7 (cross-league -59%).
- Hotfix 13 (2026-01-03 02:11 UTC) added diminishing returns. Hotfix 14, seven hours later, cut room destabilisation.
  - The same group: -8% in 24 h, -32% in 72 h, then **+136% at day 7** (cross-league +176%).
  - Web coverage says runs fell from "hundreds of Div" to about 20 (market-trends S6).
- Lesson: **buff = outputs fall within days; nerf = a dip, then a rise inside a week.**

**E. The early-league trap: 0.4.0c Patch Notes (FotV day 6) and 0.2.0d (Dawn of the Hunt day 3).**
- 0.4.0c halved the temple bonus/reroll medallions. Temple outputs were +35% in 72 h and +53% at day 7 against their
  group, but only +2% and +14% after the cross-league check. Soul cores peak around day 10 in every league anyway.
- 0.2.0d capped the Freedom of Faith infinite Ritual reroll. Omens were +46% in 72 h and +120% at day 7 against their
  group, and +32% / +57% after the cross-league check.
  - So the exploit fix still had an effect, but about half the raw move was ordinary week-1 omen drift.

**F. 0.1.0c, 2024-12-10, Early Access day 3: a currency rebalance.**
- "Increased the drop rate of Regal Orbs": Regal -51% in 72 h against other currency.
- "Lowered the drop rate of Chaos Orbs and distributed it amongst … Regal, Exalted": Chaos **+139%** in 72 h
  (+348% at day 7).
- Artificer's drop weight moved to Lesser Jeweller's: Lesser Jeweller's -73% in 72 h (as expected). Artificer's also
  fell (-53%), against the expectation.
- Caveat: 0.1 has no other league to check against, and its early exchange data is thin.

**G. Transcendent Alloy flip-flop: 0.5.2 (06-11) and 0.5.3 (06-18), Runes of Aldur.**
- Removed from Foci/Wands: -40% in 24 h, -76% in 72 h.
- Restored a week later: -80% in 24 h, -75% in 72 h.
- The same 0.5.3 post doubled the rewards of Runic Inscriptions, so supply rose as the use came back.
- Lesson: when a line changes an item's use and another line in the same post changes its supply, **supply decides.**

**H. Socketables: 0.5.5 notes (2026-09-02), measured on the still-live Runes of Aldur, 24 h only (Forbidden Rites
started two days later).**
- Soul Core of Citaqualotl buff: +69%. Soul Core of Tacati buff: +55%.
- Soul Core of Cholotl and Atmohua's Soul Core of Retreat "buffs": -51% and -90%.
- "Limit of 1" on Topotante: -58%.
- Lesson: buffs to socketables used in meta builds rise; reworks of niche ones get dumped.

**I. Uniques (poe.ninja history, Runes of Aldur only).**
- 0.5.5 fixed the Prism of Belief / From Nothing "snapshot" bug: From Nothing +21% at 3 days, Prism of Belief flat.
- Chernobog's Pillar legacy fix: -19% at 3 days.
- Three cases, no rule.

---

## 5. Correlation vs causation

- **Every case has a before-trend (pre7) stored.** Several targeted items were already moving. For example, Ancient
  Infuser and Architect's Orb were -45% and -43% in the week before the 0.4.0c Hotfix 12 temple buff.
- **GGG reacts to the market:**
  - Nerfs follow booms, and fixes follow visible exploits.
  - Part of a post-nerf rise is the boom's supply simply ending, not the patch itself.
  - Part of a post-buff fall is GGG buffing things that were already being abandoned.
- **Patches come in clusters.** 0.4.0c had 26 hotfixes in 24 days. A 7-day window often holds 2-5 other posts. 0.5.3
  arrived exactly 7 days after 0.5.2.
- **Content-update posts are not measured.** These are 0.2.0, 0.3.0, 0.4.0, 0.5.0 and the 1.0 notes. They come
  about a week before a new league, so the old league's price reaction says little about the new economy. Use
  `research/market` for launch-week behaviour, and this rulebook from the first hotfix on.
- The hand-reviewed list is my judgement of which lines matter, with directions fixed before measuring. Hit rates of
  55-75% on 4-18 cases are evidence, not proof.

---

## 6. Checklist for reading the 1.0 notes (and every hotfix)

1. **Search for "now drops / has a chance to drop / always drops / can now be found" next to an exchange item.**
   - This is the strongest signal.
   - Sell that item before deploy or within the first hours. The floor came in 24-72 h.
   - Don't buy the dip on day 1.
2. **"No longer drops / only drops from":** hold. Any rise came around day 7, not day 1.
3. **Drop-rate numbers for Divine, Exalted or Chaos:** re-price the league in Divine the same day.
   - A Divine buff slows the Div:Ex rise rather than reversing it.
   - In 0.2.0g, Divine rose 26% in Ex terms in 72 h after the high-rarity currency buff (n=1).
4. **Farm nerfs (diminishing returns, caps, exploit fixes):**
   - Hold the farm's outputs for about a week. There is often a dip in the first 72 h, then a rise.
   - Sell the farm's inputs immediately.
5. **Farm buffs:** sell the outputs you hold within 1-3 days. The fall deepened through day 7 in every case.
6. **The same item named in two lines of one post (a use change and a supply change):** the supply line wins.
7. **Socketable stat changes:** buffs to meta-used soul cores and runes rise the same day. Niche reworks get dumped.
   Check which builds use them.
8. **Skill, ascendancy and support numbers:** list each buffed build's 2-3 key uniques and lineage supports (from
   the Vault or guides, never the builds API) and price-check them on day 0 and day 3. This is inference: it was not
   measurable here.
9. **Unique changes:** check whether old copies keep their stats (legacy) before trading.
10. **Exchange listing changes** ("now appears in the Currency Exchange", "added to the exchange"): expect a sharp
    re-price within 24 h as listings consolidate (inference).
11. **League day:**
    - In days 0-14, compare every move with the item's normal league curve (`research/market`) before calling it a
      patch effect.
    - `rules.py` takes `league_day` for exactly this.
12. **Size gate:** only act on a predicted move bigger than the noise band (24% / 38% / 49% at 24 h / 72 h / 7 d for
    a single item). A whole group moving together is more reliable than one thin item.

---

## 7. Using `rules.py` in the app

```python
import rules
rules.classify("Conquering the Vessel of Kulemak now has a chance to drop Ancient Jawbones.", league_day=20)
# [{'rule': 'drop_source_added', 'class': 'drop_source', 'direction': 'down', 'affected_group': 'Ancient Jawbone',
#   'expected_move_pct': ..., 'window': 'h72', 'confidence': ..., 'basis': 'measured', 'n_cases': ...,
#   'measured_key': 'drop_source_added:big', 'second_order': '...', 'magnitude': 'big'}]
rules.classify_notes(full_post_text, league_day=3)   # every price-relevant line of a post
```

- **What it returns.** Every line gets a rule, an affected group, a direction, the expected move, the window and a
  confidence. `basis` is `measured` or `estimated`.
- **Lookup order.** `expected_move_pct` comes from the most specific measured key with at least 3 cases (for
  example `farm_nerf:mid_late`). If none exists, it falls back to a hand-set estimate.
- **Farm nerfs and exploit fixes need `league_day`.** Without it they return the estimate, because the measured sign
  flips with league timing.
- **Item names** come from `scripts/cache/exchange_names.json`, `gem_names.json` and `unique_names.json`, built from
  the app's game data. The app can also pass its own `names` list.
- **Rebuilding.** `scripts/build_outputs.py` rewrites the `MEASURED` block whenever the data is rebuilt.

---

## 8. What I could not verify

- **Deploy time vs post time.** I used the forum post time. Most GGG posts go up at deployment, but some had Steam
  previews hours or days earlier (0.4.0d, 0.1.1).
- **0.1 data quality.** 0.1 has no other league to check against. Its early digests look odd (about 3.6 Ex per Div on
  2024-12-13, against about 99 by the end of December in market-trends S24).
- **Unique items.** poe.ninja history covers only about the last 120 days. That gave 3 minor cases and no rule.
  Second-order skill → unique effects are inference.
- **Noise.** Thin single-item markets are noisy: only 7-25% of single-item cases beat the placebo band. Group cases
  (the temple patches, 40+ items) are far more reliable.
- **Phase-check coverage.** The cross-league check uses two leagues and single hours. League-specific items (Fate of
  the Vaal temple currency, Runes of Aldur Verisium/alloys) often have no counterpart, so phase-hit is missing or
  based on n=1 there.
- **Farm inputs.** Temple medallions, crystals and tablets don't trade on the exchange.
- **Exact deploy timing for the 1.0 notes.** They are not out yet: the wiki lists 1.0.0 for 2026-12-11.

---

## Sources

- **P1:** GGG forum, Early Access Patch Notes (https://www.pathofexile.com/forum/view-forum/2212). The first post of
  all 276 threads, fetched 3 s apart, no login. Each thread URL is in `patch-impact.json`.
- **P2:** GGG public Currency Exchange history (https://web.poecdn.com/api/currency-exchange/poe2/<hour>), fetched
  2.5 s apart.
- **P3:** Exile Oracle DB `<data folder>/data/poe2kit.db`, opened read-only (`ex_price`, `patch_notes`).
- **P4:** poe2wiki.net Version history and the Cargo `versions` table (dates cross-check).
- **P5:** Steam News API for app 2694490 (timestamps cross-check).
- **P6:** poe.ninja PoE 2 economy API: item overview and item history (uniques; economy endpoints only).
- **P7:** `research/market/market-trends.md` and `sources.md`. S5, S6 and S13 are quoted above.

**Rebuild order:**
1. `scripts/fetch_forum_index.py`
2. `fetch_threads.py`
3. `build_names.py`
4. `measure.py plan` → `fetch` → `measure` → `phase_plan` → `phase_fetch` → `phase_measure`
5. `measure_curated.py fetch`, then `measure_curated.py`
6. `ninja_uniques.py`
7. `build_outputs.py`

Run each with `python -I` from `scripts/`.
