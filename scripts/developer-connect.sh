#!/usr/bin/env bash
set -euo pipefail

# Override these paths if the user-local tools are installed elsewhere.
node_bin="${WEBOS_NODE_BIN:-$HOME/.local/opt/webos-node24/node_modules/node/bin/node}"
cli_dir="${WEBOS_CLI_DIR:-$HOME/.local/opt/webos-tools/node_modules/@webos-tools/cli/bin}"
device="${1:-lab-tv}"

if [[ $# -gt 1 || ! -t 0 || ! -t 1 ]]; then
    echo "Usage: scripts/developer-connect.sh [configured-device-name] (run in a terminal)" >&2
    exit 2
fi
if [[ ! -x "$node_bin" || ! -f "$cli_dir/ares-novacom.js" || ! -f "$cli_dir/ares-device.js" ]]; then
    echo "webOS CLI or Node not found; set WEBOS_NODE_BIN and WEBOS_CLI_DIR." >&2
    exit 1
fi

export NODE_OPTIONS="${NODE_OPTIONS:+$NODE_OPTIONS }--no-addons"
echo "Enable Key Server on the TV, then enter its displayed passphrase at the prompt."
"$node_bin" "$cli_dir/ares-novacom.js" --device "$device" --getkey
echo "Checking the developer connection..."
"$node_bin" "$cli_dir/ares-device.js" --device "$device" --system-info
