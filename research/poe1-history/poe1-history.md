# PoE 1 league history as a guide for PoE 2 (researched 2026-11-21)

> **This is analogy, not PoE 2 fact.** Everything below is measured in **Path of Exile 1** leagues. Each pattern
> is then checked against the three PoE 2 launches in `research/market/` and marked **confirmed**, **partly**,
> **contradicted** or **unknown**. Only the confirmed ones should be trusted for PoE 2 1.0 (2026-12-11), and
> even those only until the first 48 hours of 1.0 data say otherwise.

The structured version for the app is `poe1-history.json`:
- `laws`: each law with holds_in / out_of / exceptions / poe2_mapping / poe2_check / poe2_evidence;
- `league_curves`: group → league → day → relative price;
- `group_timing`, `ratios`, `hype`, `examples`, `sources`, `caveats`.

## The data

- **poe.ninja's public PoE 1 economy dumps** (https://poe.ninja/poe1/data, licensed CC-BY-SA): one zip per league,
  with a daily price for every currency and item. **33 challenge leagues**, Essence (Sep 2016, 2.4) to Allflame
  (Jul-Nov 2026). Ruthless and short event leagues (Phrecia, Ancestors) are left out. Economy data only; no builds
  or character data was touched.
- **SteamCharts** monthly peak players (Steam only) as a hype index.
- **PoE 2 side:** `research/market/market-trends.json`, plus the app DB opened read-only for three group-wide
  tests the market study didn't run (all exchange items, days 0-6 of FotV/RoA/FR; FR days 63-77).

**How prices are measured**
- PoE 1 prices are in Chaos. To match the PoE 2 study (which prices in Divines), item curves are in **top-orb terms**:
  - the **Exalted Orb** up to Sentinel (3.18);
  - the **Divine Orb** from Kalandra (3.19), when the two swapped roles.
- **Day 0** is the launch Friday, a partial day. Curves are **relative to day 1** (Saturday) unless stated.
- **Item groups only count items worth 5c+ on day 1.** Cheaper items sit on the ~1c listing floor, and their curves
  just copy the Chaos Orb.
- A **law** here means it held in **80%+ of leagues**. A **tendency** held in 60-79%. Anything under 60% is
  **not a law**.

---

## 1. The strongest laws (PoE 1), and how they map to PoE 2

