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
Dashboard → **Status** → **Your profile**: your class, main ascendancy, league-start path (e.g. `Lich, Blood Mage`)
and the words you care about in patch notes. Claude uses these as your defaults.

To let Claude see your characters: install **Path of Building Community (PoE 2)** and sign in to your GGG account in
it once. Then ask Claude *"import my character <name>"* (it only talks to GGG when you ask, and reuses an import
for 15 minutes).

## 3. Things to ask

**Economy and farming**
- "What should I farm right now, and why?"
- "What's Mageblood / a Divine / Omen of Light worth, and where is it heading this week?"
- "What are the biggest price movers in the last 24 hours?"
- "It's day 1 of the league: what should I sell straight away and what should I hold?"

**My character**
- "Import my character Bob_the_Witch and show it on the dashboard."
- "How close am I to the top 1% of my ascendancy? What closes the gap fastest?"
- "Find me upgrades under 5 divines, best DPS per divine first."
- "What if I swap my helmet for this item?" (paste the item: Ctrl+C on it in game)
- "Compare my build with this one" (paste a Path of Building code)

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
- Ask Claude to **"show it on the dashboard"**: it can put charts, tables, build costs, upgrades and compares on the
  dashboard's *From Claude* tab while it explains in chat.
- Prices follow poe.ninja and GGG's Currency Exchange; early in a league they move fast. Ask "refresh prices" first
  if it matters.
- Uniques whose value depends on their roll (e.g. Prism of Belief) are priced at the cheapest roll: Claude will say
  so; check the trade site for your roll.
- Rare items have no public prices: the toolkit estimates what crafting one would cost (a floor).

## 5. What Claude can and can't do here
- **Can:** read prices and history, your builds and imported characters, your play sessions (from the game's log
  file), patch notes, the league-start playbook and drop-rate research; run Path of Building for real numbers; plan
  crafts and league starts.
- **Can't / won't:** touch the game (no input, no memory reading, no game-file changes), log in for you, trade for
  you, or use GGG's private trade API. Your GGG login stays inside Path of Building.

## Troubleshooting
- *Claude doesn't list `poe2_` tools:* quit Claude completely and reopen it; check Settings says "Connected".
- *"Monitor not running":* click the red tray icon (or start Exile Oracle from the Start menu).
- *Disconnect:* Settings → **Disconnect**, then restart Claude.
