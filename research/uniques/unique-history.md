# PoE 2 unique prices by league day (researched 2026-11-21)

This is the unique-item companion to `research/market/market-trends.md`. The Currency Exchange has no uniques, so that
report had no unique curves. This one rebuilds them for five leagues from public aggregator data. The structured
version for the Oracle is `unique-history.json`; all 140 tracked uniques are in `derived/uniques_merged.json`.

| League | Patch | Start (UTC) | Unique data from |
|---|---|---|---|
| Dawn of the Hunt (DotH) | 0.2 | 2025-04-04 | poe2scout, from day 1-2 |
| Rise of the Abyssal (RotA) | 0.3 | 2025-08-29 | poe2scout, from day 0 |
| Fate of the Vaal (FotV) | 0.4 | 2025-12-12 | poe2scout, from day 0 |
| Runes of Aldur (RoA) | 0.5 | 2026-05-29 | poe2scout from day 0; poe.ninja archive copies days 1-37; poe.ninja history from day 57 |
| Forbidden Rites (FR) | 0.5.5 | 2026-09-04 | poe.ninja history from day 1-4 (all days); poe2scout from day 8 |

**Day numbering.** Day 0 is the launch date. Launches are around 20:00 UTC, so day 0 is only about 4 hours. Day 1 is the
next UTC day. Every price is in **Divine Orbs** and is a listing-based estimate, not a confirmed sale.

**How to read the tables.**
- `*` means fewer than 3 listings: unreliable, often a troll or price-fixed listing.
- For FR the `d3` column is really **day 4** for most chase items. That is poe.ninja's first full day; before it, poe.ninja did not list them at all.

**Source codes in the JSON** (`day_source`):
- **N:** poe.ninja item history.
- **A:** an Internet Archive copy of poe.ninja.
- **S:** poe2scout.
- **D:** the app DB.
- **`~`:** estimated: unit inferred, or converted with poe2scout's daily rate.

Everything else is sourced.

---

## 1. Summary

1. **Two kinds of chase unique behave in opposite ways.**
   - **Single-source items climb for 5-7 weeks:** Temporalis and The Last Flame. They come only from Zarokh in Trial of the Sekhemas.
   - **Repeatable-source items peak early and then crash:** Headhunter peaks on day 7-11; Mageblood on day 11-18.
2. **Headhunter is the most reliable curve in the data.** It peaked on day 7-11 in 5 of 5 leagues, then lost 84-96% by league end.
3. **Mageblood (new in 0.5):**
   - Starts at 72 div on RoA day 1, with 20 listings.
   - Peaks at 641 div on day 18 (RoA) and 579 div on day 11 (FR).
   - Then falls 60-80% as listings go from 20 to over 7,000.
4. **Temporalis:**
   - 4 of 5 leagues: it climbs from tens or hundreds of div to thousands. RoA went from 218 on day 3 to a 5,101 peak on day 35. FR went from 1,369 on day 4 to an 11,324 peak on day 34.
   - It never has more than about 60 listings.
   - 0.3 was the exception: it sat at 44-83 div all league.
5. **Levelling uniques** are worth most on day 0-1. The median one loses 70-90% by day 7 and 85-98% by day 28.
6. **Mid-tier build-enablers:**
   - The normal shape: a spike on day 2-7, then about -90% by day 28.
   - Kalandra's Touch, Rite of Passage, The Taming, Sacred Flame, The Ordained and Controlled Metamorphosis all follow it.
   - The exception is when a build becomes the meta. In 0.2, Kalandra's Touch went from 1 to 985 div.
7. **Late-endgame pieces bottom out in week 1-2 and climb late:**
   - Death Articulated: 19-280 div at the end.
   - Grand Spectrum, Runemastered Tabula Rasa and Morior Invictus, Against the Darkness, Bursting Decay.
