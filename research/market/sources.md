# Sources for market-trends.md / market-trends.json (all accessed 2026-11-21)

**Seller sites.** Sites marked [seller] sell currency or boosting. Their numbers are low trust and are used only to
cross-check GGG data.

**How each page was read:**
- (fetched): someone read the page itself, either the research sub-agent or this pass.
- (snippet): only the search-result snippet was seen, not the page.

## Primary data
| # | Source | Note |
|---|---|---|
| S1 | GGG Currency Exchange history: `https://web.poecdn.com/api/currency-exchange/poe2/<hour>` | GGG's public hourly digests (no login). The app already syncs these. For this report, 20 hours were fetched at 2.5 s spacing: noon on days 10, 14, 21, 28, 42, 56 and 70 of Fate of the Vaal and Runes of Aldur, and days 10-56 of Forbidden Rites. Prices come from volume-weighted pair ratios, the same method as `poe2kit/leaguestart.py`. Scripts are in `scripts/`. |
| S2 | Exile Oracle DB `<data folder>\data\poe2kit.db`, opened read-only | `ls_price` holds days 0-6 of the three launches. `ex_price` and `exchange_hour` hold Forbidden Rites days 63-77 (the app's own sync from 2026-11-06). `patch_notes` holds the 0.5.0-0.5.4b texts. |
| S3 | `datapack/playbook.json` | The existing day 1-7 playbook: sell_day1 and hold lists, and the div_rate per day. This report extends it to week 10 and does not repeat it. |
| S4 | GGG patch notes 0.5.0, 0.5.2, 0.5.3, 0.5.4, 0.5.4b (official Steam announcements, https://store.steampowered.com/news/app/2694490, as stored in the app DB) | The 0.5.3 Vessel of Kulemak Ancient-bone drops. The 0.5.0 changes: Recombinator removed, Chaotic omens inverted, catalysts only from the Genesis Tree, Fracturing needs atlas specialisation. |

## Web (news, guides, forums)
| # | Title | URL | Note |
|---|---|---|---|
| S5 | Gamepressure: PoE 2 players complain about the death of the new season (Dec 29 2025) | https://www.gamepressure.com/newsroom/poe-2-players-complain-about-the-death-of-the-new-season-all-beca/z78b67 | 0.4 temple farming. Gear went 70-90 Div → ~200 Div in a day. Temples gave ~10-15 Div each. (fetched) |
| S6 | PCGamesN: temple diminishing-returns patch notes | https://www.pcgamesn.com/path-of-exile-2/patch-notes-temple-diminishing-returns | Jan 3 2026 nerf, runs went from "hundreds of Div" to ~20, no rollback. The hotfix label is reported as 0.3.0c, but is probably 0.4.0c. (fetched) |
| S7 | PoE forum: "800 Divines for Gear? This Economy Is Completely Out of Control" | https://www.pathofexile.com/forum/view-thread/3900276 | 0.4: Mirror ~4,000 Div, gear 200-800 Div (Dec 29 2025). (fetched) |
| S8 | Switchblade Gaming: PoE 2 economy guide | https://www.switchbladegaming.com/path-of-exile-2/economy-guide-4/ | Timing heuristics, e.g. don't buy uniques in the first 72 h. Its Chaos numbers contradict every other source; low trust. (fetched) |
| S9 | outof.games: PoE 2 economy tracker, Omen of Light | https://outof.games/realms/poe2/economy/omens/omen-of-light/ | 7-day change snapshots, e.g. Omen of Light -59% in a week (RoA, July 2026). (fetched) |
| S10 | timesaver.gg: Divine/Exalted value end of league, 740 to 1 [seller] | https://timesaver.gg/blog/poe2-divine-exalted-value-end-of-league-740-to-1 | FR Oct 5: ~740 Ex per Div, 10.8 Chaos per Div, Mirror 5,316 Div. (fetched) |
| S11 | timesaver.gg: Divine:Exalted rate, Forbidden Rites 0.5.5 [seller] | https://timesaver.gg/blog/poe2-divine-exalted-exchange-rate-forbidden-rites-0-5-5 | FR Sep 5: ~65 Ex per Div, ~20 Chaos per Div. (fetched) |
| S12 | PCGamesN: Return of the Ancients makes Divine Orbs more common | https://www.pcgamesn.com/path-of-exile-2/return-of-the-ancients-divine-orbs | The 0.5 Divine drop buff (no number given) and a targeted temple nerf. (fetched) |
| S13 | iGGM: Patch 0.4.0d will bring economy changes [seller] | https://www.iggm.com/news/poe-2-patch-0-4-0d-will-bring-economy-changes | Immured Fury / Fracturing fix, Atziri fix. (fetched) |
| S14 | vortexgaming: Fubgun's 0.5 league-start plan | https://vortexgaming.io/en/postdetail/985241 | Secondhand summary: rush the atlas, sell tradeables at once. (fetched) |
| S15 | kami-labs: league-start tier list, 0.5.5 | https://kami-labs.fr/en/path-of-exile-2/tier-list-league-start-poe2-0-5-5/ | Fubgun's criterion: builds that clear pinnacles for 10 Div or less. (fetched) |
| S16 | PCGamer: director says exploiters "ruined Christmas" | https://pcgamer.com/games/rpg/path-of-exile-2-director-says-players-exploiting-system-to-become-in-game-millionaires-ruined-christmas-for-me-and-joked-that-hes-lost-all-sympathy-for-everyone-who-took-advantage-of-it/ | GGG's stance on the temple boom. (fetched / snippet) |
| S17 | RPG Site: PoE 2 1.0 full release on December 11 | https://www.rpgsite.net/news/21188-path-exile-2-reaches-its-10-full-release-on-december-11 | 1.0 date. Pushsquare and Game Informer report the same. (fetched) |
| S18 | Maxroll: Flipping with the Currency Exchange | https://maxroll.gg/poe2/resources/flipping-with-the-currency-exchange | Exchange mechanics and worked flip margins (0.2 era). (fetched) |
| S19 | iGGM: PoE 2 1.0, curb inflation [seller] | https://www.iggm.com/news/poe-2-1-0-curb-inflation-keep-new-players-around | 0.3: Div:Ex ~55 → ~280 in 2 weeks, then ~650. (fetched) |
| S20 | MMOGah: PoE currency price history [seller] | https://www.mmogah.com/news/poe/poe-currency-price-history | PoE 1 3.23-3.29 RMT decay, and 50% / 77% of orders in the first 2 / 4 weeks. (snippet only, the page returned 403) |
| S21 | PCGamesN: 0.2.0g patch notes | https://www.pcgamesn.com/path-of-exile-2/update-020g-patch-notes | The 0.2 loot buff numbers. (fetched) |
| S22 | Sportskeeda: Breach getting nerfed in Dawn of the Hunt | https://sportskeeda.com/mmo/breach-getting-nerfed-path-exile-2-dawn-the-hunt-ggg-confirms | Breach nerfed at the 0.2 launch. (snippet) |
| S23 | Gamepressure: Ritual exploit fixed (0.2.0d) | https://www.gamepressure.com/newsroom/ritual-exploit-in-poe2-is-fixed-now-according-to-patch-notes-deve/z17cb5 | Unlimited-reroll tablet capped. Abusers banned and their items removed. (fetched) |
| S24 | PoE forum thread 3669686, page 2 | https://www.pathofexile.com/forum/view-thread/3669686/page/2 | 0.1: "1 Div = 99 ex" (Dec 28 2024). (fetched) |

## Looked at but not used for claims
- **poe.ninja API docs** (https://poe.ninja/docs/api) and the poe.ninja PoE 2 economy blog posts returned 403.
  No poe.ninja unique-price history for past leagues was available.
- **Other seller pages** (aoeah Mageblood, timesaver "most expensive items", mmoexp, wowcarry) only appear as
  cross-checks in the unique-items paragraph, marked as low confidence.
- **Reddit** was not opened (rule). The poe-vault Ritual article quoting Reddit was seen but not relied on.
