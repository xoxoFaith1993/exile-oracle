# Exile Oracle: notes for Codex / ChatGPT working in this repository
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
- **GGG's trade site** is used only by the optional overlay setting `live_trade` (off by default):
  - one search per check, GGG's `X-Rate-Limit` headers obeyed, never retried in a loop;
  - no login;
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
  - platform differences: `osutil.py`;
  - checks: `doctor.py`.
- `dashboard/`: `index.html` (dashboard) and `overlay.html` (popup).
- `datapack/`: shipped data that doesn't need the game files.
- `pobhost/`: Lua scripts that run Path of Building headless.

## Testing
- `python smoke_test.py`: a fresh data folder, every dashboard view, the overlay price check with live trade off,
  the Build Planner id map and the Claude tools list.
- `python smoke_test.py --pob`: also downloads Path of Building and runs real calculations, levelling-route edits
  and the route maths.
- GitHub Actions runs both on Linux and Windows on every push, and builds and test-installs the Linux package.
