# Exile Oracle: licences and credits

**Exile Oracle** is a personal, free tool shared between friends. Use at your own risk; no warranty.
It isn't affiliated with or endorsed by Grinding Gear Games. Path of Exile, its names and all of its artwork are
© Grinding Gear Games. This free, non-commercial fan tool uses one piece of game art (the Blood Mage "Sanguimancy"
ascendancy art) as its icon; it will be replaced on request (an original icon is ready in `release\icon.png`).
The installer also bundles item, skill and passive-tree pictures taken from the game files (`toolkit\gameart`), so
the tool looks right without extra downloads; they are © Grinding Gear Games, shipped for this free, non-commercial
fan tool, and will be removed on request. Other item pictures load from GGG's own image servers through poe.ninja.

## Included
- **Python 3.15** (embedded distribution), Python Software Foundation License: https://docs.python.org/3/license.html
- **poblua.exe**: a small launcher that runs Path of Building's Lua runtime headless (source: `toolkit\pobhost\poblua.c`).

Linux download only, built by GitHub Actions:
- **Python 3.15** from python-build-standalone (Astral), Python Software Foundation License and the licences of
  its bundled libraries: https://github.com/astral-sh/python-build-standalone
- **LuaJIT 2.1**: MIT License, https://luajit.org
- **luautf8**: MIT License, https://github.com/starwing/luautf8
- **Lua-cURLv3**: MIT License, https://github.com/Lua-cURL/Lua-cURLv3 (uses the system's libcurl)

## Downloaded on first run (not bundled)
- **Path of Building Community (PoE 2)**: MIT License, https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2
  (its `LICENSE.md` is downloaded with it).
- **RePoE (PoE 2 fork)** game-data export: https://repoe-fork.github.io/poe2
- Market data: poe.ninja (https://poe.ninja), GGG's public Currency Exchange API, Steam News API.

## Data pack
`toolkit\datapack\` holds small facts derived from game data (zone list, essence and currency descriptions, campaign
rewards) and research summaries (Top 1% benchmarks from public poe.ninja pages, league-start price history from
GGG's public exchange API, community drop-rate estimates with their sources in `toolkit\research\drop-rates.md`).

By installing you agree to use it under these terms.