8. **New late-endgame chase climbs all league:**
   - Voices: corrupted FR went from 226 to about 1,400.
   - Runeseeker's Call: Runemastered FR went from 250 to 1,530.
9. **First copies of chase items appear on day 0-3 on 1-20 listings.**
   - Headhunter: day 0.3-1.3.
   - The Last Flame: day 0.8-2.6.
   - Temporalis: day 1.1-5.8.
   - Those prices are noise: 2-10x swings within a day.
10. **Compare leagues in Mirror terms.** The Mirror on day 42 was 1,110 div (0.2), 1,421 (0.3), 6,527 (0.4), 5,227 (0.5) and 5,397 (0.5.5).
11. **0.4 is an outlier.** The temple Divine glut made every scarce item 10-500x more expensive in Divine terms after week 2.
12. **Mageblood vs Temporalis.** See section 2. In short: close only in week 1 of RoA, never equal, and 16x (RoA) to 56x (FR) apart now.

---

## 2. Mageblood vs Temporalis (the player's memory)

**Claim:** "At the start of Runes of Aldur, Mageblood cost about the same as Temporalis."

**Verdict:**
- **Roughly true for the first week only.** Both were a few hundred Divines, but Temporalis was always 1.5-3.5x Mageblood. They were never equal.
- **Headhunter was actually above Mageblood for the first 2-3 days.** On day 1 it was 97 vs 72; on day 3, 202 vs 146.
- **Confidence:** high from day 3, medium for days 1-2 (Temporalis had only 1-3 listings).

| RoA day | Mageblood (listings) | Temporalis (listings) | Temporalis ÷ Mageblood | Mirror (div) |
|---|---|---|---|---|
| 1 | 72 (20) | 153 (1) | 2.1 | - |
| 2 | 100 (35) | 350 (3) | 3.5 | 399 |
| 3 | 146 (128) | 218 (10) | 1.5 | 606 |
| 7 | 377 (482) | 730 (14) | 1.9 | 1,609 |
| 14 | 559 (1,522) | 1,398 (29) | 2.5 | 2,445 |
| 28 | 630 (4,472) | 3,936 (40) | 6.2 | 4,646 |
| 42 | 387 (7,110) | 4,555 (56) | 11.8 | 5,227 |
| 170 (now) | 225 (3,959) | 3,599 (41) | 16.0 | 5,000 |

| FR day | Mageblood (listings) | Temporalis (listings) | Temporalis ÷ Mageblood |
|---|---|---|---|
| 4 (first poe.ninja day) | 400 (398) | 1,369 (2) | 3.4 |
| 7 | 530 (743) | 1,970 (5) | 3.7 |
| 14 | 535 (2,501) | 6,721 (10) | 12.6 |
| 28 | 303 (5,164) | 7,100 (20) | 23.4 |
| 42 | 170 (6,972) | 9,063 (25) | 53 |
| 78 (today) | 110 (6,682) | 6,198 (18) | 56 |

**Why the gap opens: supply.**
- **Mageblood has repeatable sources.** It comes from Ritual favours and the tribute shop, and from an Orb of Chance on a Utility Belt. In 0.5.5 the campaign tribute shop was added too. Its listings went from 20 to about 7,000 in six weeks.
- **Temporalis has one gated source:** Zarokh, the Temporal, in Trial of the Sekhemas level 80+. You need The Last Flame and an effectively deathless run. Its listings stayed at 10-60 in every league.

**In Mirror terms:**
- **Mageblood** went from 0.24 Mirror (RoA day 3) to 0.04 (now). In FR it went from 0.32 to 0.02.
- **Temporalis** went from 0.36 to 0.87 Mirror in RoA (day 3 → day 42). In FR it stayed at 0.9-1.7.

**For 1.0:** expect the same opening.
- **Mageblood:** buyable for under 100-150 div on day 1, at the top by day 10-18, then dropping.
- **Temporalis:** about 2x Mageblood in week 1, then 10x or more from week 4.
- **Caveat:** if 1.0 changes either drop source, this resets.

