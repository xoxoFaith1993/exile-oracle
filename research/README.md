# The research behind Exile Oracle

Everything the Oracle says comes from the research in this folder. Each topic has:

- a **report** (`.md`) written for people;
- the **data** (`.json`) the app reads, in a cleaned copy under `datapack/`;
- the **scripts** that fetched and measured it, so anyone can check it or run it again (for example on 1.0).

Every finding is tagged with how sure it is (high / medium / low) and where it came from. The tags mark the difference
between measured data (GGG's public Currency Exchange history, the game files) and community claims (guides, videos),
which are labelled and checked against the data.

| Topic | Report | What it found | Used by |
|---|---|---|---|
| Market trends | [market/market-trends.md](market/market-trends.md) | How every exchange item moves from day 1 to week 10 over three launches: what spikes, what crashes, when to sell | Oracle advice, Economy, Home |
| League start, hour by hour | [league-start/league-start-deep.md](league-start/league-start-deep.md) | The first 72 hours: sell windows, early buys, fast fallers, a 72-hour plan, community tips checked against the data | Prophecy timeline and omen, countdowns |
| Price forecast | [forecast/forecast-model.md](forecast/forecast-model.md) | A forecast for 688 items tested on six launches (its ranges hold 79% of the time) | Prophecy forecast fans, `poe2_oracle` |
| Patch impact | [patch-impact/patch-impact.md](patch-impact/patch-impact.md) | 276 PoE 2 patches matched to the price moves after them, and a rulebook (`rules.py`) | Patch prophecy |
| Farming returns | [farming/farming-returns.md](farming/farming-returns.md) | Divines per hour for 22 strategies by league phase, with build requirements | Farming oracle, Atlas strategies |
| Chase uniques | [uniques/unique-history.md](uniques/unique-history.md) | Mageblood, Headhunter, Temporalis and 45 more, by league day over five leagues | Prophecy: chase uniques |
| PoE 1 history | [poe1-history/poe1-history.md](poe1-history/poe1-history.md) | 20+ PoE 1 leagues as labelled analogy: league-economy patterns, checked against PoE 2 | Oracle notes |
| Atlas | [atlas/atlas.md](atlas/atlas.md) | The atlas tree from the game files, 11 strategies with key nodes, waystone mod danger and reward, rolling, tablets | Atlas, Maps and Tablets pages, waystone check |
| Campaign | [campaign/campaign.md](campaign/campaign.md) | The rush route, every permanent reward, trials, breakpoints, times | Campaign page, route panel |
| Bosses | [bosses/boss-readiness.md](bosses/boss-readiness.md) | What each pinnacle boss needs (life, resistances, damage) | Build Lab boss readiness |
| Drop rates | [drop-rates.md](drop-rates.md) | What the public web knows about PoE 2 drop rates | Farming page |

**What's left out:** downloaded raw pages and API dumps (`cache/` folders). They are large, and they are other people's
content; the scripts fetch them again.

History, not a promise: patches move prices, and 1.0 (2026-12-11) will change a lot. The scripts are there so the
research can be re-run on 1.0 data.
