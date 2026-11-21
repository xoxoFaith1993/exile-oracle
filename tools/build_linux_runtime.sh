#!/bin/sh
# Build the Lua runtime Path of Building needs on Linux, so nothing has to be installed on the player's PC
# (Steam Deck included): LuaJIT 2.1 (the same Lua PoB uses on Windows), lua-utf8 and lcurl (character import).
#   sh tools/build_linux_runtime.sh [out dir, default ./linux]   ->  <out>/bin/luajit, <out>/lib/lua-utf8.so, lcurl.so
# Needs: git, make, gcc, libcurl development headers (Ubuntu: libcurl4-openssl-dev). GitHub Actions runs this.
set -eu
OUT=$(realpath -m "${1:-linux}")
W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT
cd "$W"
git clone -q --depth 1 --branch v2.1 https://github.com/LuaJIT/LuaJIT.git
git clone -q --depth 1 --branch 0.1.6 https://github.com/starwing/luautf8.git
git clone -q --depth 1 --branch v0.3.13 https://github.com/Lua-cURL/Lua-cURLv3.git
make -s -C LuaJIT -j"$(nproc)"
mkdir -p "$OUT/bin" "$OUT/lib"
cp LuaJIT/src/luajit "$OUT/bin/luajit"
CF="-O2 -fPIC -shared -I LuaJIT/src"
gcc $CF luautf8/lutf8lib.c -o "$OUT/lib/lua-utf8.so"
gcc $CF -I Lua-cURLv3/src Lua-cURLv3/src/*.c -lcurl -o "$OUT/lib/lcurl.so"
strip "$OUT/bin/luajit" "$OUT/lib/"*.so
cat > "$OUT/VERSIONS.txt" <<EOF
LuaJIT  $(git -C LuaJIT rev-parse --short HEAD) (v2.1, MIT)
luautf8 0.1.6 (MIT)
Lua-cURLv3 v0.3.13 (MIT), linked to the system libcurl.so.4
built on $(. /etc/os-release && echo "$PRETTY_NAME"), $(ldd --version | head -1)
EOF
"$OUT/bin/luajit" -v
cat "$OUT/VERSIONS.txt"