---

## 3. Checkpoint tables (Divine)

`end` is the last day with data. For 0.2, 0.3 and 0.4 that is the true end of the league (day 101-164). For 0.5 and 0.5.5 it is today (day 176 and day 78).

### Chase uniques
| Unique | League | d0 | d1 | d3 | d7 | d14 | d28 | d42 | end | peak (day) | end/d1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Temporalis | 0.2 DotH | - | - | - | 187 | 370 | 371 | 548 | 411 | 1,315 (d83) | - |
| Temporalis | 0.3 RotA | - | - | 195* | 44.4 | 80.3 | 44.6 | 21.6 | 48.1 | 83.0 (d8) | 0.25 |
| Temporalis | 0.4 FotV | - | - | 43.8 | 52.8 | 744 | 7,402 | 25,803 | 21,433 | 26,956 (d149) | 490 |
| Temporalis | 0.5 RoA | - | 153* | 218 | 730 | 1,398 | 3,936 | 4,555 | 3,710 | 5,101 (d35) | 24 |
| Temporalis | 0.5.5 FR | - | - | 1,369* | 1,970 | 6,721 | 7,100 | 9,063 | 6,198 | 11,324 (d34) | 4.5 |
| The Last Flame | 0.2 DotH | - | - | 186* | 99.9* | 253 | 308 | 797* | 332 | 1,113 (d52) | 1.8 |
| The Last Flame | 0.3 RotA | - | - | 15.6 | 36.0 | 68.8 | 44.2 | 113 | 94.6 | 190 (d55) | 6.1 |
| The Last Flame | 0.4 FotV | - | 222* | 30.2 | 68.5 | 797 | 8,169* | 23,089 | 11,380 | 27,088 (d55) | 51 |
| The Last Flame | 0.5 RoA | - | 82.4 | 169 | 610 | 915 | - | - | 2,960 | 4,140 (d57) | 36 |
| The Last Flame | 0.5.5 FR | - | - | 1,724 | 2,170 | 5,156 | 7,194 | 7,640 | 5,620 | 8,500 (d46) | 3.3 |
| Mageblood | 0.5 RoA | - | 72.1 | 146 | 377 | 559 | 630 | 387 | 230 | 641 (d18) | 3.2 |
| Mageblood | 0.5.5 FR | - | - | 400 | 530 | 535 | 303 | 170 | 110 | 579 (d11) | 0.28 |
| Headhunter | 0.2 DotH | - | - | 17.2 | 31.7 | 29.8 | 22.1 | 21.5 | 3.0 | 36.9 (d10) | 0.17 |
| Headhunter | 0.3 RotA | - | 32.7 | 39.3 | 59.2 | 62.7 | 34.6 | 15.1 | 5.6 | 68.5 (d8) | 0.17 |
| Headhunter | 0.4 FotV | - | 19.9 | 42.5 | 50.5 | 46.2 | 18.7 | 6.2 | 5.7 | 52.0 (d11) | 0.29 |
| Headhunter | 0.5 RoA | - | 97.1 | 202 | 335 | 370 | 234 | 111 | 60.0 | 381 (d10) | 0.62 |
| Headhunter | 0.5.5 FR | - | - | 259 | 292 | 154 | 31.6 | 10.4 | 11.2 | 292 (d7) | 0.04 |
| Voices | 0.5 RoA | - | - | 1,023* | 191 | 375 | 487 | 674 | 724 | 780 (d51) | - |
| Voices [corrupted] | 0.5.5 FR | - | - | 226 | 400 | 654 | 1,100 | 1,154 | 5,624 (see note) | - | - |
| Runeseeker's Call [Runemastered] | 0.5 RoA | - | - | - | - | 120 | 450 | 999 | 1,290 | 1,573 (d175) | - |
| Runeseeker's Call [Runemastered] | 0.5.5 FR | - | - | 250* | 496 | 907 | 1,096 | 1,408 | 1,530 | 1,839 (d34) | 6.1 |