| # | PoE 1 law | Holds | PoE 2 check |
|---|---|---|---|
| 1 | The Chaos:top-orb ratio does **not** peak in week 1; its high comes on day 10 or later (median day 46, 80% of peaks between day 13 and 67) | **33/33** | **confirmed** (Ex:Div peaked d14, d42, d42) |
| 2 | Mirror of Kalandra keeps rising in top-orb terms: day 42 ≥ 1.5x day 7 (median 2.6x; 3.5x by day 70) | **28/28** | **confirmed** (PoE 2: similar in 0.5, far more in 0.4) |
| 3 | Uniques fall hardest in **week 1** (median -63% in Chaos), never in week 2 | **32/32** | partly (PoE 2 commons are front-loaded too; no unique data) |
| 4 | "Week 2 crash" as the worst week | **0/32** | contradicted (a myth in both games) |
| 5 | Early-spike uniques (build enablers once the meta forms) are 20%+ below their peak by day 28 (median 59% below) | **31/32** | partly (same shape in PoE 2 meta gems and soul cores) |
| 6 | Chaos per top orb rises at least 1.2x from day 1 to day 14 (median 2.2x) | **31/33** | **confirmed** |
| 7 | Common essences lose 40%+ of their top-orb value by day 42 (median -82%) | **30/31** | **confirmed** |
| 8 | Special essences (Hysteria, Insanity, Horror, Delirium) beat the common ones | **30/30** | partly (PoE 2 Essence of Delirium rises 8-24x; PoE 1 only recovers) |
| 9 | Basic currency (Alch, Fusing, Chrome, Alt, Jeweller's, Regal...) is ≤60% of its day-1 top-orb value by day 42 (median -60%) | **28/33** | **confirmed** |
| 10 | The everyday currency loses 40%+ against the top orb by day 14 | **27/33** | **confirmed** (PoE 2 Exalted loses more) |
| 11 | Pinnacle keys/fragments fall with the Chaos Orb (≤60% of day-1 top-orb value by day 42) | **28/32** | **contradicted** (PoE 2 Fates, Cranium etc. rise 19-88x) |
| 12 | Uniques worth 10c+ are dearer in Chaos in the last 2 weeks of a league (median +7%) | **27/32** | unknown |

**In one breath:** the **timing** rules transfer well:
- the everyday currency deflates against the top orb for weeks, with no week-1 peak;
- pure sinks like the Mirror climb all league;
- commons and fresh meta items crash early;
- the worst week is week 1, not week 2.

The **sizes** don't transfer. PoE 2's Exalted deflates 4-11x where PoE 1's Chaos deflates about 2.75x, and PoE 2's
scarce exchange items (keys, catalysts, top omens) **rise** where their PoE 1 cousins fall.

---

## 2. All laws with counts

Exceptions are listed per law in the JSON.

### Currency ratio (PoE 1 Chaos per top orb ↔ PoE 2 Exalted per Divine)

| Law | Holds | Status | PoE 2 |
|---|---|---|---|
| Rises ≥1.2x day 1 → day 14 (median 2.16x) | 31/33 (not: Essence, Heist) | law | confirmed |
| Biggest jump is week 1: day 7 ≥1.4x day 1 (median 1.89x) | 29/33 (not: Essence, Heist, Ritual, Expedition) | law | confirmed (1.6x / 1.7x / 3.1x by d6) |
| Peak (3-day smoothed, days 1-70) on day 10 or later | 33/33 | law | confirmed |
| Peak is 1.8-4x day 1 (median 2.75x) | 24/33 | tendency | **contradicted**: PoE 2 4.4x / 10.7x / 8.4x |
| Last 7 days ≥10% below the peak (late slide) | 20/33 | tendency | partly (PoE 2: 25-34% slide in 3/3, RoA recovered at d108+) |
| Chaos Orb loses ≥40% vs top orb by day 14 (median: 46% of day-1 value at d14, 41% at d42) | 27/33 | law | confirmed (Ex -83 to -92% by d28) |

The ratio slide is weak in PoE 1 because the top orb **rises late** in about a third of leagues (Mirage 412 → 515,
Keepers 186 → 260, Allflame 390 → 418). Patch news moves it hard: in **Sentinel** the Exalted fell from about 180c
to 79c in the final weeks, after the 3.19 swap that made Exalted Orbs common was announced.

### Mirror and sinks

| Law | Holds | Status | PoE 2 |
|---|---|---|---|
| Mirror day 42 ≥1.5x day 7 in top-orb terms (median 2.63x; 3.8x in Chaos) | 28/28 | law | confirmed (PoE 2 Mirror d6→d42 23x / 3.6x / 2.4x; Hinekora's Lock 65x / 20x / 21x d1→d42) |

Mirror quotes before day 7 are troll listings and were ignored. Kalandra's quotes were unusable.

### Item groups (top-orb terms, day 1 = 1.00, median across leagues)

| Group | Leagues | d3 | d7 | d14 | d28 | d42 | d70 | Median peak / bottom day |
|---|---|---|---|---|---|---|---|---|
| Chaos Orb itself | 33 | 0.64 | 0.53 | 0.46 | 0.43 | 0.41 | 0.39 | 1 / 44 |
| Basic currency | 33 | 0.73 | 0.57 | 0.50 | 0.44 | 0.40 | 0.43 | 1 / 51 |
| Splinters (Breach, Timeless, Simulacrum) | 32 | 0.34 | 0.25 | 0.19 | 0.18 | 0.17 | 0.19 | 1 / 45 |
| Pinnacle keys/fragments | 32 | 0.62 | 0.50 | 0.43 | 0.37 | 0.36 | 0.42 | 1 / 35 |
| Catalysts | 20 | 0.68 | 0.64 | 0.51 | 0.37 | 0.36 | 0.37 | 1 / 51 |
| Scarabs | 23 | 0.63 | 0.69 | 0.70 | 0.68 | 0.74 | 0.81 | 8 / 11 |
| Common essences | 31 | 0.51 | 0.36 | 0.26 | 0.20 | 0.18 | 0.17 | 1 / 54 |
| Special essences | 31 | 0.51 | 0.57 | 0.56 | 0.59 | 0.71 | 0.91 | 8 / 10 |
| Fossils | 24 | 0.41 | 0.28 | 0.25 | 0.23 | 0.24 | 0.26 | 1 / 25 |
| Resonators | 18 | 1.28 | 1.55 | 1.91 | 1.88 | 2.18 | 1.78 | 42 / 2 |
| Oils | 21 | 0.76 | 0.60 | 0.47 | 0.46 | 0.49 | 0.56 | 1 / 18 |
| Delirium orbs | 16 | 1.38 | 1.69 | 1.79 | 1.89 | 2.15 | 1.75 | 32 / 2 |
| Incubators | 19 | 0.43 | 0.25 | 0.20 | 0.21 | 0.17 | 0.22 | 1 / 35 |
| Omens (3.24+) | 7 | 1.00 | 0.71 | 0.73 | 0.64 | 0.54 | 1.00 | 53 / 30 |
| Divination cards | 31 | 0.75 | 0.65 | 0.54 | 0.43 | 0.43 | 0.44 | 1 / 45 |
| All uniques (5c+) | 32 | 0.40 | 0.23 | 0.16 | 0.13 | 0.12 | 0.14 | 1 / 34 |
| Chase uniques (8 dearest on day 3; base day 3) | 32 | 1.00 | 0.81 | 0.78 | 0.83 | 0.88 | 0.87 | 14 / 15 |
| Early-spike uniques | 32 | 2.36 | 3.19 | 2.09 | 1.57 | 1.29 | 1.27 | 6 / 16 |
| New league-mechanic items | 24 | 0.73 | 0.64 | 0.56 | 0.45 | 0.54 | 0.52 | 1 / 33 |

**Group laws**

| Law | Holds | Status | PoE 2 |
|---|---|---|---|
| Common essences ≤60% by d42 | 30/31 | law | **confirmed**: essence category -90% / -89% (RoA, FR) |
| Special essences beat common ones by d70 | 30/30 | law | **partly**: Essence of Delirium 12x / 8x / 24x in PoE 2 |
| Basic currency ≤60% by d42 | 28/33 | law | **confirmed** |
| Basic currency tracks the Chaos Orb (within 35% at d42) | 24/33 | tendency | partly: PoE 2 basic orbs fall faster than Ex in week 1 |
| Pinnacle keys ≤60% by d42 | 28/32 | law | **contradicted**: Victorious Fate 42x / 29x / 53x |
| Splinters ≤30% by d42 | 24/32 | tendency | **contradicted**: PoE 2 Breach Splinter 5.2x / 0.6x / 5.0x, Simulacrum Splinter 1.9x / 0.5x / 1.3x d1→d42 |
| Catalysts ≤60% by d42 | 16/20 | law | **contradicted**: Refined Sibilant Catalyst 44x / 42x (RoA, FR) |
| Fossils ≤70% by d42 | 23/24 | law | **partly**: PoE 2 weak omens crash, top omens soar |
| Delirium orbs above day 1 at d42 | 13/16 | law | partly (no direct PoE 2 item) |
| Scarabs ≤70% by d42 | 11/23 | not a law (scarabs mostly **hold**) | unknown: tablets aren't on the exchange |
| Oils ≤50% by d42 | 11/21 | not a law | partly: oils crashed 3.8-3.18 and have held since 3.19; PoE 2 liquid emotions crash like early-era oils |
| Omens ≥ day 1 at d42 | 3/7 | not a law (they dip, then recover by d70) | partly: PoE 2 top omens rise 3-91x |
| "Rich get richer": dearer on day 1 → better by day 42 (Spearman > 0, median rho 0.07) | 22/33 | tendency, weak | partly: same sign, stronger in PoE 2 (rho 0.27 / 0.12 / 0.18 for d1→d6) |

### Uniques

| Law | Holds | Status | PoE 2 |
|---|---|---|---|
| Week 1 is the worst week (10c+ uniques, Chaos; median -63%, week 2 -18%) | 32/32 | law | partly |
| "Week 2 crash" (week 2 is the worst week) | 0/32 | **myth** | contradicted |
| Week 2 is still a down week | 27/32 | law | partly |
| Early-spike uniques ≥20% below their peak by d28 (median: 41% of peak in Chaos; 30% in top-orb terms by d42) | 31/32 | law | partly |
| Most early-spike uniques peak by day 7 (21% peak by d3, 53% by d7, 47% on d8-28) | 21/32 | tendency | partly: PoE 2 spikers peak d6-14 |
| Chase uniques beat the median unique by ≥2x from d3 to d42 (median 2.7x) | 21/32 | tendency | unknown |
| Chase uniques stay within 0.5-2x of their day-3 top-orb price at d42 (median 0.88x; +33% in Chaos) | 19/32 | tendency | unknown |

**How the spikers were picked.** "Early-spike uniques" are each league's 15 biggest day-1 → week-1 risers (10c+).
They're picked on days 1-7 only, so what happens to them afterwards is a fair test. They are the build-enabling items
of the league's meta, for example:
- Settlers: The Tides of Time, Dawnbreaker, Impresence;
- Keepers: Bonemeld, The Dark Monarch;
- Allflame: Foulborn Voice of the Storm, Foulborn Brass Dome.

**"Build enablers spike in days 1-3, then fall"** is only half right. The fall is near-universal (31/32), but the
typical peak is around **day 6**, not days 1-3. Only 21% peak by day 3.

**The chase tier** is Mageblood, Headhunter, Original Sin, Voices, Nimis and, since 3.27, their Foulborn versions. In
top-orb terms it mostly **holds** (median 0.88x by d42, a +33% rise in Chaos) while ordinary uniques lose 88%. It
neither crashes nor moons.

### League-mechanic loot, weekends, end of league

| Law | Holds | Status | PoE 2 |
|---|---|---|---|
| New mechanic loot does **not** fall harder in its first week than older items (median 0.68 vs 0.61 of start value) | 15/22 | tendency | **confirmed**: items new to the PoE 2 exchange didn't fall harder either (RoA 0.86 vs 0.79; FR 1.06 vs 0.81, d1→d6) |
| Weekend dip, items (10c+, detrended, days 8-63; median effect -0.4%) | 23/32 | tendency, tiny | unknown (FR d63-77, two weekends: no clear dip) |
| Weekend dip, ratio (median -0.5%) | 24/33 | tendency, tiny | unknown |
| Uniques dearer in Chaos in the last 14 days (median +7%); ratio flat (median 0%) | 27/32 | law | unknown |

- **"Loot from the league mechanic crashes hardest in week 1"** is **not** a law. It held in only 7 of 22 leagues
  (Breach, Delve, Ritual, Kalandra, Ancestor and Necropolis were among them). Everything crashes in week 1; new loot
  doesn't crash more.
- **"The first weekend dips prices"** can't be separated from the launch crash, because PoE leagues start on a Friday
  and the first weekend is days 1-2. By Monday (day 3) the median 5c+ unique is at 40% of its Saturday top-orb value,
  and the ratio is 1.56x. After that, weekends are only about 0.5% lower than midweek, in roughly 3 leagues of 4.
  That's too small to trade on. The sign also flipped from about Ancestor (3.22) onward.
- **End of league.** Late markets get thin: asks for decent uniques creep up in Chaos, and the top orb is flat to up.
  Don't expect a fire sale.

### Hyped vs quiet launches

**The hype index** is a league's Steam peak in its launch month, divided by the median of the previous three
launches. It runs from 0.66 (Blight) to 2.1 (Harbinger).

It shows **no link** to the shape of the economy:

| Measure | Spearman rho with hype |
|---|---|
| Ratio growth d1 → d14 | 0.02 |
| Ratio growth d1 → peak | 0.09 |
| Uniques' week-1 fall | 0.16 |
| Early-spiker fade | 0.05 |
| Mirror growth | -0.33 |
| Chase uniques | -0.28 |

**The most hyped third vs the quietest third:**
- Most hyped: Harbinger, Legacy, Crucible, Betrayal, Breach, Settlers, Ritual, Ultimatum, Delirium, Incursion.
- Quietest: Blight, Expedition, Sanctum, Sentinel, Delve, Mercenaries, Scourge, Heist, Keepers, Mirage.

| Measure | Hyped | Quiet |
|---|---|---|
| Ratio d1 → d14 | 2.21x | 2.0x |
| Uniques, week 1 | -61% | -69% |
| Mirror d7 → d42 | 2.6x | 2.9x |
| Chase uniques d3 → d42 | 0.77x | 1.06x |

**Inference:** a bigger crowd brings more buyers *and* more sellers, so the curves keep their shape. The one hint is
that a big launch makes chase items and Mirrors **a little less** scarce later. For PoE 2 1.0 (likely the biggest
launch yet), expect the same shapes as 0.4-0.5.5, not a different game.

---

## 3. Mapping PoE 1 groups to PoE 2: where the analogy holds or breaks

| PoE 1 group | PoE 2 counterpart | PoE 1 pattern | PoE 2 data (research/market) | Verdict |
|---|---|---|---|---|
| Chaos per Exalted/Divine | Ex per Div | Rises 2.2x by d14, peaks d13-67, no week-1 peak | Rises 4-11x, peaks d14-42 | **Timing holds, size breaks** |
| Chaos Orb (everyday currency) | Exalted Orb | -54% vs top by d14 | -53 to -79% by d6, -83 to -92% by d28 | Holds (PoE 2 harsher) |
| Mirror | Mirror, Hinekora's Lock | 2.6x d7→d42 in top orb | 2.4x / 3.6x (0.5 leagues), 23x (0.4) d6→d42; Lock 20-65x | **Holds** |
| Basic orbs | Transmute/Aug/Regal/Alch, Greater/Lesser orbs | -60% by d42 | -82 to -99% | Holds (PoE 2 harsher) |
| Common essences | Common/Greater essences | -82% by d42 | -89/-90% (RoA, FR) | **Holds** |
| Special essences | Essence of Delirium, Perfect Essence of the Infinite | Recover to ~0.9x by d70 | 8-24x | Direction holds, size breaks |
| Fossils (crafting consumables) | Crafting omens | -76% by d42 | Weak omens -98%; top omens +3-91x | Partly: PoE 2 splits harder into winners and losers |
| PoE 1 omens | PoE 2 omens | Dip, recover by d70 (7 leagues) | Top omens soar, weak omens crash | Partly |
| Oils | Liquid emotions | Crashed in 3.8-3.18, hold since 3.19 | -95 to -99% (RoA, FR) | PoE 2 = early-era PoE 1 |
| Scarabs | Precursor Tablets | Hold ~0.7-0.8x | Not on the exchange | Unknown |
| Splinters | Breach / Simulacrum splinters | -83% by d42 | Mostly up (Breach 5x in FotV and FR; -40% in RoA) | **Breaks** |
| Pinnacle keys/fragments | Trialmaster Fates, Breachstone, Simulacrum, Preserved Cranium | -64% by d42 | Fates 29-53x; Cranium 19-88x; Breachstone mixed | **Breaks** |
| Catalysts | Refined catalysts | -64% by d42 | ~42-44x | **Breaks** |
| Delirium orbs, Resonators (map/craft inputs that rise) | Simulacrum, Ancient bones | Rise ~2x | Mixed / up unless patched | Partly |
| Early-spike (meta) uniques | Uncut Skill Gem L20, common soul cores | Peak ~d6, -59% by d28 | Peak d6-14, -58 to -83% later | **Shape holds** (different item class) |
| Chase uniques | Chase uniques, chase lineage gems | Hold in top orb (0.88x) | No unique curves; chase lineage gems 20-50x | Unknown |
| All uniques | Uniques | -77% in week 1 (top-orb terms) | No unique curves | Unknown, so start logging |
| New mechanic loot | New exchange items in a launch | No extra crash | No extra crash (2/2) | **Holds** |
| Divination cards | None in PoE 2 | -57% by d42 | - | Doesn't map |

**Why the sizes break (inference).**
- PoE 1 prices are **listing** prices in a Chaos-denominated market with crafting benches and bulk farming of keys.
- PoE 2 prices are **executed trades** on a Currency Exchange.
- PoE 2's Exalted Orb drops far more often than PoE 1's Chaos.
- Many PoE 2 boss keys and catalysts are deliberately scarce.

So in PoE 2, **scarce exchange inputs behave like PoE 1's Mirror** (they rise), not like PoE 1's fragments (they fall).

---

## 4. What this means for 1.0 (inference, built from the confirmed rows only)

1. **Don't sell Divines for Exalted early, and don't hold Exalted.** No PoE 1 league (0/33) and no PoE 2 launch (0/3)
   had the ratio peak in week 1.
2. **Sell meta uniques and week-1 spikers into the spike, around days 4-10.** In 31/32 PoE 1 leagues they were 20%+
   below their peak by day 28; PoE 2 meta gems and soul cores did the same.
3. **Week 1 is the crash; week 2 is a smaller second leg** (27/32 still down). There's no special "week 2 crash" to wait for.
4. **Pure sinks (Mirror, Hinekora's Lock) rise all league** in both games.
5. **Don't use PoE 1 fragment, splinter or catalyst behaviour for PoE 2.** Those groups rise in PoE 2.
6. **Weekend timing isn't worth planning around** (about 0.5% effects).
7. **Start logging unique prices daily from 1.0 day 0.** Chase and meta unique curves are the biggest gap in the PoE 2
   data; PoE 1 says chase items hold while ordinary uniques lose about 88%.

---

## 5. Caveats

- **Analogy only.** PoE 1 has player-to-player trade with a Chaos unit of account; PoE 2 has a Currency Exchange.
  The game systems, drop rates and crafting differ.
- **poe.ninja dump values are daily listing-based estimates**, not trades. They carry no volume or listing count,
  so **liquidity could not be measured**.
  - Thin items (Mirror; uniques on days 0-2) are noisy.
  - Day-1 asks over-shoot, which weakens the "rich get richer" test.
- **The top orb changed at 3.19.** Ratio laws compare the Exalted (before 3.19) with the Divine (after).
- **Leagues left out of some tests:**
  - Essence (2016) has item data only from day 48, so it's out of the item laws.
  - Kalandra's Mirror quotes were unusable.
  - Omens and Tattoos exist only in the last 6-7 leagues.
- **Groups are rule-based** (names and types in `scripts/analyse.py`). "New mechanic loot" means an item name never
  priced in an earlier league. Mirage's 1,956 "new" items are mostly Foulborn and other variants.
- **Settlers ran about 10 months**, and Mercenaries through Allflame ran 4-5 months. End-of-league tests use each
  league's real last day.
- **Steam counts miss the standalone client**, so the hype index is relative only.
- **PoE 2 checks come from 3 launches**, with days 10-70 as single sampled hours (see research/market caveats).

## 6. Files and how to rebuild

- `scripts/fetch.py`: downloads the 33 dumps politely (one at a time, 3 s apart, resumable). They total **1.1 GB**, so
  the raw zips are on **F:\Research-cache\poe1\zips**, not in this folder.
- `scripts/slim.py`: keeps only the softcore challenge league and the useful item types, in `cache/slim/` (49 MB gzip).
- `scripts/players.py`: SteamCharts table, in `cache/steamcharts_238960.csv`.
- `scripts/analyse.py`: writes `cache/metrics.json`.
- `scripts/poe2_check.py`: writes `cache/poe2_checks.json` (reads research/market and the app DB, read-only).
- `scripts/build.py`: writes `poe1-history.json` (all counts are computed there).

Run them in this order, each with `python -I`: fetch, slim, players, analyse, poe2_check, build.
