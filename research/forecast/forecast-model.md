# Price forecast model: PoE 2 (six launches, for PLAN R14)

Built 2026-11-21. Machine-readable model: `forecast-model.json`. Code: `forecast.py` (the same code ships in the app as
`poe2kit/forecast.py`), and `scripts/` rebuilds everything from scratch.

## What it answers

"It is league day D and this item costs P Divines (and moved X% over the last 7 days): where will it be in 1, 3, 7 and
14 days?" The answer is a median plus a range: the 25-75% band (half the time) and the 10-90% band (8 times in 10).

## Data

- GGG's public Currency Exchange history (hourly digests), one price per day per item (the 21:00 UTC hour; volume-weighted
  pair ratios; only hours where the item really traded).
- **Six launches:** EA 0.1 (128 items, 118 days), Dawn of the Hunt (232, 140), Rise of the Abyssal (410, 100), Fate of the
  Vaal (436, 140), Runes of Aldur (657, 98) and Forbidden Rites (663, 78 so far).
- Hardcore and legacy (Standard) markets were used only as checks, not for fitting.
- The result: 688 items in 15 categories.

## The model, in plain words

For each horizon h (all in log price):

1. **Typical drift:** how the same item moved over the same h days at the same point of past launches (the median across
   launches). Items with few launches are pulled toward their category's path.
2. **Momentum / reversion:** how much of the last week's *unusual* move carries on or gives back. It is fitted per
   liquidity tier and league phase. Markets mostly revert: the day-to-day autocorrelation is about -0.4.
3. **Spread:** the item's usual size of surprise, times empirical quantiles of past surprises for that horizon and phase.
   After a patch hits the item, the spread is widened 1.8x (measured).

## Honest backtest

Leave-one-launch-out: each launch is predicted by a model fitted on the other five. That gives 212,456 one-day cases.

| Horizon | Range held (target 80%) | Typical error: model / "no change" | Direction right when it calls a 10%+ move |
|---|---|---|---|
| 1 day | 79% | 31% / 29% | 63% |
| 3 days | 79% | 43% / 41% | 62% |
| 7 days | 79% | 58% / 58% | 61% |
| 14 days | 79% | 82% / 81% | 60% |

**What this means:**

- **The ranges are the trustworthy part.** They hold about as often as they claim, in every phase, every liquidity tier
  and every launch.
- **The middle guess is only a little better than assuming no change across a whole league.** The exception is launch
  week, when it is much better: over 7 days, the typical error is 80% vs 112% for days 0-2 and 66% vs 86% for days 3-6,
  and the direction calls are right 70-74% of the time.
- **Liquid items are far more predictable:** a 12% typical one-day error for liquid items vs 63% for thin ones.

## Other findings

- **Spikes give back:** after a sudden jump, the median item returns 42% of it within 7 days. 46% of spikes are at least
  half reversed, and only 29% keep climbing.
- **Trends rarely continue:** a 7-day move continues in the next 7 days only 45% of the time (57% in days 7-20).
- **Shock days:** the days when many items jumped and stayed are listed in `forecast-model.json` (research.shock_days).
  Most are hotfix and patch days.

## Finishing touches in the app (2026-11-21)

- **One consistent path.** Each horizon (+1, +3, +7, +14 days) was forecast on its own, so the middle line could jump up
  then down (82.7% of item-days in the backtest zig-zagged). The app now fits one path that moves one way or stays flat
  from today's price, and bands that only widen further out (`poe2kit/forecast.smooth`). On the same leave-one-launch-out
  backtest (`scripts/smooth_check.py`) it is slightly better on every measure: median error 46.5% -> 45.8%, the 10-90%
  band held 79.9% -> 80.3%, direction right on 10%+ calls 61.3% -> 62.1%, zig-zags 0%.
- **Past-launch lines for every item.** `scripts/paths.py` writes the daily price of all 681 exchange items in the last
  three launches to `datapack/forecast-paths.json` for the chart's faint lines (before, only the 42 key items had them).
  Its prices come from `build_dataset.py <dir> value`: each item priced from the market (Ex / Div / Chaos) with the
  most VALUE traded, the app's corrected method (17.8% median error vs poe.ninja instead of 36.6% for "Exalted first").
  (On these daily samples the two methods barely differ.) The model itself is still the one trained on the original
  dataset.

## Limits

- It is history, not a promise. Patches override it, and 1.0 (2026-12-11) adds new items with no history: those use
  their category's path.
- Prices are in Divine Orbs, so the Divine itself cannot be forecast (it is always 1).
