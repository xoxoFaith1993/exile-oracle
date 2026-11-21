#!/bin/sh
# Build the Lua runtime Path of Building needs on Linux, so nothing has to be installed on the player's PC
# (Steam Deck included): LuaJIT 2.1 (the same Lua PoB uses), lua-utf8 and lcurl (character import).
#   sh tools/build_linux_runtime.sh [out dir, default ./linux]   ->  <out>/bin/luajit, <out>/lib/lua-utf8.so, lcurl.so
# Needs: git, make, gcc, libcurl development headers (Ubuntu: libcurl4-openssl-dev). GitHub Actions runs this.
set -eu
OUT=$(realpath -m "${1:-linux}")
W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT
cd "$W"
# the LuaJIT commit Path of Building's own Linux tests use: newer LuaJIT reads PoB's "#@" first lines as an error
LUAJIT_COMMIT=2460b3ff93a1c955de3d62cfc825de7d68dc272e
git init -q LuaJIT && git -C LuaJIT fetch -q --depth 1 https://github.com/LuaJIT/LuaJIT.git "$LUAJIT_COMMIT"   && git -C LuaJIT checkout -q FETCH_HEAD
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
LuaJIT  $(git -C LuaJIT rev-parse --short HEAD) (v2.1, the commit PoB tests with, MIT)
luautf8 0.1.6 (MIT)
Lua-cURLv3 v0.3.13 (MIT), linked to the system libcurl.so.4
built on $(. /etc/os-release && echo "$PRETTY_NAME"), $(ldd --version | head -1)
EOF
"$OUT/bin/luajit" -v
cat "$OUT/VERSIONS.txt"
