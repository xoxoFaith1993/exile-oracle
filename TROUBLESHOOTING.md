# Exile Oracle: troubleshooting (written for Claude)

You are helping a player whose Exile Oracle isn't working. This project is at an early stage: assume bugs are
possible and check before you guess. **Start with the `poe2_doctor` tool**: it runs every check below and names the
sections of this guide that apply. Then follow those sections. Tell the player what you found in plain words.

**Ground rules while fixing:**
- Read-only toward the game. Never read its memory or change its files.
- The only keys the toolkit ever sends are Ctrl+Alt+C, when the player presses an overlay hotkey, and the chat
  command keys they set up.
- Never touch files in the game's `BuildPlanner` folder unless their name starts with `Exile Oracle - `.
- Live trade-site prices stay within GGG's rate limits: one search per check, never retry in a loop.
- Don't put the player's account name, email or character names into anything you post or send anywhere.

## How it fits together

| Part | What it is | Where |
|---|---|---|
| Monitor | `monitor.py`: background jobs (prices every 30 min, exchange hourly, game log every minute, ...) and the dashboard at http://127.0.0.1:47830 | started by the tray app (Windows), `launcher.py` (Linux) or `start-monitor.bat` |
| Overlay | `overlay.pyw` (Windows only): hotkeys, clipboard, the popup (a borderless Edge window showing `/overlay`) | started by the monitor when the setting `overlay` is on |
| Claude tools | `server.py` (MCP), reads the toolkit's database | registered in Claude Desktop / Claude Code |
| Data folder (HOME) | settings, database, logs, Path of Building | Windows: `%LOCALAPPDATA%\PoE2Toolkit`; Linux: `~/.local/share/poe2toolkit`; developer copy: `F:\PoE2Toolkit`; `POE2KIT_HOME` overrides |

Files in HOME:
- `logs\monitor.log` and `logs\overlay.log`: read their last lines first.
- `settings.json`, `data\poe2kit.db`.
- `monitor.lock` and `overlay.lock` hold the running process ids.
- `overlay.quit`: creating this file makes the overlay close itself.

## Restarting things (safe at any time)

- **Monitor:**
  1. Stop the process whose id is in `HOME\monitor.lock` and delete the lock.
  2. Start it again. Windows: the tray icon (Quit, then start Exile Oracle from the Start menu), or run
     `start-monitor.bat`. Linux: `python launcher.py --stop`, then `python launcher.py`.
  3. Check that http://127.0.0.1:47830/api/status answers.
- **Overlay:** create the empty file `HOME\overlay.quit`. The overlay closes within a second. Then switch it back on:
  dashboard Settings → Price-check overlay → Overlay on (or POST `{"overlay": true}` to `/api/overlay/options`).
  After a monitor restart it starts by itself when the setting is on.
- **A popup window that's stuck on screen:** see "Overlay" below.

## Dashboard

- **Won't open / "can't reach 127.0.0.1:47830":** the monitor isn't running. Restart it. If it dies at once, read
  `monitor.log`. If port 47830 is taken by another program, set the environment variable `POE2KIT_PORT`.
- **"⏳ Still setting up" banner:** a first start downloads game data and Path of Building, which takes a few
  minutes. If it stays longer than 10 minutes, `monitor.log` shows the failing download (usually network).
- **Prices empty or old:** the `prices` job runs every 30 minutes. Settings shows each job's last result.

## Overlay (Windows)

Keys work only while Path of Exile 2 is the window in front (all of them can be changed in the overlay settings or
Settings → Price-check overlay; saved as `price_keys` in settings.json):
- Ctrl+D quick check (on a waystone or tablet it also rates every mod for the active character);
- Ctrl+Alt+D detailed;
- Ctrl+Shift+D settings;
- Ctrl+Alt+R shows / hides the campaign route panel;
- F5 / F9 and others: chat commands.

