#!/bin/sh
# Build a native Developer Mode probe; never install automatically.
set -eu
cd "$(dirname "$0")"
: "${WEBOS_SDK:?Set path to the relocated webOS ARM gnueabi SDK}"
: "${WEBOS_NODE_BIN:=$HOME/.local/opt/webos-node24/node_modules/node/bin/node}"
: "${WEBOS_CLI_DIR:=$HOME/.local/opt/webos-tools/node_modules/@webos-tools/cli/bin}"
: "${OUTPUT_DIR:?Set an existing private output directory outside the checkout}"
output=$(realpath "$OUTPUT_DIR")
sdk=$(realpath "$WEBOS_SDK")
cc="$sdk/bin/arm-webos-linux-gnueabi-gcc"
root=$("$cc" -print-sysroot)
[ -d "$root/usr/include/SDL2" ]
[ -x "$cc" ]
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT HUP INT TERM
"$cc" -std=c99 -Wall -Wextra -Werror -O2 -I"$root/usr/include/SDL2" controller_probe.c -o "$stage/controller_probe" -lSDL2
readelf -h "$stage/controller_probe" | grep -E 'Class:.*ELF32'
readelf -h "$stage/controller_probe" | grep -E 'Machine:.*ARM$'
readelf -l "$stage/controller_probe" | grep -F '/lib/ld-linux.so.3]'
readelf -d "$stage/controller_probe" | grep NEEDED
cat > "$stage/appinfo.json" <<'JSON'
{"id":"com.arthexis.aeon.inputprobe","type":"native","main":"controller_probe","title":"AEon Input Probe","version":"0.2.0","vendor":"Arthexis","icon":"icon.png"}
JSON
python3 - "$stage/icon.png" <<'PY'
import struct,zlib,sys
w=h=80
raw=b''.join(b'\0'+b''.join(bytes((90,230,130) if 12<x<68 and (30<y<50 or 30<x<50 and 12<y<68) else (16,22,35)) for x in range(w)) for y in range(h))
def chunk(t,b): return struct.pack('>I',len(b))+t+b+struct.pack('>I',zlib.crc32(t+b)&0xffffffff)
open(sys.argv[1],'wb').write(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))
PY
NODE_OPTIONS=--no-addons "$WEBOS_NODE_BIN" "$WEBOS_CLI_DIR/ares-package.js" "$stage" -o "$output"
find "$output" -maxdepth 1 -name 'com.arthexis.aeon.inputprobe_0.2.0_*.ipk' -exec sha256sum {} \;
