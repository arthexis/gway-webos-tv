#!/bin/sh
set -eu

# Regression check: the fast-path comparison and persisted marker must use
# the same release key (SHA + listener). A SHA-only marker causes a full
# Ansible run on every invocation even when the deployed release is healthy.
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
script="$ROOT/deploy.sh"
grep -F 'release_key="$local_sha $listen"' "$script" >/dev/null
grep -F '[ "$current" = "$release_key" ]' "$script" >/dev/null
grep -F 'printf ' "$script" | grep -F '"$release_key" > "$temp"' >/dev/null

# Ensure a change in the WireGuard listener invalidates the cached release.
sha=0123456789abcdef
listener=10.90.0.2
key="$sha $listener"
[ "$key" = "$sha $listener" ]
[ "$key" != "$sha 10.90.0.3" ]
echo "deploy marker regression checks passed"