**Notes on the chase table:**
- **Voices [corrupted], FR:** it was about 1,400 div on days 69-75. poe.ninja jumped to 5,624 on day 78. That is probably a different corrupted variant taking over the line, so treat the 5,624 as unconfirmed.
- **Runeseeker's Call (normal), FR:** poe.ninja flips between about 1,300 and 5,400-6,400 from day 36. Two variants share one line, so the high number is the top-roll price.
- **The Gnashing Sash, Redbeak and Bluetongue:** 1-8 listings at 500-7,500 div in 0.5+. Low confidence; the full rows are in the JSON.

### Endgame enablers (cheap early, climb late)
| Unique | League | d1 | d3 | d7 | d14 | d28 | d42 | end | peak (day) |
|---|---|---|---|---|---|---|---|---|---|
| Death Articulated | 0.2 | - | 8.5 | 0.96 | 3.1 | 6.9 | 19.1 | 19.0 | 83.5 (d87) |
| Death Articulated | 0.3 | 2.0* | 7.1 | 25.2 | 60.5 | 161 | 125 | 183 | 219 (d59) |
| Death Articulated | 0.4 | 14.5 | 1.1 | 0.88 | 1.0 | 4.5 | 34.8 | 279 | 279 (d164) |
| Death Articulated | 0.5 | 2.3 | 2.0 | 0.98 | 3.4 | 18.0 | - | 125 | 125 (d167) |
| Death Articulated | 0.5.5 | - | 4.0 | 30.0 | 11.0 | 25.0 | 29.0 | 45.5 | 45.5 (d78) |
| Grand Spectrum (Ruby) | 0.4 | 2.1 | 0.94 | 2.1 | 0.79 | 0.49 | 0.99 | 36.8 | 42.9 (d160) |
| Grand Spectrum (Ruby) | 0.5 | 1.6 | 0.34 | 0.53 | 0.74 | 0.35 | 0.70 | 20.0 | 24.5 (d168) |
| Grand Spectrum (Ruby) | 0.5.5 | - | 9.0 | 12.0 | 30.0 | 17.0 | 45.0 | 14.7 | 67.4 (d47) |
| Tabula Rasa [Runemastered] | 0.5.5 | - | 0.52 | 4.6 | 7.0 | 8.0 | 10.0 | 23.0 | 88 (d47, thin) |
| Morior Invictus [Runemastered] | 0.5.5 | - | 7.0* | 22.0 | 48.0* | 30.5 | 87.7 | 34.0 | 284 (d45, thin) |

