# League start, the first 72 hours (researched 2026-11-21)

This is the deep follow-up to `research/market/market-trends.md`, which covers days 0-70 and is not repeated here.
This report zooms in on the first 72 hours and week 1 of the last three PoE 2 launches:
- Fate of the Vaal (**FotV**, 0.4, 2025-12-12);
- Runes of Aldur (**RoA**, 0.5, 2026-05-29);
- Forbidden Rites (**FR**, 0.5.5, 2026-09-04).

It ends with a concrete 72-hour plan for 1.0 (Dec 11 2026).

**Files:**
- `league-start-deep.json`: the structured version for the app. It has hourly curves for 75 items plus Exalted and Chaos, the Div:Ex and Chaos:Div rates, liquidity, sell windows, early buys, the plan, community tips, gear notes and sources.
- `scripts/`: the code and a cache of every digest fetched.

**Labels:**
- **Data:** measured from GGG's exchange history.
- **Web [Sxx]:** a published source (list at the end; [seller] means a currency or boost seller, low trust).
- **Inference:** my reading, not measured.
- **Confidence:** high, medium or low. "3/3" means the pattern showed in all three launches.

---

## 0. The short version

1. **Nothing trades for the first 2-3 hours.** The exchange unlocks per league at Act 4 [S44], and the first trades appear at L2-3 in all three launches. (Data, high)
2. **Ex per Divine roughly doubles between L4 and L18-24, then keeps climbing** (Data, high, 3/3):

   | League | L4 | L18-24 | L72 | day 6-7 |
   |---|---|---|---|---|
   | FotV | 36 | 70 | 93 | 146 |
   | RoA | 25 | 48 | 74 | 87 |
   | FR | 35 | 68 | 127 | 262 |

   **Convert spare Ex to Div the moment you have it, and never sell a Divine for Ex on day 1.**
3. **Campaign crafting mats are worth the most in L3-12, when supply is near zero.** (Data, high, 3/3)
   - The crash group sells for 1.4-3.1x its own L12-24 price there: Greater-tier orbs, common to Perfect essences, Gnawed bones, Diluted emotions, weak omens, Greater runes and uncut skill gems level 16-19.
   - It is down to 0.14-0.46x by day 6-7.
   - Selling a Greater essence at L3-12 instead of day 6 is worth about 10x.
4. **Some campaign drops rise instead.** Keep them: Orb of Annulment (+45 / +180 / +400% from L3-8 to day 6-7), Uncut Skill Gem (Level 1) (+42 / +440 / +800%), Glassblower's Bauble, Armourer's Scrap, and Orb of Chance (up to about L60-72). (Data, medium-high)
5. **The exchange is thin until about L18 and properly liquid only from L37-39** (Data, high, 3/3).
   - Traded value reaches 10% of the L48-72 level at L13-18, 25% at L25-31 and 50% at L37-39.
   - The Div:Ex within-hour spread first stays under 15% at L18-23.
   - The most liquid stretch of the first 3 days is L60-72.
6. **Daily rhythm** (Data, high): liquidity peaks 13:00-18:00 UTC at 0.9-1.0 of the daily max and bottoms at 21:00-01:00 UTC (0.3-0.45). Sell big lots in the peak.
7. **The best early buys gained a median +100 to +700% in Divines from L12-24 to day 6-7** (Data, high): Omen of Light, Ancient Abyss bones, Preserved Cranium, Orb of Annulment, Uncut Skill Gem (Level 20), Uncut Spirit gems level 8-20, Victorious Fate and meta lineage gems.
8. **Chaos beats Exalted as a short-term store 3/3, but it is no safer than Divine.** (Data, medium)
   - Against Div it lost 62-64% over the 72 h in FotV and RoA, and gained 51% in FR.
   - By day 6-7 it was ahead of Div only in the two 0.5 leagues.
9. **The big balance patches come on days 3-6, not in the first 72 h.** (Web, high, GGG forum [S51])
   - Examples: 0.4.0b at L76, 0.5.0b Hotfix 13 (Temple) at L106, 0.5.1 (Abyss loot nerf) at L146, 0.5.5b at L150.
   - The 72 h window has mostly crash fixes, plus one item deletion in 0.4 at about L8.
   - No rollbacks of legal farming were found.
10. **Uniques and rares have no public price history.** Snapshots show common levelling uniques at a 3-10x premium on day 2 (HC FR). (Web, low)

---

## 1. Data and method

- **Prices:** GGG's public Currency Exchange history [S1], the same endpoint the app syncs (`poe2kit/ggg_exchange.py`).
- **What the app DB already held** (read-only check):
  - `ls_price` holds derived prices for exchange hours 0-167 of each launch.
  - It has no raw markets (no low/high ratio, no stock) and nothing before the app's `start_hour`, which is the first hour with 30+ markets.
  - `exchange_hour` and `ex_price` only cover Nov 2026.
