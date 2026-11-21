# Using Exile Oracle with Claude

**This is how the toolkit is meant to be used.** The dashboard shows you the numbers; Claude reads the same data and
answers your questions about it, does the maths, compares builds, and puts the right view on your dashboard while it
explains. The toolkit works without Claude, but the best of it is a conversation.

## 1. Connect (once, about a minute)

**Claude desktop app (recommended)**
1. Install the toolkit and open the dashboard (the red icon by your clock).
2. Go to the **Status** tab → **Connect to Claude** → click **Connect to Claude desktop**.
   (It adds the toolkit to Claude's settings file and keeps a backup of the old one.)
3. Fully quit Claude (right-click its tray icon → Quit) and open it again.
4. In a new chat, ask: *"What Exile Oracle tools do you have?"* Claude should list tools starting with `poe2_`.

**Claude Code (terminal)**
In Settings, open *"Using Claude Code instead?"* and run the one command it shows, e.g.
```
claude mcp add poe2 --scope user -- "<your install>\python\python.exe" "<your install>\toolkit\server.py"
```
then start a new Claude Code session.

**Linux / Steam Deck:** use Claude Code the same way. `install.sh` prints the exact command at the end; it looks like
```
claude mcp add poe2 --scope user -- "$HOME/.local/share/poe2toolkit/app/python/bin/python3" "$HOME/.local/share/poe2toolkit/app/toolkit/server.py"
```

Nothing is sent anywhere by the toolkit itself. Claude reads your toolkit data only when you ask a question, through
the toolkit's own tools, and those tools are read-only toward the game.

## 2. Set your profile first
Dashboard → **Settings** → **Your profile**: your class, main ascendancy, league-start path (e.g. `Lich, Blood Mage`)
and the words you care about in patch notes. Claude uses these as your defaults.

Got more than one character? Pick the one you're playing in **Playing** at the top of the dashboard. Every page and
Claude answer for that one unless you name another.

To let Claude see your characters: install **Path of Building Community (PoE 2)** and sign in to your GGG account in
it once. Then ask Claude *"import my character <name>"* (it only talks to GGG when you ask, and reuses an import
for 15 minutes).

## 3. Things to ask

**Economy and farming**
- "What should I farm right now, and why?"
- "What's Mageblood / a Divine / Omen of Light worth, and where is it heading this week?"
- "What are the biggest price movers in the last 24 hours?"
- "Put Mageblood on my wishlist at 90 div" / "what's on my wishlist, and is anything close?" (Wishlist page)
- "Any Currency Exchange gaps worth trading right now?" (the same item cheaper in one currency than another; Economy page)
- "It's day 1 of the league: what should I sell straight away and what should I hold?"

**The Oracle (what happens next)**
- "What's today's omen, and how long until 1.0?"
- "Where will Omen of Light / Exalted Orbs be in a week?" (it answers with a range, and says how often that range held)
- "What did the latest patch do to prices?" (it reads the newest patch notes the app picked up)
- "Plan my first 72 hours of 1.0, hour by hour."
- "How did Mageblood move through the last leagues? When should I sell mine?"

**Atlas and maps**
- "Which atlas strategy suits my build right now? Draw it on the Atlas page."
- "How should I roll my waystones, and what would each strategy earn me per hour?" (Maps page)
- "Which tablets should I run for my strategy?" (Tablets page)
- "Which waystone mods are deadly for my build? Make me a search string that hides them."
- In game: **Ctrl+D on a waystone** rates every mod for your build.

**Campaign**
- "Plan my campaign rush: which rewards can't I skip, and when do I do each trial?"
- "Which permanent rewards am I still missing?" (from your checklist on the Campaign page)
- In game, the **route panel** follows your zone by itself (Ctrl+Alt+R hides it).

**My character**
- Paste any build into the vault on the Builds page (a Path of Building code or a pobb.in / pastebin / poe.ninja link),
  then ask about it by name.
- "Import my character Bob_the_Witch and show it on the dashboard."
- "How close am I to the top 1% of my ascendancy? What closes the gap fastest?"
- "Find me upgrades under 5 divines, best DPS per divine first."
- "What if I swap my helmet for this item?" (paste the item: Ctrl+C on it in game)
- "Compare my build with this one" (paste a Path of Building code): with builds from the vault it shows on the
  **Compare** page (shape chart, stat bars, both trees on one tree, gear and skills)

**Builds and patch notes**
- "What does this build cost, and in what order should I buy it?" (paste a PoB code)
- "What did the latest patch change for my builds?"
- "Plan my league start as a Witch going Lich then Blood Mage."

**Crafting**
- "How do I craft this?" (paste the item text) — Claude reads every mod's tier and gives a step-by-step route with
  current currency costs; the **Craft** tab can then follow it step by step.
- "Is this rare any good?" (paste it)

**Sessions**
- "How did my last session go? Maps per hour, deaths, average map time?"

## 4. Tips
- The **"Ask the Oracle:" chips** on every page open Claude with the question typed in: just press Enter. (Claude
  shows a short safety note on prompts that arrive from a link; that's normal.) Settings → Question chips can switch
  them to ChatGPT or plain copy.
- Ask Claude to **"show it on the dashboard"**: it can put charts, tables, build costs, upgrades and compares on the
  dashboard's *From the Oracle* tab while it explains in chat.
- Prices follow poe.ninja and GGG's Currency Exchange; early in a league they move fast. Ask "refresh prices" first
  if it matters.
- Uniques whose value depends on their roll (e.g. Prism of Belief) are priced at the cheapest roll: Claude will say
  so; check the trade site for your roll.
- Rare items have no public prices: the toolkit estimates what crafting one would cost (a floor).

## 5. What Claude can and can't do here
- **Can:** read prices and history, your builds and imported characters, your play sessions (from the game's log
  file), patch notes, and the whole research behind the Oracle (market trends, forecasts, patch impact, farming,
  uniques, atlas, campaign, bosses); run Path of Building for real numbers; plan crafts, league starts, atlas setups
  and campaign rushes; put what-if cards on the Build Lab and views on the dashboard.
- **Can't / won't:** touch the game (no input, no memory reading, no game-file changes), log in for you, trade for
  you, or use GGG's private trade API. Your GGG login stays inside Path of Building.

## Troubleshooting
- *Claude doesn't list `poe2_` tools:* quit Claude completely and reopen it; check Settings says "Connected".
- *"Monitor not running":* click the red tray icon (or start Exile Oracle from the Start menu).
- *Disconnect:* Settings → **Disconnect**, then restart Claude.

## Using ChatGPT or Gemini instead
Exile Oracle's tools are a standard MCP server, so other AI apps can use them too:
- **Settings → Other AI apps → Connect** next to *ChatGPT (desktop app / Codex)* or *Gemini CLI*, then restart that
  app. ChatGPT is marked *untested* until a player confirms it works.
- Every app gets the same built-in instructions when it connects: how to use the tools, the Build Lab, and the rules.
  So you can ask the same questions as in this guide.
- The Build Lab's *Oracle feed* shows which app is asking.
- **Gemini CLI** (tested): personal Google sign-in no longer works for it, so it needs a Gemini API key (*Use Gemini
  API Key*). Start it in an **empty folder**, not the Exile Oracle folder, so it uses the tools instead of reading
  the app's files. Free keys hit their per-minute limit quickly: if you see "quota exceeded", wait a minute. On
  Windows, if PowerShell says "running scripts is disabled", start it with `gemini.cmd`.

<!-- tools: generated by build_release.py from server.py, do not edit by hand -->
## Every tool the AI can use
The same tools work in Claude, ChatGPT / Codex and Gemini CLI.

| Tool | What it does |
|---|---|
| `poe2_status` | Toolkit status |
| `poe2_refresh` | Pull fresh prices from poe.ninja (cached, polite) and sync GGG hourly Currency Exchange history. |
| `poe2_price` | Latest stored price for items/currency whose name contains query (poe.ninja data). |
| `poe2_history` | Stored price history for items matching query, for trend questions. |
| `poe2_movers` | Biggest price risers and fallers over the last N hours (default 24) from stored history. |
| `poe2_vault_add` | Save a Path of Building (PoE 2) code to the Build Vault forever. |
| `poe2_vault_list` | List builds in the vault (also imports new vault/<league>/*.pob.txt files). |
| `poe2_vault_show` | Show one vault build |
| `poe2_build_cost` | Price a whole build |
| `poe2_pob_stats` | Run a build through headless Path of Building |
| `poe2_show` | Show a view on the toolkit dashboard (http://127.0.0.1:47830) while answering in chat. |
| `poe2_patch_notes` | Patch notes vs the player's builds |
| `poe2_league_plan` | League start planner for any class and any chain of ascendancies (they can be changed any time, e.g. |
| `poe2_farm` | Farm advisor |
| `poe2_top1` | Top 1% check (goal |
| `poe2_league_start` | League start playbook from the last PoE 2 launches (GGG Currency Exchange history, hour by hour, first 7 days) |
| `poe2_sessions` | The player's play sessions from the game's own log (Client.txt) |
| `poe2_craft` | Crafting Lab |
| `poe2_my_characters` | List the player's PoE 2 characters (all leagues incl. |
| `poe2_import_character` | Import one of the player's characters live (gear, tree, jewels, skills) through headless Path of Building and save it to the vault; returns build_id for poe2_show/character, cost, upgrades. |
| `poe2_upgrades` | Upgrade finder |
| `poe2_whatif` | What if I swap this item? Puts item_text (in-game Ctrl+C text) into slot (Helmet, Body Armour, Gloves, Boots, Amulet, Ring 1, Ring 2, Belt, Weapon 1, Weapon 2) and shows every stat that changes. |
| `poe2_compare` | Compare two builds in Path of Building side by side (b vs a, % differences). |
| `poe2_read_rare` | Read a rare item |
| `poe2_build_planner` | Put a build into Path of Exile 2's in-game Build Planner (GGG's documented .build file; the game shows the passive path, skills + supports to cut and gear-slot hints, and reloads the file by itself when it changes). |
| `poe2_levelling` | Review a levelling route for a vault build BEFORE it goes into the in-game Build Planner (the automatic order is a rule of thumb; plans stay a plain endgame path until you switch the route on). |
| `poe2_lab` | The Build Lab tab on the dashboard |
| `poe2_campaign` | Campaign rush |
| `poe2_atlas` | Endgame (the Atlas, Maps and Tablets pages) |
| `poe2_oracle` | The Oracle |
| `poe2_doctor` | Something in the toolkit is broken or acting odd (overlay, prices, dashboard, Build Planner, Path of Building, Claude connection)? Call this FIRST |
| `poe2_from_overlay` | Items the player sent from the in-game price-check overlay (its Ask the Oracle button, called Ask Claude before 0.4.0), newest first |
| `poe2_wishlist` | The player's chase-item wishlist (its own Wishlist page under Market) |
| `poe2_trade_link` | Make an official trade-site search link (by unique name and/or base type) to open in a browser. |
<!-- /tools -->
