# Exile Oracle: notes for Gemini working in this repository
> The same notes are in CLAUDE.md, AGENTS.md and GEMINI.md (one per AI app); they are made from CLAUDE.md by build_release.py.

This toolkit is made to be used with Claude. Players ask Claude about prices, farming, builds and crafting, and when
something breaks they ask Claude to fix it. The project is at an early stage, so expect rough edges and verify before
you assume.

## When a player reports a problem
1. Call the `poe2_doctor` tool if it's connected. Otherwise, from the app folder, run
   `python -c "import sys, json; sys.path.insert(0, '.'); from poe2kit import doctor; print(json.dumps(doctor.run(), indent=1))"`. It checks every part read-only and
   names the sections that apply.
2. Follow **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**: how the parts fit together, safe restarts, and checks and
   fixes per problem.
3. If it's a real bug, help the player open an issue (template in `.github/ISSUE_TEMPLATE`). Remove their account
   name, character names and email from logs first.

## Rules (keep them when changing code)
- **Read-only toward the game:**
  - no memory reading, no changes to game files;
  - the only keys ever sent are Ctrl+Alt+C on an overlay hotkey press and the player's chat-command keys (one chat
    command per press).
- **GGG's trade site** is used only behind the optional setting `live_trade` (off by default), and only when the
  player presses something: the overlay's price check, and Check now on a Wishlist wanted item
  (`poe2kit/tradewatch.py`):
  - one search per check (plus fetches of the listings), GGG's `X-Rate-Limit` headers obeyed, never retried in a
    loop, never in the background (the same wanted item at most once a minute);
  - no login, no seller account names stored (only the trade site's whisper text for the listings on screen);
  - Open this listing: one search for that listing's exact stats and price, when the player presses it;
  - a trade link's search id is the gzip-compressed search itself, read locally (no request);
  - nothing else calls it.
- **Other GGG / poe.ninja data:** only documented public data (poe.ninja economy API, GGG's Currency Exchange
  history, the Build Planner file format). No undocumented endpoints beyond the trade site above, and no scraping.
- **The game's `BuildPlanner` folder:** only files named `Exile Oracle - *.build` are written or removed. The first
  write asks the player.
- **Exiled Exchange 2:** don't copy its code. Its AI policy asks for no AI-written code; read it for facts only.
- **Reports and suggestions** (`poe2kit/report.py`) are sent only when the player presses Send, scrubbed, and
  anonymous. Never send one on your own.
- **Build Lab** (`poe2kit/lab.py`, tool `poe2_lab`): put what-if cards on it whenever you compare options, so the
  player sees Path of Building's numbers.
- **No personal details in commits.** `build_release.py` runs a privacy scan before anything is published.

## Layout
- `monitor.py`: background jobs and the dashboard at http://127.0.0.1:47830.
- `server.py`: the MCP tools Claude uses.
- `overlay.pyw`: the Windows overlay.
- `launcher.py` / `tray.pyw`: starting it.
- `poe2kit/`, one module per area:
  - pricing: `ninja.py`, `trade.py`, `pricecheck.py`, `market.py`;
  - items: `itemtext.py`;
  - Path of Building: `pob.py`;
  - in-game Build Planner: `buildplanner.py`, `buildplan.py`, `route.py`;
  - game log: `clientlog.py`;
  - the Oracle: `oracle.py` (market timing), `prophecy.py` (omen, timeline, countdowns, farming oracle, unique
    history), `forecast.py` (price forecast), `patchrules.py` (patch prophecy);
  - atlas: `atlas.py` (tree from the game files), `atlasplan.py` (strategies, setups, rolling, ROI), `mapmods.py`
    (waystone / tablet mods, danger for a build, search strings, the overlay's waystone check);
  - campaign: `campaign.py` (rush guide, checklist, the route panel's zone card);
  - characters: `chars.py` (the active character every page follows);
  - Currency Exchange gaps: `spreads.py` (the same item priced differently vs Ex / Div / Chaos, strict filters; R24);
  - data updates: `dataupdate.py` (data-only packs from our GitHub, checked, switched, rolled back; R27);
  - alerts: `alerts.py` (the kinds the player picked, real-move filters, daily market digest, the Oracle's calls);
  - league plan: `journey.py` (six stages, checks measured by Path of Building against researched thresholds with sources, the next checkpoint, farming you can run; from scratch without a build);
  - "I'm stuck": `rescue.py` (symptom -> measured gaps for the content played -> fix cheaply / respec / start over; plain questions when the build can't be read);
  - desecration: `desecration.py` (bones, the hidden mod, the 3-choice reveal, omens, odds; data from research/desecration) used by `craftsim.py` and `crafting.py`;
  - wanted items: `tradewatch.py` (saved trade searches checked by hand: new / re-priced / gone listings, pins);
  - wishlist: `wishlist.py` (chase items with a target price: hit / forecast heading there / patch call alerts, Home omen; R25);
  - platform differences: `osutil.py`;
  - checks: `doctor.py`.
- `dashboard/`: `index.html` (dashboard), `overlay.html` (popup) and `route.html` (the campaign route panel).
- `datapack/`: shipped data that doesn't need the game files, including the cleaned research results.
- `research/`: the research behind the Oracle: a report, its data and its scripts per topic (index:
  `research/README.md`). A new research topic gets a row there.
- `pobhost/`: Lua scripts that run Path of Building headless.

## Testing
- `python smoke_test.py`: a fresh data folder, every dashboard view, the overlay price check with live trade off,
  the Build Planner id map and the Claude tools list.
- `python smoke_test.py --pob`: also downloads Path of Building and runs real calculations, levelling-route edits
  and the route maths.
- GitHub Actions runs both on Linux and Windows on every push, and builds and test-installs the Linux package.

## Data updates (no new release)
Data (anything in `datapack/`) can reach players without an app release: `python build_release.py --data` makes a
pack (zip + manifest with every file's size and sha256) and prints the `gh release create data-<version>
--prerelease` command. Publishing needs the author's OK, like a release. Apps pick it up within 6 hours, verify it,
switch to it, and keep the previous one. `release/test_dataupdate.py` tests the whole path (part of smoke_test.py).
Data only: never put code in a pack.
- **Patch mode** (`poe2kit/patchwatch.py`): the app reads the game's build id (Steam's appmanifest, else the size and
  time of `Bundles2/_.index.bin`); when it changes, it checks the community game data (conditional requests: only
  what changed downloads) and our data packs every hour for 48 hours.
- **New league (1.0):** `patchwatch.new_leagues` reads poe.ninja's league list (every 6 h, hourly in patch mode and
  around the 1.0 launch, which counts as patch mode by itself); a new trade league is followed in automatic mode,
  the player is alerted (with how to switch if they picked a league by name), and its day 0 for the Oracle is the 1.0
  launch time (else the earliest of first seen / first exchange hour).
- **Patch day on the author's PC:** `python release/patch_day.py` reads the updated game (launch_sweep.py), rebuilds
  the data pack (make_datapack.py), makes a data update and lists what changed, then prints the publish command.
  The game-file reader (poe2x) is NOT shipped: its library (LibGGPK3) is AGPL and it needs Oodle (oo2core.dll),
  which can't be redistributed.

## Auto-fixes for imported builds
`poe2kit/pob.py` AUTOFIXES: each one repairs a known import problem before Path of Building measures a build, for
every player, and adds a "Fixed automatically: ..." note (shown in green on the Character page). Today: weapons only
in weapon set II are measured with set II. When a player reports wrong numbers, find the cause and add a fix there
(it must leave a correct build unchanged) plus a check in smoke_test.py.

## Docs go with every change
Players only see what the docs show. `build_release.py` refuses to build when a tool is missing from
`CLAUDE-GUIDE.md`, a dashboard page is missing from `README.md`, a research folder is missing from
`research/README.md`, or the README points at a screenshot that doesn't exist. When you add a feature, also update:
- `README.md`: a section with a screenshot (add it to `release/readme_shots.py`);
- `CLAUDE-GUIDE.md`: what to ask (it's the guide for Claude, ChatGPT and Gemini users);
- the tool description and `INSTRUCTIONS` in `server.py` (what every AI app is told);
- `TROUBLESHOOTING.md` when the feature can break;
- `README-friends.md` for big changes.