- **What was fetched:** I fetched the missing raw digests, hours L-1 to L76 of each launch (231 pages, 2.5 s apart, about 14 MB cached in `scripts/cache`, filtered to the league).
- **Hour axis:** L = hours since the official launch [S45, S47, S48]:
  - FotV 2025-12-12 19:00 UTC;
  - RoA 2026-05-29 20:00 UTC;
  - FR 2026-09-04 20:00 UTC.
  - L = the app's `offset_h` + 4 (FotV) or + 3 (RoA, FR).
  - The digest id is taken as the start of the hour it covers (GGG doesn't document this, so allow ±1 h).
  - **All three launches were on a Friday, and so is 1.0.** L28-76 is the weekend.
- **Price per item per hour:** volume-weighted on each of its markets against Ex, Div and Chaos, converted and combined by value traded, then expressed in Divines.
  - Peaks and bottoms use 3-hour volume-weighted smoothing and skip hours with under 5% of the item's peak volume.
  - Day 3 and day 6-7 come from `ls_price`.
- **Limits:**
  - `volume_traded` units are undocumented, so liquidity is a relative index.
  - Values of exactly 1.0 Ex in L3-10 are often 1:1 minimum trades.
  - No uniques or rares.

---

## 2. Hour by hour

### 2.1 When the market opens

| | FotV | RoA | FR |
|---|---|---|---|
| Launch (UTC) | Fri 19:00 | Fri 20:00 | Fri 20:00 |
| First markets | L3 (28 markets) | L3 (85) | L2 (7), L3 (106) |
| Markets at L6 / L12 / L24 / L72 | 68 (one-hour dip at L6, cause unknown) / 575 / 950 / 1,412 | 500 / 1,109 / 1,641 / 2,099 | 495 / 985 / 1,349 / 1,903 |

- **Why the 2-3 hour gap (Web, high):**
  - The exchange unlocks per league at Act 4. 0.3.0b fixed later characters having to redo it [S44].
  - The fastest players reach Act 4 about 2-3 h in. The level 1-to-maps record is 3 h 31 m (May 2026) [S55, low].
- **When each kind of item first trades** (median first hour with 3+ units traded; FotV / RoA / FR) (Data, high):
  - **L3-6:** basic campaign currency, uncut support gems, common essences, Gnawed bones.
  - **L5-10:** Greater-tier orbs and Greater runes.
  - **L9-13:** Perfect-tier orbs and Perfect essences.
  - **L10-20, the first mappers:** endgame-only items. These include top crafting omens (20 / 16 / 10), normal catalysts (17 / 14 / 12), Ancient bones (19 / 14 / 11), common soul cores (21 / 16 / 11) and fragments (19 / 22 / 18).
  - **L36-37:** Refined catalysts.
  - This fits the web's "racers hit maps around hour 10-12".

### 2.2 Divine, Exalted and Chaos

**Ex per Div** (3-hour rolling median; Data):

| L | 4 | 9 | 12 | 18 | 24 | 36 | 48 | 60 | 72 |
|---|---|---|---|---|---|---|---|---|---|
| FotV | 36 | 43 | 56 | 70 | 69 | 89 | 107 | 105 | 93 |
| RoA | 25 | 37 | 39 | 48 | 49 | 48 | 54 | 62 | 74 |
| FR | 35 | 48 | 51 | 69 | 67 | 77 | 104 | 107 | 127 |

- **Fastest 6-hour rises:**
  - FotV: L5-14 at +48 to +61% per 6 h.
  - RoA: L4-11 at +37 to +53%.
  - FR: L4-10 at +40%, and again L11-19 at +27 to +39%.
- After L24 the rate slows to about 1-2% an hour, with pauses:
  - RoA was flat from L18 to L48;
  - FotV fell about 10% at L54-72, the only real drop in any league's first 72 h.
- **Takeaway (high, 3/3):** the clock is hardest on Exalts between L4 and L19. An Ex is worth 64-65% fewer Divines by L60-72 than at L3-8 in every launch. Per Ex: 0.028 → 0.010 Div (FotV), 0.040 → 0.014 (RoA), 0.025 → 0.009 (FR).

**Chaos per Div:**

| L | 4 | 9 | 12 | 18 | 24 | 36 | 48 | 60 | 72 |
|---|---|---|---|---|---|---|---|---|---|
| FotV | 25 | 34 | 50 | 61 | 38 | 40 | 38 | 51 | 71 |
| RoA | 19 | 31 | 30 | 27 | 24 | 62 | 91 | 68 | 60 |
| FR | 25 | 31 | 28 | 29 | 20 | 26 | 21 | 20 | 18 |

- **In the first 9-12 h, Chaos lost ground to Divine in all three launches** (19-25 → 28-50 Chaos per Div).
- **After that it depends on the league:**
  - FotV: Chaos weakened late on day 3.
  - RoA: Chaos crashed against Div at L30-48, from 27 to 91 per Div, then half-recovered. I found no patch that explains it (inference: a Chaos-rich farm or dump).
  - FR: Chaos gained steadily.
- **In Exalts, a Chaos went:**
  - FotV 1.42 → 1.47 Ex (L60-72) → 1.9 (day 6-7);
  - RoA 1.05 → 1.1 → 4.8;
  - FR 1.53 → 5.9 → 25.1.
- **Takeaway (medium):** hold Chaos rather than Ex (3/3), but Divine is the safer store in the first 72 h (2/3).

### 2.3 Liquidity

The traded-value index is relative to the L48-72 mean (Data):

| L | 9 | 12 | 18 | 24 | 30 | 36 | 42 | 48 | 60 | 66 | 72 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| FotV | 0.01 | 0.04 | 0.10 | 0.16 | 0.24 | 0.43 | 0.76 | 0.77 | 0.92 | 1.40 | 1.31 |
| RoA | 0.04 | 0.09 | 0.18 | 0.24 | 0.32 | 0.49 | 0.81 | 0.78 | 0.93 | 1.38 | 1.26 |
| FR | 0.04 | 0.07 | 0.13 | 0.16 | 0.24 | 0.44 | 0.70 | 0.61 | 0.99 | 1.56 | 1.10 |

- **Index thresholds:**
  - 10% at L18 / L13 / L16;
  - 25% at L31 / L25 / L31;
  - 50% at L38 / L37 / L39.
- **Usable liquidity for single items** (units at least half the item's own 72 h median per hour):
  - L13-20 for campaign mats in the 0.5 leagues (L25-31 in FotV);
  - L30-37 for most endgame items;
  - L40-52 for Simulacrum and Mirror-tier items.
- **Hour of day**, for UTC hours across L24-72, shown as a share of the daily max:
  - 12:00-19:00 UTC is 0.83-1.0;
  - 21:00-01:00 UTC is 0.30-0.45.
  - The pattern was the same in all three launches (high).

### 2.4 When each item peaks and bottoms (Divine terms, L0-72, liquid hours only)

Full per-item data is in `item_peaks` in the JSON. Highlights (FotV / RoA / FR):

| Item | Peak hour | Bottom hour | Reading |
|---|---|---|---|
| Greater Jeweller's Orb | 12 / 25 / 7 | 68 / 64 / 61 | sell as early as you can |
| Greater Exalted Orb | 28 / 27 / 15 | 68 / 68 / 70 | sell early |
| Omen of Sinistral Necromancy | 18 / 17 / 9 | 69 / 67 / 67 | sell early |
| Perfect Essence of Battle | 17 / 13 / 11 | 61 / 68 / 61 | sell early |
| Uncut Support Gem (Level 5) | 13 / 16 / 8 | 51 / 61 / 61 | sell early |
| Preserved Rib | 31 / 27 / 24 | 70 / 68 / 61 | sell in L8-31 |
| Kulemak's Invitation | 28 / 27 / 72 | 63 / 68 / 17 | mixed |
| Orb of Chance | 57 / 72 / 48 | 29 / 13 / 19 | sell L48-72 |
| Orb of Annulment | 59 / 72 / 65 | 19 / 19 / 15 | rising; hold |
| Omen of Light | 64 / 57 / 72 | 19 / 19 / 17 | rising; buy at L17-24 |
| Hinekora's Lock | 66 / 71 / 68 | 35 / 11 / 16 | rising |
| Uncut Skill Gem (Level 20) | 72 / 70 / 72 | 34 / 19 / 18 | rising |
| Ancient Jawbone | 72 / 49 / 72 | 32 / 19 / 17 | rising |
| Perfect Chaos Orb | 33 / 68 / 70 | 49 / 33 / 37 | rising in 0.5 |

**Pattern (high, 3/3):** endgame risers bottom at **L15-20**, when the first mappers dump their first drops for currency. That is the cheapest hour to buy them. Crash items bottom at **L60-72** and keep falling after.

---

## 3. What sells first and best

### 3.1 Sell windows by group

Each figure is the group's median Divine price relative to its own L12-24 price (Data; full table in `groups` and `sell_windows` in the JSON).

| Group | L3-8 | L8-12 | L24-36 | L60-72 | day 6-7 | Best window | Conf. |
|---|---|---|---|---|---|---|---|
| Greater-tier orbs | 2.0-2.1 (RoA/FR) | 2.9 (FotV) | 0.9-1.1 | 0.38-0.59 | 0.14-0.29 | L3-12 | high |
| Essences: Greater | 2.9-3.1 | 1.5-2.8 | 0.9 | 0.44-0.58 | 0.23-0.34 | L3-12 | high |
| Essences: Lesser / normal | 1.7-2.5 | 1.1-2.1 | 0.9-1.0 | 0.57-0.73 | 0.5-0.69 | L3-12 | high |
| Essences: Perfect | 2.6-2.9 | 1.6-1.9 | 0.8-0.9 | 0.4-0.73 | 0.29-0.69 | L3-12 | high |
| Essences: special | - | 0.6-1.5 | 0.9-1.1 | 0.7-1.0 | 0.53-2.45 | hold (2/3) | medium |
| Basic campaign currency | 1.0-3.2 | 0.9-1.7 | 1.0-1.2 | 0.74-1.32 | 0.48-1.07 | L3-24 (FotV); no crash in 0.5 | medium |
| Perfect-tier orbs | 2.0 (FR) | 1.0-1.3 | 0.9-1.0 | 0.64-1.05 | 0.71-1.12 | mixed (Perfect Jeweller's falls, Perfect Exalted/Chaos rise) | medium |
| Sink / rare currency | - | 0.4-1.6 | 1.1-1.5 | 1.96-2.89 | 2.6-7.0 | **hold** | high |
| Omens: top crafting | - | 1.0-1.2 | 1.0-1.1 | 0.88-1.61 | 1.0-3.15 | **hold** | high |
| Omens: other | 1.1-2.6 | 1.3-1.6 | 0.9-1.1 | 0.66-1.24 | 0.69-1.47 | L3-12 | medium |
| Runes: Greater | 1.0-2.1 | 1.0-1.7 | 0.8-0.9 | 0.38-0.62 | 0.16-0.31 | L3-24 | high |
| Runes: Lesser / normal | 1.0-2.8 | 1.0-1.5 | 0.9-1.1 | 0.64-0.98 | 0.85-1.44 | L3-12 in FotV; little crash | low |
| Runes: named / special | - | 0.9-1.3 | 0.9-1.1 | 0.8-0.9 | 0.41-0.93 | L8-36 | medium |
| Uncut skill gems L16-19 | 2.4 (FR) | 1.9-3.0 | 0.7-1.0 | 0.4-0.97 | 0.25-0.37 | L3-12 | high |
| Uncut skill gem L20 | - | 0.9-1.5 | 1.1-1.5 | 1.7-4.2 | 3.5-6.8 | **hold to days 6-14** | high |
| Uncut spirit gems L14-20 | 0.6-0.8 | 0.9-1.2 | 0.9-1.3 | 1.0-2.1 | 1.3-2.7 | **hold** | high |
| Uncut support gems | 0.7-1.7 | 0.8-1.0 | 1.0-1.2 | 0.9-1.0 | 0.56-0.72 | any time in L3-48 | medium |
| Lineage gems (all) | - | 1.0 | 0.9-1.1 | 0.65-0.91 | 0.30-0.52 | sell non-meta by L36; hold meta | high |
| Liquid emotions: Diluted | 0.7-2.6 | 1.1-2.2 | 0.7-0.8 | 0.19-0.37 | 0.05-0.15 | L3-18 | high |
| Liquid emotions: Ancient (0.5) | - | - | 0.4-1.4 | 0.12-0.23 | 0.04-0.05 | L18-36 | medium |
| Catalysts (normal) | - | - | 1.1-1.2 | 0.95-1.46 | 0.75-1.24 | L48-72 | medium |
| Fragments and boss keys | - | 1.2 (FR) | 1.0-1.2 | 1.0-1.6 | 0.8-1.27 | L48 to day 3 | low |
| Splinters (Breach, Simulacrum) | - | 0.8-2.1 | 1.0-1.2 | 0.66-0.89 | 0.75-1.15 | L8-12 | low |
| Soul cores: common | 1.4 (FR) | 0.9-1.6 | 0.9-1.4 | 0.7-2.5 | 0.72-2.79 | hold to about day 10 (2/3) | medium |
| Abyss: Gnawed bones | 1.5-2.6 | 1.3-1.7 | 0.9 | 0.51-0.7 | 0.35-0.46 | L3-12 | high |
| Abyss: Ancient bones | - | 0.6-1.8 | 1.1-1.2 | 1.9-2.9 | 3.3-6.8 | **hold** | high |
| New-league currency (Verisium, Alloys, Fluxes, Idols at their launch) | 1.5-3.7 | 1.0-2.1 | 0.9-1.3 | 0.33-0.82 | 0.12-0.94 | L3-18 | medium |

**Why the early premium exists** (Data + inference, high):
- In L3-12, about 100-1,000 markets are open, and buyers are the fastest players. They need crafting mats and levelling power now, and pay in Ex they find plentiful.
- Supply is a handful of racers' drops.
- By L24-36, thousands of players reach Act 4, and common drops flood in: Greater orbs first trade at L6-10, and their volume share is under 3% before L18.
- **Inference for 1.0:** Acts 5-6 make the campaign longer [S46]. The premium window may stretch, but it starts at whatever act unlocks the exchange.

### 3.2 Campaign and first-map loot: what it is worth and when (Divine per item; Data)

| Item | L3-8 (FotV / RoA / FR) | L18-24 | L60-72 | day 6-7 | Verdict |
|---|---|---|---|---|---|
| Greater Jeweller's Orb | 0.22 / 0.20 / 0.28 | 0.12 / 0.10 / 0.17 | 0.04 / 0.04 / 0.03 | 0.007 / 0.017 / 0.010 | sell at once |
| Greater Exalted Orb | 0.34 (L8-12) / 0.33 / 0.40 | 0.11 / 0.20 / 0.18 | 0.05 / 0.15 / 0.06 | 0.03 / 0.13 / 0.015 | sell at once |
| Greater Essence of Abrasion (example) | 0.20 / 0.50 / 0.48 | 0.07 / 0.09 / 0.04 | 0.03 / 0.04 / 0.02 | 0.03 / 0.013 / 0.007 | sell at once |
| Gemcutter's Prism | 0.036 / 0.049 / 0.090 | 0.021 / 0.035 / 0.078 | 0.024 / 0.044 / 0.051 | 0.010 / 0.024 / 0.018 | sell by L48 |
| Lesser Jeweller's Orb | 0.020 / 0.024 / 0.009 | 0.002 / 0.005 / 0.004 | 0.0005 / 0.001 / 0.002 | 0.0003-0.0005 | sell at once |
| Orb of Alchemy | 0.020 / 0.020 / 0.010 | 0.006 / 0.018 / 0.014 | 0.005 / 0.020 / 0.008 | 0.002 / 0.007 / 0.005 | sell by L48 |
| Regal Orb | 0.016 / 0.019 / 0.005 | 0.002 / 0.005 / 0.004 | 0.001 / 0.006 / 0.005 | 0.0007 / 0.003 / 0.004 | sell at once (FotV) |
| Omen of the Liege | 0.06 (L8-12) / 0.15 / 0.05 | 0.03 / 0.04 / 0.01 | 0.002 / 0.010 / 0.003 | under 0.004 | sell at once |
| Diluted Liquid Ire | 0.028 / 0.026 / 0.022 | 0.006 / 0.020 / 0.012 | 0.001 / 0.011 / 0.002 | under 0.004 | sell at once |
| Gnawed Jawbone | 0.049 / 0.055 / 0.116 | 0.031 / 0.034 / 0.041 | 0.017 / 0.013 / 0.026 | about 0.01 | sell at once |
| Orb of Annulment | 0.086 / 0.113 / 0.104 | 0.059 / 0.099 / 0.127 | 0.086 / 0.252 / 0.398 | 0.12 / 0.32 / 0.52 | **keep** |
| Orb of Chance | 0.11 / 0.15 / 0.07 | 0.05 / 0.14 / 0.04 | 0.09 / 0.20 / 0.07 | 0.05 / 0.19 / 0.05 | sell L48-72 |
| Uncut Skill Gem (Level 1) | 0.027 / 0.023 / 0.056 | 0.03 / 0.06 / 0.14 | 0.02 / 0.07 / 0.32 | 0.04 / 0.12 / 0.51 | **keep** |
| Glassblower's Bauble | 0.008 / 0.008 / 0.013 | 0.003 / 0.008 / 0.012 | 0.007 / 0.026 / 0.023 | 0.010 / 0.023 / 0.013 | sell L48-72 |
| Armourer's Scrap | 0.006 / 0.003 / 0.005 | 0.002 / 0.004 / 0.012 | 0.006 / 0.013 / 0.017 | 0.003 / 0.009 / 0.009 | sell L36-72 |
| Soul Core of Tacati | 0.032 (L8-12) / 0.040 / 0.027 | 0.02 / 0.05 / 0.04 | 0.09 / 0.26 / 0.06 | 0.21 / 0.35 / 0.08 | keep to about day 10 |

The full table (44 items, Ex and Div) is `campaign_loot_prices` in the JSON.

### 3.3 What loses value fastest (L12-24 → day 6-7, Divine terms, 3/3)

The fast fallers below are all from `fast_fallers` in the JSON (Data, high):
- **Orbs and other currency:** Greater Jeweller's Orb -83 to -95%, Greater Regal -83 to -92%, Greater Orb of Transmutation -64 to -87%, Artificer's Orb -56 to -84%, Orb of Alchemy -61 to -64%.
- **Exalted Orb:** -48 to -75%.
- **Omens:** Omen of Sinistral/Dextral Necromancy -63 to -88%, Putrefaction -64 to -91%.
- **Abyss bones:** Preserved Jawbone -69 to -87%, Preserved Rib -51 to -62%.
- **Uncut gems:** Uncut Support Gem (Level 5) -53 to -64%, Uncut Skill Gem (Level 18) -77 to -88%.
- **Greater runes:** Storm, Desert and Glacial -80 to -93%.
- **Non-meta lineage gems:** e.g. Ahn's Citadel -94 to -97%, Ratha's Assault -89 to -98%, Arjun's Medal -88 to -93%.

---

## 4. What to buy early

The gain is the change in Divine price from the L12-24 median to day 6-7. All leagues with data had to show at least +30%. The full list with per-league numbers is `early_buys` in the JSON (Data).

| Item | Gain by day 6-7 (FotV / RoA / FR) | Buy by | Conf. | Note |
|---|---|---|---|---|
| Omen of Light | +410 / +136 / +235% | L72 (bottom L17-19) | high | keeps rising to days 42-56 (market-trends) |
| Ancient Collarbone / Jawbone / Rib | +209 / +713 / +768%; +283 / +237 / +416%; +123 / +165 / +568% | L72 | high | watch patches for new drop sources (the 0.5.3 crash) |
| Preserved Cranium | +110 / +211 / +1,875% | L48 | high | |
| Orb of Annulment | +113 / +227 / +383% | L48 | high | sell on days 10-21 |
| Uncut Skill Gem (Level 20) | +251 / +594 / +295% | L48 | high | sell on days 6-14 |
| Uncut Spirit Gems (Level 8, 14, 19) | +143 to +264% | L24 | high | Level 20: +583 / +375% (RoA / FR) |
| Victorious Fate | +54 / +159 / +336% | L48 | high | Deadly Fate +45 / +107 / +84% |
| Omen of Chaotic Quantity / Amelioration | +140 / +376 / +2,389%; +588 / +389 / +193% | L24-72 | high | cheap and thin |
| Vaal Armourer's Infuser | +789 / +80 / +249% | L24 | high | |
| Soul Core of Tacati | +812 / +657 / +72% | L24 | high | sell by about day 10 |
| Meta lineage gems (Rakiata's Flow, Dialla's Desire, Garukhan's Resolve, Rigwald's Ferocity) | +199 to +1,393% | L48-72 | high/medium | which gems are meta in 1.0 is unknown until the patch notes |
| Hinekora's Lock | +199 / +897% (RoA / FR) | L24 | medium | 1,100-2,000 Div by day 42 (market-trends) |
| Perfect Chaos Orb | +36 / +141 / +142% | L48 | medium | |
| Architect's Orb | +412 / +383% (FotV / FR) | L24 | medium | |
| Greater Essence of Opulence | +488 / +123 / +169% | L48 | high | the one Greater essence that rises |

**How to use it** (inference, medium):
- Buy risers you will use anyway (crafting omens, Fates for bossing) at L15-30, when the first mappers dump them.
- Buy pure speculation only with Divines you don't need for atlas speed. Early farming speed still compounds faster than a 2-4x hold on a few Divines.

---

## 5. Gear and uniques at league start (not on the exchange)

Web only, low-medium confidence. Details are in `gear_notes` in the JSON.

**Levelling uniques**
- **Maxroll** lists Wanderlust, Bushwhack, Thrillsteel, Death Rush, Astramentis, Thief's Torment, Goldrim, Tabula Rasa and others [S21].
  - Cheap staples are "affordable at any time".
  - Tabula Rasa, Thief's Torment and high-attribute Astramentis are dear early and drop later.
- **outof.games**, day-2 HC FR (Sep 6 2026) against now [S22]:

  | Unique | Day 2 HC | Now |
  |---|---|---|
  | Wanderlust | 0.20 Div | 0.034 Div |
  | Goldrim | 0.40 | 0.088 |
  | Thrillsteel | 0.50 | 0.16 |
  | Tabula Rasa | 4.9 | 0.96 |
  | Astramentis | 4.0 | 0.44 |

  HC is thinner and dearer, so read these as an upper bound.
- **Verdict:** pay in Exalts, early, only for what shortens your campaign. Wait until day 3-4 for anything priced in Divines.

**Early rare gear**
- **Campaign targets (ZiggyD / Maxroll) [S20]:**
  - MS boots at levels 16 / 33 / 46 (15 / 20 / 25%);
  - capped resistances and 25-30% MS for maps;
  - +skill-level weapons for casters.
- **Mid-patch price:** ilvl 82 boots with 30% MS and a resistance cost about 1 Ex (0.5.2) [S24].
- **0.4 boots craft-and-sell (seller claim, 2025-12-22) [S38]:**
  - tier-1 35% MS boots with weak other mods: 0.3-0.5 Div;
  - good life/resistance finishes: 6-7 Div;
  - top tier: 10+ Div;
  - cost: about 1.5-3 Div for 10 bases plus omens.
- No dated day-1 prices exist for +level weapons or resistance jewellery.

**Chase uniques, week 1**

| Unique | HC FR day 2 | SC FR now | SC RoA (Jul 24 2026) |
|---|---|---|---|
| Headhunter | 78 Div | 11 Div | 60 Div |
| Mageblood | 374 Div | 110 Div | 230 Div |
| Kalandra's Touch | 27 Div | 1.8 Div | - |

- Sources: [S22, S25].
- In 0.5.5, day-1 Magebloods and Headhunters came from campaign Ritual unique shops (Fubgun and Spicysushi video titles [S40]).
- **Inference (low):** chase uniques are dearest in Divines in week 1. Buy them after day 4-5 unless one unlocks a farm.

**Recommendation for the app:** start saving poe.ninja unique snapshots daily from 1.0 hour 0. That is the only way to get real unique curves.

---

## 6. What top players and guides do

PoE 2 unless marked PoE 1.

**Campaign speed vs farming**
- **Rush camp:**
  - "Hours 0-8: rush maps", because the "first hours of a fresh economy are where the most currency is made per hour" (Timesaver [S30, seller]).
  - Fubgun: rush the campaign and atlas, sell tradeables at once (market-trends sources S14, S15).
- **Farm-along camp:** clear every campaign Ritual on night 1, aiming for Act 3, the first ascendancy and two Ritual clusters (KamiLabs, 0.5.5 [S32]).
- **The data favours the rush camp**, within limits:
  - Reaching the exchange early is what pays: the L3-12 premium.
  - Reaching maps by L10-20 lets you sell the first endgame drops.
  - Mapping before about L18 isn't the main money: endgame items barely trade until then.

**"First map" money**
- **0.5:** Ritual first, with the first 10-15 atlas points in Ritual and T5-T8 maps [S35, S42]. Expedition "needs no atlas investment" [S39, seller].
- **Mirror Tier [S37]:** farm the lowest tier that drops your target mods (T1 for MS boots, T7 for resistance jewellery, T11 for +3 amulets).
- **Data:** the first endgame items to trade (L10-20) are the ones that pay best early: Omen of Light, Ancient bones, catalysts, soul cores, crisis fragments.

**Which mechanics paid most in week 1** (Web, mostly video titles, low-medium)

| Launch | What paid |
|---|---|
| 0.1 | Breach |
| 0.2 | Ritual ("70+ Div from Rituals alone"), Expedition logbooks, Delirium/Simulacrum |
| 0.3 | Map juicing, Ritual, Expedition |
| 0.4 | Vaal Temples ("100 d/hr" titles; "hundreds of Div" per snake run until the Jan 3 2026 nerf), plus Abyss and Delirium omens |
| 0.5 | Ritual (Headhunter/Mageblood), Abyss Rogue Exiles (nerfed in 0.5.1, day 6), Breach, Grand Expedition, lineage gems ("400+ Div in two days", Fubgun) |
| 0.5.5 | Grand Expedition ("60 d+/hr"), Abyss, Ritual, Trial of Chaos, Fracturing Orb farm |

Sources: [S40, S6, S35, S39]. The common thread: every launch's top farm was the new or reworked mechanic, plus Ritual or Expedition.

**The day-1 craft-and-sell meta**
- MS boots (0.4), belts (0.5, "15-20 Div sale for 1-3 Div cost" [S39, seller]), and +3 amulets, staves and spears (SaVeQ titles [S40]).
- No independent price data. The exchange data shows the inputs (Greater orbs, essences) are at their dearest in L3-12. Inference: crafting to sell pays best after L24, when inputs are cheaper but demand for gear is still rising.

**Risks in week 1** (GGG forum [S51], high)

| When | League | What happened |
|---|---|---|
| L~8 | 0.4 | Hotfix 4 deleted every Cartographer's Chisel and Engineer's Orb (they had dropped by bug) |
| L~76 | 0.4 | 0.4.0b raised Tablet drops |
| L~146 | 0.4 | 0.4.0c buffed Temples; the boom was nerfed about day 22 (Jan 3 2026) |
| L~33 | 0.5 | Waystone buff |
| L~78 | 0.5 | Ritual reroll cost reduction capped at 90% |
| L~106 | 0.5 | Temple nerf |
| L~146 | 0.5 | 0.5.1 cut Elite Abyss loot |
| day 6-7 | 0.5 | Runeforging un-fracture exploit closed; a Hinekora's Lock crafting source disabled |
| L~1-4 | 0.5.5 | Atzoatl Map Device off for about 3.5 h |
| L~40-50 | 0.5.5 | Trial of Chaos exploit and Ocean Expedition fixes |
| L~150 | 0.5.5 | 0.5.5b raised Tablet drops |

- No bans or rollbacks for legal play.
- **Rule:** a strong farm found in L24-72 has usually survived to about day 4-6. Sell its output fast, before the "now also drops" or loot-nerf patch.

**PoE 1 analogy (labelled, weak):** "be the first to do something"; sell surplus currency to fund upgrades before choosing an endgame strategy [S56, S57]. Same timing logic, but different currencies.

---

## 7. What people say vs what the data shows

Every tip is treated as an opinion and checked against the exchange data. The full list (22 tips) is `community_tips` in the JSON.

| # | Tip | Source | Verdict | Evidence | One-line verdict |
|---|---|---|---|---|---|
| 1 | Rush maps; the first hours make the most per hour | Timesaver [S30, S31, seller] | **partly** | Mats are 1.4-3.1x their L12-24 price at L3-12, but liquidity is 1-7% of the weekend level before L12, and endgame items trade only from L10-20 | Rush to the exchange (Act 4) first; maps pay from about L15 |
| 2 | Don't use Ex/Chaos/Div in the campaign | ZiggyD/Maxroll [S20] | **confirmed** | Div:Ex doubles L4 → L18-24 (3/3); Greater orbs are 2-3x dearer at L3-12 | Sell or convert them; don't slam them |
| 3 | Buy levelling uniques / MS boots / resistances with Exalts | ZiggyD/Maxroll [S20, S21] | **partly** | Ex loses 64-65% vs Div by L60-72, but levelling uniques carry a day-1-2 premium (Wanderlust 0.20 vs 0.034 Div) | Pay in Ex, only for real speed |
| 4 | Sell rare bases, uncut gems and bulk basic currency in hours 8-24 | Timesaver [S30, seller] | **partly** | Basic currency premium 3.2x / 1.36x / none; uncut skill gems L16-19 -63 to -75% by day 6-7; but uncut L20 (+251 to +594%), L1 and spirit gems rise | Sell the crash ones; keep L20, L1 and spirit |
| 5 | A day-1 sale gets about 3x the day-10 price | Timesaver via KamiLabs [S32] | **partly** | Crash group about 3-10x (Greater essences 2.8-3.1x vs 0.23-0.34x); risers do the opposite | True for crash items only |
| 6 | Farm Ex + Chaos first, convert to Divine later | Timesaver 1.0 guide [S31, seller] | **contradicted** | Ex per Div L3-8 → L60-72: 35 → 98, 25 → 72, 41 → 114 | Convert as you go, not later |
| 7 | Sell Ex for Div on a schedule; hold early Divines | Timesaver [S33, S30, seller] | **confirmed** | Div:Ex never fell more than about 11% in any 6 h window of L4-72, and rose up to +61% in 6 h | Do it continuously from L3 |
| 8 | Keep liquidity in Chaos | EODGamerz [S34], techsngames [S35] | **partly** | Chaos beat Ex 3/3 by day 6-7, but vs Div it went -62% / -64% / +51% in 72 h | Chaos over Ex, but Div over Chaos |
| 9 | Don't buy gear in the first 48 h | Switchblade [S8], Timesaver [S33] | **partly** | Right for the crash group (Greater Jeweller's -80% by L60-72); wrong for risers (sink currency 2-3x by L60-72) | Wait on commodities; buy risers early |
| 10 | Don't buy Z until the weekend | the player's example; no published source | **partly** | The weekend (L28-76) is the liquidity peak, and crash items are at 0.38-0.59x by then; risers are dearer | Good for commodities, bad for risers |
| 11 | Prices are chaos in the first 48 h; don't panic-buy | seller snippets [S36] | **confirmed** | Div:Ex within-hour gap 20-140% at L3-10, under 15% only from L18-23 | Avoid big buys before about L18 |
| 12 | Park wealth in omens; buy Hinekora's Lock early | Mirror Tier [S37] | **confirmed** | Omen of Light +136 to +410%, Hinekora's +199 / +897% by day 6-7 (Whittling 2/3) | Yes: Light, Annulment and Erasure omens, Locks |
| 13 | Sell essences early | Timesaver; Maxroll [S23] | **confirmed** | Best band L3-12 3/3; 0.23-0.69x by day 6-7 | Sell common to Perfect essences at once; keep special ones |
| 14 | Don't craft early | Timesaver [S30] | **partly** | Inputs are 2-3x dearer at L3-12; craft-to-sell can't be checked | Don't spend mats on yourself before L24 |
| 15 | Craft and sell MS boots / belts / amulets on day 1 | IGGM, ConquestCapped [seller], SaVeQ titles [S38-S40] | **unverifiable** | Only seller claims (boots 0.3-10+ Div) | Possible, unproven |
| 16 | Clear every campaign Ritual on night 1 | KamiLabs [S32] | **unverifiable** | No drop data; "other omens" were 2.6x at L3-8 in FR | Sell what you get fast |
| 17 | Save campaign Tribute for the boss unique shop | Timesaver [S41, seller] | **unverifiable** | 0.5.5-specific | |
| 18 | Commit your first atlas points to one mechanic (Ritual or Expedition) | techsngames, GamesFuze, ConquestCapped [S35, S42, S39] | **unverifiable** | The exchange shows prices, not income; Expedition Logbook rose in RoA but crashed in FR | |
| 19 | Flip on the exchange early | GGG forum [S43]; Maxroll [S18] | **partly** | Wide spreads early, but thin fills (1-7% volume) | Small and risky before L18 |
| 20 | Rush to Act 4 for the exchange | EODGamerz [S34]; GGG 0.3.0b [S44] | **confirmed** | First trades at L2-3; biggest premiums L3-12 | Yes |
| 21 | Common uniques are only dear on day 1 | Maxroll [S21] | **partly** | HC day 2 3-10x vs later [S22]; no SC day-1 data | Likely; weak evidence |
| 22 | Hold Chaos until you run T8+ | techsngames [S35] | **partly** | As tip 8 | |

**Folded into the plan:** tips 2, 7, 11, 12, 13 and 20, plus the parts of 1, 3, 4, 5, 8, 9, 10 and 14 that the data supports.

**Left out of the plan:** tip 6, "farm Ex and Chaos first, convert to Divine later". It is contradicted: in every launch, converting later cost 55-65% of the Ex's Divine value within 72 hours.

---

## 8. The first-72-hours plan (generic, any class)

L = hours since the 1.0 launch.
- **1.0's launch hour is not announced** [S46]. Past launches were 19:00-20:00 UTC on a Friday.
- **1.0 adds Acts 5-6**, so map entry will likely come later than L10-20. The exchange timing (Act 4) may not move. Check both on launch day.

### L0-3: before the exchange opens
- **Do:**
  - Race the campaign. Pick up every currency item, essence, rune, uncut gem and omen; ignore gear you'll replace.
  - Don't spend Ex, Chaos, Div, Greater/Perfect orbs, essences or Annulments on your own items.
  - Play a build that works with no trades.
- **Why:** no trades exist before L2-3 (3/3). The mats you hold now are worth 1.4-3.1x more in the next 9 hours than at L24.

### L3-12: the thin, premium market (first exchange access at Act 4)
- **Sell at once,** in small lots:
  - Greater-tier orbs;
  - common, Greater and Perfect essences;
  - Lesser Jeweller's, Regal, Alchemy, Artificer's, Transmutation and Augmentation;
  - Gnawed bones, Preserved Rib and Jawbone;
  - Diluted emotions;
  - uncut skill gems level 16-19;
  - weak omens (Liege, Putrefaction, Necromancy, Exaltation omens);
  - Greater runes;
  - the new league's own basic currency.
- **Convert:** every spare Exalted Orb into Divines, right away. Never sell a Divine for Ex.
- **Buy:** only campaign speed (MS boots, a weapon, a key levelling unique), paid in Ex.
- **Keep:** Divines, Chaos (over Ex), Orb of Annulment, Orb of Chance, Glassblower's Bauble, Armourer's Scrap, Uncut Skill Gem level 1 and 20, Uncut Spirit gems level 14+, Perfect Exalted/Chaos, any top crafting omen.
- **Why:**
  - crash-group medians are 1.4-3.1x their L12-24 price here, and 0.14-0.46x by day 6-7;
  - Ex per Div rises 40-61% per 6 h in L4-19;
  - the "keep" items rose in 3/3.

### L12-24: first night, first maps for fast players
- **Do:**
  - Keep converting Ex to Div: RoA and FR still rose +23-39% per 6 h at L11-19.
  - Finish the campaign. Endgame items start trading at L10-20.
  - Sell the rest of the crash group before L24. Spreads tighten under 15% around L18-23, so prices are now trustworthy.
- **Sell:** leftover Greater essences, runes and orbs; non-meta lineage gems (by L36); Ancient emotions if the league has them (peak L18-36); Breach/Simulacrum splinters.
- **Keep:** first endgame risers (Ancient bones, Preserved Cranium/Collarbone, top omens, Fates, Hinekora's Lock, Refined catalysts, Uncut Skill Gem (Level 20), special essences).
- **Why:** risers bottom at L15-20 (3/3), so this is also the cheapest window to buy them.

### L24-48: Saturday, mapping and atlas
- **Do:**
  - Push the atlas in the one mechanic you farm. This is the season's money engine; farm for value.
  - With spare Divines, buy risers you'll need or hold: Omen of Light, Orb of Annulment, Ancient bones, Uncut Skill Gem (Level 20), Uncut Spirit gems 14+, Victorious/Deadly Fate, meta lineage gems once the meta is clear.
  - List larger lots at 13:00-18:00 UTC.
- **Sell:** named/special runes (by L36), uncut support gems (before day 3), normal catalysts from L48.
- **Why:**
  - liquidity crosses 50% of the weekend level at L37-39, so orders fill;
  - risers bought at L12-36 gained a median +100-400% by day 6-7;
  - Div:Ex now grows only about 1-2% an hour.

### L48-72: Sunday into Monday, the liquidity peak
- **Do:**
  - Bulk-sell and make big buys now: L60-72 is the most liquid stretch, at 1.0-1.56x the L48-72 mean.
  - Read every hotfix. The first farm nerfs and drop-rate changes come on days 3-6; sell a strong farm's output before them.
  - Start daily unique-price snapshots in the app.
- **Sell:** Orb of Chance (peak about L48-72), normal catalysts, Concentrated emotions if they rose, anything left from the crash group.
- **Keep, with exit times:**

  | Item | Sell |
  |---|---|
  | Sink currency (Hinekora's, Architect's, Vaal infusers, Fracturing) | weeks 5-8 |
  | Top omens | weeks 5-8 |
  | Orb of Annulment | days 10-21 |
  | Common soul cores | about day 10 |
  | Uncut Skill Gem (Level 20) | days 6-14 |
  | Meta lineage gems | weeks 2-6 |

- **Why:** a small Div:Ex dip is possible here (FotV -10% at L54-72). Sink currency is at 1.96-2.89x by L60-72 and 2.6-7x by day 6-7.

**Always:**
- Price everything in Divines.
- Never save in Exalts.
- Move Divines out of the stash before bulk trades (scam warning [S58]).
- Treat the first 24 h of 1.0 as a test: check that Div:Ex is rising and that the crash group falls. If not, the 1.0 economy differs and the plan's timings need moving.

---

## 9. What could not be verified

- **Uniques and rares:** no public price history. Only HC day-2 snapshots from outof.games, and seller claims for crafted boots. No day-1 softcore numbers.
- **The exact meaning of a digest hour** (start or end of the hour, ±1 h) and **the units of `volume_traded`.** Liquidity is relative only.
- **Real executable spreads and the gold-fee formula.** No source documents the fee.
- **Income per hour by mechanic.** The exchange shows prices, not drops. Mechanic rankings come from creator titles and seller sites.
- **The cause of the RoA Chaos crash at L30-48.** No matching patch line was found.
- **1.0 specifics:**
  - the launch hour;
  - whether the exchange still unlocks at Act 4;
  - how much longer the 6-act campaign makes the road to maps;
  - the new league's own currency (Crimson Iron and Infused Blood come from castle treasuries [S49]);
  - whether 0.5's Chaos role survives.
- **Creator transcripts:** no YouTube transcripts were retrievable. Only titles and third-party summaries.
- **Blocked or not used:**
  - poe2wiki (bot wall), Mobalytics (403), game8 (402) and web.archive.org could not be read.
  - Reddit was not opened (rule).
  - poe.ninja builds and character pages were not used (rule).

## Sources

| # | Source | URL |
|---|---|---|
| S1 | GGG public Currency Exchange history API | https://web.poecdn.com/api/currency-exchange/poe2/<unix hour> |
| S2 | Exile Oracle DB, `ls_price` (read-only) | <data folder>\data\poe2kit.db |
| S3 | market-trends.md / .json (earlier research) | research/market/ |
| S6 | PCGamesN, temple diminishing returns | https://www.pcgamesn.com/path-of-exile-2/patch-notes-temple-diminishing-returns |
| S8 | Switchblade Gaming economy guide (low trust) | https://www.switchbladegaming.com/path-of-exile-2/economy-guide-4/ |
| S18 | Maxroll, Flipping with the Currency Exchange | https://maxroll.gg/poe2/resources/flipping-with-the-currency-exchange |
| S20 | Maxroll (ZiggyD), Comprehensive League Start Leveling Guide | https://maxroll.gg/poe2/getting-started/comprehensive-league-start-leveling-guide |
| S21 | Maxroll, The Best Leveling Uniques | https://maxroll.gg/poe2/meta/the-best-leveling-uniques |
| S22 | outof.games PoE 2 economy (Headhunter, Mageblood, Wanderlust, Tabula Rasa...) | https://outof.games/realms/poe2/economy/unique-accessories/ |
| S23 | Maxroll, Currency Guide | https://maxroll.gg/poe2/resources/currency-guide |
| S24 | Maxroll, How to Craft in PoE 2 | https://maxroll.gg/poe2/resources/how-to-craft-in-path-of-exile-2 |
| S25 | Prima Games, most expensive items, Dawn of the Hunt | https://primagames.com/tips/most-expensive-items-in-path-of-exile-2-dawn-of-the-hunt |
| S30 | Timesaver, Forbidden Rites league start guide [seller] | https://timesaver.gg/blog/poe2-forbidden-rites-league-start-guide-0-5-5 |
| S31 | Timesaver, 1.0 league start currency guide [seller] | https://timesaver.gg/blog/poe2-1-0-league-start-currency-guide |
| S32 | KamiLabs, Forbidden Rites first night | https://kami-labs.fr/en/path-of-exile-2/forbidden-rites-league-start-plan-jour-1/ |
| S33 | Timesaver, Economy cooked 0.5.5 [seller] | https://timesaver.gg/blog/poe2-economy-cooked-what-currency-worth-farming-maps-0-5-5 |
| S34 | Gistly summary of EODGamerz' 0.5 market analysis | https://gist.ly/youtube-summarizer/path-of-exile-2-05-league-market-profit-guide |
| S35 | techsngames, PoE 2 currency farming guide 2026 | https://techsngames.com/path-of-exile-2-currency-farming/ |
| S36 | Timesaver, trade prices Standard vs league [seller] | https://timesaver.gg/blog/poe2-trade-prices-wrong-standard-vs-league-forbidden-rites-0-5-5 |
| S37 | Gistly summary of Mirror Tier's league-start gearing | https://gist.ly/youtube-summarizer/poe2-league-start-farm-craft-and-beat-inflation |
| S38 | IGGM, 0.4 boots crafting [seller] | https://www.iggm.com/news/poe-2-patch-0-4-0-how-to-get-currency-by-crafting-boots |
| S39 | ConquestCapped, farming Divines in 0.5 [seller] | https://conquestcapped.com/guides/path-of-exile-2/poe-2-currency-farming/ |
| S40 | poebuilds.cc top farming videos per league (YouTube titles) | https://www.poebuilds.cc/poe2/farming/top?league=rites |
| S41 | Timesaver, Mageblood from campaign rituals [seller] | https://timesaver.gg/blog/poe2-mageblood-campaign-rituals-unique-shop-0-5-5 |
| S42 | GamesFuze, more Divines in RotA | https://gamesfuze.com/guides/how-to-get-more-divines-in-path-of-exile-return-of-the-ancients/ |
| S43 | GGG forum, How to make currency in PoE2? | https://www.pathofexile.com/forum/view-thread/3863804 |
| S44 | GGG forum, 0.3.0b patch notes (exchange unlock) | https://www.pathofexile.com/forum/view-thread/3840893 |
| S45 | Steam, The Last of the Druids launches soon | https://store.steampowered.com/news/app/2694490/view/1818752592125334 |
| S46 | Steam, Full Release on December 11 PST | https://store.steampowered.com/news/app/2694490/view/1848664643347683 |
| S47 | Steam, Forbidden Rites FAQ | https://store.steampowered.com/news/app/2694490/view/1842212951308718 |
| S48 | Steam, Return of the Ancients launches soon | https://store.steampowered.com/news/app/2694490/view/1833968530889810 |
| S49 | poe-vault, Conquerors of Wraeclast explained | https://www.poe-vault.com/poe2/news/conquerors-of-wraeclast-explained-path-of-exile-2s-1-0-league-has-you-raise-an-army |
| S50 | Inven Global, Jonathan Rogers interview | https://www.invenglobal.com/articles/28823/jonathan-rogers-poe2s-official-launch-goal-is-1-million-players |
| S51 | GGG PoE 2 patch-notes forum (every hotfix thread, first two weeks of each launch) | https://www.pathofexile.com/forum/view-forum/2212 |
| S52 | Steam, Return of the Ancients two-week recap | https://store.steampowered.com/news/app/2694490/view/1835236783568632 |
| S53 | PCGamesN, RotA Divine Orbs more common | https://www.pcgamesn.com/path-of-exile-2/return-of-the-ancients-divine-orbs |
| S54 | GGG forum, 0.5.5d patch notes | https://www.pathofexile.com/forum/view-thread/4008534 |
| S55 | Gistly summary, fastest Spear Twister levelling (3h31m to maps) | https://gist.ly/youtube-summarizer/path-of-exile-2-fastest-spear-twister-leveling-guide |
| S56 | GGG forum (PoE 1), advice for currency during league start (2019) | https://www.pathofexile.com/forum/view-thread/2511170 |
| S57 | Maxroll (PoE 1 3.30), League Start Alch & Go | https://maxroll.gg/poe/currency/league-start-alch-and-go |
| S58 | poe-vault, This PoE2 trading trick could save your Divines | https://www.poe-vault.com/poe2/news/this-poe2-trading-trick-could-save-your-divines |
