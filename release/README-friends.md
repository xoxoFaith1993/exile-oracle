# Exile Oracle

A personal Path of Exile 2 companion: live economy, what to farm, a league-start playbook, a Top 1% check for your
character, your play sessions, a craft lab and patch notes checked against your builds. It runs on your own PC and
opens in your browser.

## Install
1. Run `PoE2Toolkit-Setup.exe`. Windows may say "Windows protected your PC" because the installer isn't signed:
   click **More info**, then **Run anyway**.
2. It installs for your Windows user only (no admin needed) and starts. A red icon appears by the clock: click it to
   open the dashboard, right-click for **Start with Windows** and **Quit**.
3. The first start downloads prices, the community game data and Path of Building (about 2 minutes, around 600 MB in
   `%LOCALAPPDATA%\PoE2Toolkit`).

## First steps
- **Status tab → Your profile:** pick your class and ascendancy and save. That sets the defaults everywhere.
- **Your characters:** install *Path of Building Community (PoE 2)* and sign in to your GGG account there once. The
  Builds tab can then import your characters (only when you press the button).
- **Sessions:** start the game once; the toolkit reads the game's own log file to track maps, map time and deaths.

## Best with Claude
This toolkit is meant to be used **with Claude**: the dashboard shows the numbers, Claude answers your questions
about them ("what should I farm", "how close am I to the top 1%", "how do I craft this"). Connect it once from the
**Status** tab → **Connect to Claude**, then restart Claude. Full guide: `CLAUDE-GUIDE.md` in the install folder
(also in the Start menu: *Using Exile Oracle with Claude*). Everything still works without Claude.

## The rules it follows (so your account stays safe)
- Read-only: it never sends input to the game, never reads game memory, never changes game files.
- Only public data: poe.ninja's economy data, GGG's public Currency Exchange history, Steam news, and the game's own
  log file on your PC. Your GGG login stays inside Path of Building.
- Polite polling: prices every 30 minutes, exchange history hourly.
- Nothing about you leaves your PC.

## Not affiliated
This product isn't affiliated with or endorsed by Grinding Gear Games in any way.
