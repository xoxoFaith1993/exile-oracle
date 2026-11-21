#!/bin/sh
# Remove Exile Oracle (Linux). Keeps your data (prices, builds, settings) unless you add --purge.
set -eu
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/poe2toolkit"
APP="$DATA/app"
PURGE=0
[ "${1:-}" = "--purge" ] && PURGE=1

if [ -x "$APP/python/bin/python3" ]; then
  "$APP/python/bin/python3" "$APP/toolkit/launcher.py" --stop >/dev/null 2>&1 || true
fi
rm -rf "$APP" "$DATA/app.new" "$DATA/app.old"
rm -f "${XDG_DATA_HOME:-$HOME/.local/share}/applications/exile-oracle.desktop" \
      "${XDG_DATA_HOME:-$HOME/.local/share}/applications/poe2-toolkit.desktop" \
      "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/exile-oracle.desktop" "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/poe2-toolkit.desktop"
if [ "$PURGE" = 1 ]; then
  rm -rf "$DATA"
  echo "Exile Oracle and all its data are removed."
else
  echo "Exile Oracle is removed. Your data is still in $DATA (run with --purge to delete it too)."
fi
echo "If you connected it to Claude Code: claude mcp remove poe2 --scope user"