| Problem | Check | Fix |
|---|---|---|
| Nothing happens on Ctrl+D | `poe2_doctor` overlay section; is the game in front and in **windowed fullscreen**? | Turn the overlay on. Use windowed fullscreen: true fullscreen draws over every other window. Another program may hold Ctrl+D (the doctor checks). |
| Popup appears but shows "Reading item…" forever | is the monitor running? `monitor.log` errors | restart the monitor |
| Popup stuck on screen, Esc does nothing | `overlay.log` ("reappeared by itself") | click anywhere in the game, or restart the overlay (`overlay.quit`). Fixed in 0.3.1+ (the overlay re-hides strays and holds Esc while open). |
| Command windows flash | old version | fixed in 0.3.1+ (no console windows) |
| Popup shows a browser title bar, or a grey strip at the top | Edge updated or scaling changed | restart the overlay; the window is measured again |
| Popup shows an old layout after an update | the page is kept between restarts | it reloads itself when its file changes (0.3.1+); else restart the overlay |
| Text too small/large in the popup | page zoom | zoom is blocked; delete the `127.0.0.1` entry under `per_host_zoom_levels` in `HOME\edge-overlay\Default\Preferences` while the overlay is off |
| A key does nothing after changing it | the settings show "taken by another program" (`HOME\overlay_keys.json`) | pick another key or close the program holding it; Ctrl+C / Ctrl+Alt+C are refused (the overlay presses them itself) |
| Waystone check says "could not rate for your build" | is there an own build in the vault? `poe2_status` active_character | import or save a build, pick it in **Playing**; the check needs Path of Building to run once |
| Route panel never shows | Campaign page → "Route panel in game" ticked? `/api/route/state` shows the zone? | it shows only in campaign zones and towns while the game is in front (hidden in hideout and maps, or after Ctrl+Alt+R). The zone comes from Client.txt: check `poe2_doctor` finds it |
| Route panel shows the wrong zone or act | `/api/route/state` | it follows the last "Generating level" line in Client.txt; new 1.0 zones need the refreshed `worldareas.json` (data pack update) |
| No picture for an item | — | uses the game art from the toolkit when the trade site has none; magic items find their base inside the name |

## Prices

- **Wanted items (Wishlist page) say "Trade-site checks are off":** the same `live_trade` switch as the overlay's
  live prices. The button on the card switches it on. "Wait a minute between checks": the same wanted item can be
  checked once a minute. "Trade site limit reached": GGG's limit for everyone on this PC; wait and press again.
  "That link's search can't be read": older short search ids aren't the search itself; paste the item text instead.
- **Live trade prices say "off":** the setting `live_trade` is off. It's off by default for everyone:
  it uses GGG's trade site the way Exiled Exchange 2 does, which is not a documented public API, so it's the
  player's choice. Ctrl+Shift+D → Live trade-site prices.
- **"Trade site limit reached: try again in N s":** GGG's rate limit. Wait; don't retry in a loop.
- **"Matched: 0":** the search is too strict. Untick a stat or lower a minimum, then Search. On white and magic bases
  the item level is matched too.
- **A price looks absurd:**
  - fewer than 20 listings is a thin market, so the toolkit shows the lowest price, not the middle;
  - check the currency icon (Exalted vs Divine; 1 div ≈ several hundred ex);
  - uniques whose price depends on their roll are flagged, and poe.ninja's price for them is the cheapest roll.
- **A unique has no poe.ninja price:** poe.ninja only lists items that trade often enough.

## Ask the Oracle (the popup's button; called "Ask Claude" before 0.4.0)

- **Target "Claude app":** the button saves the item and opens Claude desktop. The player pastes the copied
  question, and you read the item with `poe2_from_overlay`. If that tool is missing, Claude desktop needs a restart
  after Connect to Claude (Settings).
- **Target "Claude Code chat":** the player says "watch my overlay". You then run
  `python -u <toolkit>/cli.py watch-overlay 55` **in the background**. When it finishes it prints the item: answer
  in the chat and start it again. If items arrive but you're never woken, the watcher has hung: stop it and start a
  new one with `-u`.

## In-game Build Planner

GGG documents the `.build` format at https://www.pathofexile.com/developer/docs/game. The game reloads changed files
by itself.

| Problem | Check | Fix |
|---|---|---|
| Plan not in the game's list | does `Documents/My Games/Path of Exile 2/BuildPlanner` exist (Steam Deck: inside the Proton prefix)? | start the game once; send the build again |
| No levelling order, the whole endgame path shows at once | `poe2_build_planner` plan `levelling_route` | normal: the automatic order is a rule of thumb, so it only goes into the game after Claude reviews it. Use `poe2_levelling` mode `route` (and `gems` / `rank_skills` / `rank_supports` for early skills), then `poe2_build_planner levelling_route=true` |
| Plan listed but nothing drawn on the tree | passives have level ranges | a planned passive shows 10 levels before it's due ("Take at level N"), so at level 1 only the first ~12 show |
| Not updating as you level | `poe2_build_planner` `plan.follow` = the character's exact name? the game log is found? | switch on following with the exact character name. Updates come within about a minute of a level-up; reopen the passive tree. |
| Gear hints show endgame items at low level | — | fixed: levelling plans show "look for" hints until 55 and the endgame item after |
| Nodes say "Requirements not met" | — | normal: take the earlier nodes on the path first |
| Quest point timing off | — | the route assumes each point quest is done at its area level; a skipped quest delays the nodes after it |
| Weapon Set notes | — | quest points are Weapon Set points in PoE 2: damage nodes are marked for Weapon Set I; life/defence stay on normal points |

