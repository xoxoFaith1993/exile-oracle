#!/bin/sh
# Exile Oracle (formerly PoE 2 Toolkit) for Linux and the Steam Deck: installs for your user only (no sudo, nothing system-wide).
#
#   sh install.sh               install (or reinstall) and open the dashboard
#   sh install.sh --autostart   also start it in the background when you log in
#   sh install.sh --update      used by the toolkit's own update button: replace the app, keep your data, restart
#   sh install.sh --no-start    install without starting (tests)
#
# The app goes to ~/.local/share/poe2toolkit/app; your data (prices, builds, settings) stays in
# ~/.local/share/poe2toolkit and survives updates. Remove it with uninstall.sh.
set -eu

SRC=$(cd "$(dirname "$0")" && pwd)
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/poe2toolkit"
APP="$DATA/app"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
UPDATE=0 START=1 AUTOSTART=0
for a in "$@"; do
  case "$a" in
    --update) UPDATE=1 ;;
    --no-start) START=0 ;;
    --autostart) AUTOSTART=1 ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done

[ -x "$SRC/app/python/bin/python3" ] || { echo "This folder doesn't look like the unpacked Exile Oracle download." >&2; exit 1; }

# 1. stop a running copy (the update button runs this script while the toolkit is running)
if [ -x "$APP/python/bin/python3" ]; then
  "$APP/python/bin/python3" "$APP/toolkit/launcher.py" --stop >/dev/null 2>&1 || true
  sleep 1
fi

# 2. put the new app in place (copy next to it first, then swap, so a failed copy leaves the old one working)
mkdir -p "$DATA"
rm -rf "$DATA/app.new" "$DATA/app.old"
cp -a "$SRC/app" "$DATA/app.new"
[ -d "$APP" ] && mv "$APP" "$DATA/app.old"
mv "$DATA/app.new" "$APP"
rm -rf "$DATA/app.old"
chmod +x "$APP/python/bin/"* "$APP/toolkit/linux/bin/luajit" 2>/dev/null || true

# 3. app menu entry (on a Steam Deck: Desktop Mode menu; right-click it there to "Add to Steam")
mkdir -p "$APPS"
rm -f "$APPS/poe2-toolkit.desktop"   # menu entry from before the rename
sed "s|@APP@|$APP|g" "$SRC/exile-oracle.desktop.in" > "$APPS/exile-oracle.desktop"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q "$APPS" 2>/dev/null || true

# 4. start at login (only when asked, or kept if it was already on)
if [ -f "$AUTOSTART_DIR/poe2-toolkit.desktop" ]; then rm -f "$AUTOSTART_DIR/poe2-toolkit.desktop"; AUTOSTART=1; fi
if [ "$AUTOSTART" = 1 ] || [ -f "$AUTOSTART_DIR/exile-oracle.desktop" ]; then
  mkdir -p "$AUTOSTART_DIR"
  sed -e "s|@APP@|$APP|g" -e 's|launcher.py"$|launcher.py" --background|' \
    "$SRC/exile-oracle.desktop.in" > "$AUTOSTART_DIR/exile-oracle.desktop"
fi

# 5. start it
if [ "$START" = 1 ]; then
  if [ "$UPDATE" = 1 ]; then
    nohup "$APP/python/bin/python3" "$APP/toolkit/launcher.py" --background >/dev/null 2>&1 &
  else
    nohup "$APP/python/bin/python3" "$APP/toolkit/launcher.py" >/dev/null 2>&1 &
  fi
fi

if [ "$UPDATE" = 0 ]; then
  cat <<EOF

Exile Oracle is installed.
  Open it:      "Exile Oracle" in your app menu, or http://127.0.0.1:47830 in your browser
  Your data:    $DATA
  Remove it:    sh "$SRC/uninstall.sh"   (keeps your data unless you add --purge)

Optional, with Claude Code (the toolkit is made to be used with Claude):
  claude mcp add poe2 --scope user -- "$APP/python/bin/python3" "$APP/toolkit/server.py"

First start downloads prices, game data and Path of Building (about 2 minutes).
EOF
fi