### Build-enablers (spike in week 1, then crash unless they become the meta)
| Unique | League | d1 | d3 | d7 | d14 | d28 | d42 | end | peak (day) |
|---|---|---|---|---|---|---|---|---|---|
| Kalandra's Touch | 0.2 | - | 1.0* | 130 | 286 | 435 | 698 | 2.2 | 985 (d52) - meta |
| Kalandra's Touch | 0.4 | 3.9 | 5.6 | 7.5 | 6.3 | 0.17 | 0.10 | 0.69 | 7.9 (d11) |
| Kalandra's Touch | 0.5 | 7.3 | 18.0 | 25.7 | 20.5 | 20.5 | 10.8 | 9.9 | 33.5 (d21) |
| Kalandra's Touch | 0.5.5 | - | 30.0 | 36.0 | 18.6 | 2.2 | 1.0 | 1.8 | 40.0 (d8) |
| Rite of Passage | 0.2 | - | - | 78.8 | 157 | 477 | 635 | 3.9 | 1,036 (d50) - meta |
| Rite of Passage | 0.5 | 12.9 | 15.9 | 27.5 | 24.7 | 15.5 | 8.1 | 9.0 | 27.5 (d7) |
| Rite of Passage | 0.5.5 | - | 18.0 | 20.0 | 6.0 | 4.0 | 5.0 | 6.0 | 20.0 (d7) |
| The Taming | 0.5 | - | 45.2 | 18.8 | 3.7 | 4.3 | 4.3 | 8.0 | 45.2 (d4) |
| The Taming | 0.5.5 | - | 22.9 | 8.1 | 4.8 | 4.6 | 4.6 | 11.9 | 22.9 (d4) |
| Sacred Flame | 0.3 | - | 30.8 | 6.3 | 0.96 | 0.38 | 0.09 | 0.08 | 30.8 (d3) |
| Sacred Flame | 0.5 | - | 31.6 | 22.7 | 10.0 | 2.3 | 1.6 | 1.0 | 67.0 (d2) |
| Sacred Flame | 0.5.5 | - | 21.0 | 10.0 | 2.2 | 2.0 | 2.0 | 1.0 | 21.0 (d3) |
| The Ordained | 0.5.5 | - | 53.0 | 84.9 | 69.0 | 24.0 | 13.0 | 8.0 | 96.8 (d11) |
| Controlled Metamorphosis | 0.5 | 10.2* | 14.2 | 12.8 | 8.0 | 1.4 | 2.1 | 7.9 | 21.3 (d2) |

### Levelling uniques (sell on day 0-1)
| Unique | League | d0 | d1 | d3 | d7 | d14 | d28 |
|---|---|---|---|---|---|---|---|
| Goldrim | 0.3 / 0.5 | 0.28 / - | 0.09 / 0.15 | 0.07 / 0.09 | 0.05 / 0.05 | 0.02 / 0.03 | 0.02 / 0.01 |
| Bones of Ullr | 0.3 / 0.5 | 2.8 / - | 1.4 / 0.52 | 1.9 / 0.17 | 1.5 / 0.04 | 0.06 / 0.01 | 0.01 / 0.01 |
| Ab Aeterno | 0.4 / 0.5 | - | 0.34 / 3.1* | 0.01 / 0.08 | 0.01 / 0.01 | 0.00 / 0.01 | 0.00 / 0.00 |
| Leopold's Applause | 0.3 / 0.5 | - | 1.8 / 1.0 | 0.94 / 0.07 | 0.15 / 0.01 | 0.12 / 0.01 | 0.05 / 0.01 |

The group medians cover 24 levelling and early uniques:
- **Price on day 7 as a share of day 1:** 0.26 (0.2), 0.51 (0.3), 0.18 (0.4), 0.08 (0.5).
- **Price on day 28 as a share of day 1:** 0.02-0.10.
- **Peak on day 3 or earlier:** 67-92% of them.

---

## 4. Patterns (with confidence)