## Path of Building

- **Character pages, the Top 1% check or classes don't load:** Path of Building isn't ready. The doctor checks
  `HOME\pob\manifest.xml` and the runner. Windows: `HOME\tools\poblua.exe`. Linux: `linux/bin/luajit`.
- **Character import says "not signed in":** the player signs in once inside Path of Building (Import/Export →
  Authorize). The toolkit never handles their login.
- **Linux:** PoB's own Lua is replaced by the bundled LuaJIT, pinned to the commit PoB's tests use. Newer LuaJIT
  rejects PoB's `#@` first lines.

## Linux / Steam Deck

- Install with `sh install.sh` (no sudo). The app is in `~/.local/share/poe2toolkit/app`, data next to it.
- The overlay is Windows-only for now.
- Game log not found: the doctor shows the folder it looked in. Steam, Flatpak Steam and SD-card libraries are
  searched; the game folder can also be set in Settings. The in-game Build Planner folder is found in the game's Proton prefix in any of those libraries.

## Damage looks far too low
| Problem | Check | Fix |
|---|---|---|
| A build's DPS is much lower than in game | Character page → **Build check**: weapon set, main skill | weapons only in set II are fixed automatically; otherwise pick the right weapon set / main skill there (saved with the build; "Reset to as imported" undoes it) |
| Gem level lower than in game | the skill's level in game includes "+ levels" from gear | the gem shows its own level; gear levels are counted in the DPS |

## Build Vault: paste / delete
| Problem | Check | Fix |
|---|---|---|
| "isn't a Path of Building code" | the paste is one long line from PoB (Import/Export → Generate → Copy) | copy it again; links work for pobb.in, pastebin and poe.ninja only |
| A poe.ninja link only opened a window | that's by design (no poe.ninja builds API) | press "Save this build to my vault" in that window |
| Deleted the wrong build | it's gone from the vault (its Build Lab cards too) | paste its code again; the in-game Build Planner file is untouched |

## Alerts and question chips
| Problem | Check | Fix |
|---|---|---|
| Too many / too few alerts | Alerts page → "What to alert me about" (settings.json `alerts`) | switch kinds off, raise the thresholds, mute an item, or set market moves to the daily digest |
| An expected alert never came | that kind is on? the item muted? market moves need volume / listings and must hold 2+ hours | lower the thresholds; "My items" covers only items in your own builds and watch list |
| A question chip doesn't open Claude | Settings → Question chips; is the Claude desktop app installed? | it is copied as well: paste it; or pick "only copies it". Claude's caution note on link prompts is normal |

## Game data updates (R27)
The app checks our GitHub for a newer **data pack** every 6 hours (Settings → Game data: version, last check, Check
now, Go back). Packs are data only (JSON), never code.

| Problem | Check | Fix |
|---|---|---|
| Something looks wrong right after a data update | Settings → Game data shows `downloaded update` | **Go back to the previous data** (or `/api/data/rollback`), then report it |
| "needs app X: update the app first" | the pack needs a newer app | install the app update from the banner |
| "could not check" | internet / GitHub reachable? | it tries again in 6 hours; Check now to retry |
| Pack refused: "does not match the manifest" | the download was damaged or changed | nothing to do: the old data stays in use; it retries later |
| 1.0 is out but the app still shows the old league | Settings → League: "automatic"? | automatic follows the newest league within the hour around a launch; a league picked by name stays until you change it (an alert says so) |
| "patch mode" in Settings → Game data | the game updated (new build id) | normal: for 48 hours it checks for new game data every hour, downloading only what changed |
| Files | `HOME\datapack-live\current.txt` names the pack in use; the folder before it is kept for Go back | deleting `datapack-live` returns to the data that came with the app |

## Reporting a bug (help the player write it)

Open an issue at https://github.com/xoxoFaith1993/exile-oracle/issues with:
- toolkit version (Settings or `poe2_status`), Windows or Linux;
- what they did and what happened;
- the last ~30 lines of the relevant log, **with account names, character names and email removed**.
