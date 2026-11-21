PoE 2 Toolkit for Linux and the Steam Deck
==========================================

Install (no sudo, only for your user):
    sh install.sh
    sh install.sh --autostart     same, and start it in the background when you log in

Then open "PoE 2 Toolkit" from your app menu, or http://127.0.0.1:47830 in your browser.
On a Steam Deck: do this in Desktop Mode. To open it from Game Mode, right-click the menu entry
in Desktop Mode and choose "Add to Steam".

Your data (prices, builds, settings) lives in ~/.local/share/poe2toolkit and survives updates.
Updates: the dashboard shows a banner when a new version is out; one click installs it.

Remove:
    sh uninstall.sh               keeps your data
    sh uninstall.sh --purge       removes your data too

Path of Exile 2 runs through Steam's Proton on Linux. The toolkit finds the game, its log file and Path of
Building (if you run PoB under Wine or Proton) by itself; you can set the game folder on the Status tab if not.
The price-check overlay is Windows-only for now.

Connect to Claude Code (optional, but this toolkit is made to be used with Claude):
    claude mcp add poe2 --scope user -- "$HOME/.local/share/poe2toolkit/app/python/bin/python3" \
        "$HOME/.local/share/poe2toolkit/app/toolkit/server.py"

Includes a portable Python (python-build-standalone, PSF licence) and LuaJIT, lua-utf8 and Lua-cURL (MIT),
built by GitHub Actions. Game art (c) Grinding Gear Games. Not affiliated with or endorsed by GGG.