| # | Pattern | Evidence | Confidence |
|---|---|---|---|
| P1 | Single-source chase items (Temporalis, The Last Flame) start cheap and climb for 5-7 weeks. | Temporalis from day 3/4 to day 42: 0.4 x589; 0.5 x21; 0.5.5 x6.6. 0.2, from day 7: x2.9. 0.3 is the exception. Never more than about 60 listings. | high (4/5) |
| P2 | Temporalis ends each league at 0.8-2x The Last Flame (Last Flame is the key to Temporalis). | End prices: 411/332, 48/95, 21,433/11,380, 3,710/2,960, 6,198/5,620. | high (5/5) |
| P3 | Headhunter peaks on day 7-11, then loses 84-96%. | Peak days: d10, d8, d11, d10, d7. End price as a share of peak: 0.08, 0.08, 0.11, 0.16, 0.04. | high (5/5) |
| P4 | Repeatable-source chase (Mageblood) peaks on day 11-18, then falls 60-80% as listings flood in. | RoA: 72 → 641 (d18) → 230. FR: 400 → 579 (d11) → 110. Listings went from 20 to over 7,000. | high (2/2) |
| P5 | Late-endgame chase (Voices, Runeseeker's Call) first appears in week 1-2 at 200-350 div and climbs all league. | Voices corrupted FR: 226 → about 1,400. Runeseeker's Call Runemastered FR: 250 → 1,530. RoA Voices: 191 → 724. | medium (2 leagues, variant mixing) |
| P6 | Levelling uniques peak on day 0-1 and lose 70-98% within a week. | 24 items; group medians in section 3. | high (4/4) |
| P7 | Mid-tier build-enablers spike on day 2-7 and lose about 90% by day 28, unless a build takes off. | 23 items: day 7 is 26-40% of day 1, day 28 is 5-13%. Meta exceptions: 0.2 Kalandra's Touch (x985), 0.2 Rite of Passage (x13), 0.4 Olroth's Resolve (x67). | high for the crash, low for predicting the exceptions |
| P8 | Endgame build pieces bottom out in week 1-2 and climb late. | Death Articulated's low comes on days 4-9 at 0.3-1 div; it ends at 19-280. Grand Spectrum Ruby ends at 15-45. | medium |
| P9 | The first copies appear on day 0-3, on 1-20 listings. Those prices swing 2-10x within a day. | poe2scout first-seen data, every 12 h. FR: poe.ninja did not list Mageblood on day 3. | medium |
| P10 | The Divine scale depends on the league economy, so compare across leagues in Mirror terms. | Mirror on day 42: 1,110 / 1,421 / 6,527 / 5,227 / 5,397 div. Temporalis is about 0.4-1.7 Mirror in 0.5 and 0.5.5 after day 7. | high (data) |
| P11 | 0.4 temple Divine glut: scarce items went up 10-500x in Divine terms after week 2. | Temporalis: 53 → 25,803. The Last Flame: 69 → 23,089. Mirror: 344 → 6,527. A forum post says "400 div to 3 Mirrors in a week". | high |
| P12 | Ignore end-of-league prices on thin lines. | In the last month of 0.4, many cheap uniques printed at 10-500x (The Adorned 536, Sekhema's Resolve 149) on fewer than 10 listings. | medium |

### Supply: listings by day
| Item | League | d1 | d3 | d7 | d14 | d28 | d42 |
|---|---|---|---|---|---|---|---|
| Mageblood | 0.5 | 20 | 128 | 482 | 1,522 | 4,472 | 7,110 |
| Mageblood | 0.5.5 | - | 398 (d4) | 743 | 2,501 | 5,164 | 6,972 |
| Headhunter | 0.5 | 5 | 27 | 98 | 355 | 648 | 1,218 |
| Headhunter | 0.3 | 10 | 44 | 195 | 478 | 3,441 | 7,388 |
| Temporalis | 0.5 | 1 | 10 | 14 | 29 | 40 | 56 |
| Temporalis | 0.5.5 | - | 2 (d4) | 5 | 10 | 20 | 25 |
| The Last Flame | 0.5.5 | - | 7 (d4) | 14 | 25 | 18 | 11 |

### Relative to the Mirror (price ÷ Mirror price that day)
| Item | League | d3 | d7 | d14 | d28 | d42 | end |
|---|---|---|---|---|---|---|---|
| Temporalis | 0.4 | 0.18 | 0.15 | 0.88 | 2.14 | 3.95 | 2.64 |
| Temporalis | 0.5 | 0.36 | 0.45 | 0.57 | 0.85 | 0.87 | 0.65 |
| Temporalis | 0.5.5 | 1.10 | 0.88 | 1.64 | 1.35 | 1.68 | 1.13 |
| The Last Flame | 0.5.5 | 1.39 | 0.97 | 1.29 | 1.37 | 1.42 | 1.02 |
| Mageblood | 0.5 | 0.24 | 0.23 | 0.23 | 0.14 | 0.07 | 0.04 |
| Mageblood | 0.5.5 | 0.32 | 0.24 | 0.13 | 0.06 | 0.03 | 0.02 |
| Headhunter | 0.5 | 0.33 | 0.21 | 0.15 | 0.05 | 0.02 | 0.01 |

The Divine-to-Exalted rate and the Mirror price for every league day are in `unique-history.json` → `currency`.

---

## 5. Rules for the Oracle (1.0 launch, 2026-12-11)

1. **Day 0-2:** sell levelling and common build uniques at once. Don't buy chase uniques: they sit on 1-20 listings and can be 2-10x off.
2. **Headhunter:** sell on day 7-11. Never hold it.
3. **Mageblood-type chase items with a repeatable source:** sell into the day 10-18 peak.
4. **Temporalis and The Last Flame:** buy as early as you can afford and hold. They rise through day 30-50.
5. **Late-endgame enablers** (Death Articulated, Grand Spectrum, Runemastered Tabula Rasa and Morior Invictus): buy in week 1-2 and sell late.
6. **Judge with care:**
   - Judge chase prices in Mirror terms.
   - Ignore lines with under 3 listings, and lines in the last weeks of a league with under about 10.
7. **Build the 1.0 dataset:** store poe.ninja unique snapshots daily from day 0. The app already has `unique_daily`. Then the next report has day 0-3 data from poe.ninja too.

---

## 6. Method and limits

- **Sources:**
  - **poe.ninja economy only:** the stash item overview (documented) and the item price history behind each item's public chart (undocumented but economy-only), for RoA and FR. 18 overview and 189 history requests.
  - **52 Internet Archive copies** of poe.ninja PoE 2 unique overviews and histories (RoA days 1-37, FR days 2-20), found with the CDX API.
  - **poe2scout's public API** for 0.2-0.5.5: 445 item histories plus the daily Divine and Mirror rates.
  - **The app DB,** read-only.
  - **Politeness:** every request was at least 2.5 s apart (4-5 s for archive.org) and cached under `cache/`. No logins, no trade site, and no poe.ninja builds, character or profile endpoints.
- **Merging:** one value per day. poe.ninja history comes first, then the app DB, then archive copies, then poe2scout. Where poe.ninja and poe2scout overlap (RoA days 2-9), they usually agree within 5-25%.
- **Unit fixes:**
  - In the first days of a league, poe.ninja priced in Exalted Orbs.
  - FR days 0-3 in poe.ninja's history are a mix of Exalted and Divine. The unit was inferred against the day 4-6 price and tagged `N~`.
  - FR archive copies without a rate were converted with poe2scout's daily rate and tagged `A~`.
- **Glitch filter:** from day 7 on, a day more than 5x away from the median of the 3 days either side is dropped (for example, a 1.6-div poe2scout Mageblood point).
- **Roll-dependent items carry a floor price, not the real price:** Gnashing Sash, Morior Invictus, Prism of Belief, Voices variants and Runeseeker's Call variants. poe2scout keeps one line, and poe.ninja keeps a few.

**What we could not get:**
- **0.1 Early Access:** no aggregator kept unique prices; poe2scout's Standard history is empty. Only anecdotes exist, such as "Headhunter 2-3 div".
- **FR days 0-3 for most uniques:** poe.ninja hadn't indexed them yet, and poe2scout starts on day 8.
- **RoA days 15-56:** only poe2scout and a few archive copies, because poe.ninja's history only goes back about 120 days.
- **No confirmed first sales, only listings.** No Reddit "first Mageblood" thread was found; reddit.com was blocked to the search tool.

**Reproduce:**
1. `scripts/fetch_ninja.py overview`, then `scripts/fetch_ninja.py history`.
2. `scripts/fetch_wayback.py`.
3. `scripts/fetch_scout.py`.
4. `scripts/build.py`.
5. `scripts/report.py`.
6. `scripts/tables.py table <names>` prints any table.
