#!/bin/sh
# Private standalone native helper. GPL-2.0-only dependency; not a player/core rebuild.
set -eu
d=${1:?supply directory containing pinned dependency files}
out=${2:?supply output path}
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
(cd "$d"; sha256sum -c <<'SUMS'
651d514ee52761c26af774d74e91346bf150c915120d967ec4332a69ea1600f5  mongoose.c
0ee23157099964b7ca1c7bf3e02b1b8250cbd7838a6938fed63726e720f70b0b  mongoose.h
f0d9cfd6f7d92f6ec061a5fb2882f67d2521a151bf09a637c33ca6181834b048  LICENSE
SUMS
)
"${CC:-cc}" -std=c99 -D_DEFAULT_SOURCE -DMG_TLS=MG_TLS_BUILTIN -I"$d" -O2 "$here/voice_client.c" "$d/mongoose.c" -pthread -o "$out"
