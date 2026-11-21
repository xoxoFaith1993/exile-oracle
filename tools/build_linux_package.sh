#!/bin/sh
# Build the Linux download: exile-oracle-linux-x86_64-<version>.tar.gz
#   sh tools/build_linux_package.sh <linux runtime dir> <out dir> [game art .tar.gz]
# Run from the repository root (GitHub Actions does). Contents:
#   exile-oracle-linux/install.sh, uninstall.sh, exile-oracle.desktop.in, README.txt
#   exile-oracle-linux/app/python/   portable CPython (python-build-standalone, PSF licence)
#   exile-oracle-linux/app/toolkit/  the toolkit + linux/ (LuaJIT, lua-utf8, lcurl) + gameart/ (when given)
set -eu
RT=$(realpath "$1")
OUT=$(realpath -m "$2")
ART=${3:-}
PY_URL='https://github.com/astral-sh/python-build-standalone/releases/download/20261110/cpython-3.15.2%2B20261110-x86_64-unknown-linux-gnu-install_only.tar.gz'
VER=$(python3 -c "import re;print(re.search(r\"VERSION = '([^']+)'\", open('poe2kit/config.py').read()).group(1))")
W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT
P="$W/exile-oracle-linux"
mkdir -p "$P/app/toolkit" "$OUT"

# the toolkit: the repository's tracked files, minus build/publishing files and Windows-only binaries
git archive --format=tar HEAD | tar -xf - -C "$P/app/toolkit"
(cd "$P/app/toolkit" && rm -rf .github .gitignore .gitattributes release tools packaging docs bin build_release.py tray.pyw)
cp -a "$RT" "$P/app/toolkit/linux"
chmod +x "$P/app/toolkit/linux/bin/luajit"

# portable Python, trimmed of its test suite and GUI toolkits
curl -fsSL "$PY_URL" -o "$W/python.tar.gz"
tar -xzf "$W/python.tar.gz" -C "$P/app"
for d in test idlelib tkinter turtledemo lib2to3 ensurepip; do
  rm -rf "$P/app/python/lib/python3."*/"$d"
done
find "$P/app/python" -name __pycache__ -type d -prune -exec rm -rf {} +

# game art (pictures only, made from the author's own game files; GGG owns them)
if [ -n "$ART" ] && [ -f "$ART" ]; then
  mkdir -p "$P/app/toolkit/gameart"
  tar -xzf "$ART" -C "$P/app/toolkit/gameart"
fi

cp packaging/linux/install.sh packaging/linux/uninstall.sh packaging/linux/exile-oracle.desktop.in "$P/"
cp packaging/linux/README.txt "$P/README.txt"
cp release/LICENSES.md "$P/LICENSES.md"
chmod +x "$P/install.sh" "$P/uninstall.sh"

NAME="exile-oracle-linux-x86_64-$VER.tar.gz"
tar -C "$W" -czf "$OUT/$NAME" exile-oracle-linux
echo "$OUT/$NAME $(du -h "$OUT/$NAME" | cut -f1)"
