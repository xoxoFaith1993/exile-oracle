# Exile Oracle

A Path of Exile 2 companion that measures your build, reads the market and past leagues, and tells you what to do
next. It runs on your own PC, in its own window:

- **League plan:** your league in six stages with "ready to move on" checks measured on your build, and **Stuck?**
  for when you keep dying, can't make currency or want to start over;
- **your build:** the Build Lab (every idea measured by Path of Building before you buy), Character, Compare, Top 1%;
- **the market:** live prices, exchange gaps, a wishlist with target prices, and wanted items you can check on the
  trade site;
- **the Oracle:** a daily omen, price forecasts, patch prophecy and a league timeline;
- **the campaign:** a rush guide and a route panel in game;
- **endgame:** atlas strategies drawn on your tree, waystone rolling and map mods rated for your build, tablets;
- **a price-check overlay** (Ctrl+D) that also rates waystones.

Also in it: what to farm, your play sessions, a craft lab, patch notes checked against your builds, and alerts you
choose. If something goes wrong it says so in plain words and keeps working, and a daily backup keeps your builds safe.

## Install
1. Run `ExileOracle-Setup.exe`. Windows may say "Windows protected your PC" because the installer isn't signed:
   click **More info**, then **Run anyway**.
2. It installs for your Windows user only (no admin needed) and starts. A red icon appears by the clock: click it to
   open the dashboard, right-click for **Start with Windows** and **Quit**.
3. The first start downloads prices, the community game data and Path of Building (about 2 minutes, around 600 MB in
   `%LOCALAPPDATA%\PoE2Toolkit`).

## First steps
- **Settings → Your profile:** pick your class, ascendancy and how well you know the game, and save. That sets the
  defaults everywhere and how much the Oracle explains.
- **Your characters:** install *Path of Building Community (PoE 2)* and sign in to your GGG account there once. The
  Builds tab can then import your characters (only when you press the button).
- **Sessions:** start the game once; the toolkit reads the game's own log file to track maps, map time and deaths.
- **Several characters?** Pick the one you're playing in **Playing** at the top. Every page follows it.
- **Overlay:** Settings → Price-check overlay. Ctrl+D on an item (or a waystone) in game; the keys can be changed there.
- **Campaign:** the route panel shows in a corner while you level (Ctrl+Alt+R hides it); tick rewards on the Campaign
  page.

## Best with Claude
This toolkit is meant to be used **with Claude**: the dashboard shows the numbers, Claude answers your questions
about them ("what should I farm", "how close am I to the top 1%", "how do I craft this"). Connect it once from the
**Settings** → **Connect to Claude**, then restart Claude. Full guide: `CLAUDE-GUIDE.md` in the install folder
(also in the Start menu: *Using Exile Oracle with Claude*). Everything still works without Claude.

## It keeps itself current
After a game patch, what it knows about the game updates by itself within hours (Settings → Game data). App updates
show a banner: one click installs them, and your settings and builds are kept.

## The rules it follows (so your account stays safe)
- Read-only: it never sends input to the game, never reads game memory, never changes game files.
- Only public data: poe.ninja's economy data, GGG's public Currency Exchange history, Steam news, and the game's own
  log file on your PC. Your GGG login stays inside Path of Building.
- Polite polling: prices every 30 minutes, exchange history hourly.
- Nothing about you leaves your PC.

## Not affiliated
This product isn't affiliated with or endorsed by Grinding Gear Games in any way.
