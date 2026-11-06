#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ "$(id -u)" -eq 0 ]; then
    echo "Do not deploy as root; Ansible uses become for package installation." >&2
    exit 1
fi
if [ "$#" -ne 0 ]; then
    echo "Usage: ./deploy.sh (configure the listener in ~/.config/gway-webos-tv/deploy.env)" >&2
    exit 2
fi
for command in git ansible-playbook flock systemctl; do
    command -v "$command" >/dev/null 2>&1 || { echo "Missing $command" >&2; exit 1; }
done

state_dir="$HOME/.local/state/gway-webos-tv"
[ ! -L "$HOME/.local/state" ] && [ ! -L "$state_dir" ] || {
    echo "Unsafe deployment state directory" >&2; exit 2;
}
(umask 077; mkdir -p "$state_dir")
[ ! -L "$state_dir/deploy.lock" ] || { echo "Unsafe lock" >&2; exit 2; }
(umask 077; : >> "$state_dir/deploy.lock")
exec 9<>"$state_dir/deploy.lock"
flock -n 9 || { echo "Another GWAY TV deployment is running" >&2; exit 3; }

# Deploy only the current main checkout, never a feature branch or detached HEAD.
[ "$(git -C "$ROOT" branch --show-current)" = main ] || {
    echo "Deploy only from main" >&2; exit 2;
}
[ -z "$(git -C "$ROOT" status --porcelain)" ] || {
    echo "Working tree is not clean" >&2; exit 2;
}
git -C "$ROOT" fetch --quiet origin main
local_sha=$(git -C "$ROOT" rev-parse HEAD)
remote_sha=$(git -C "$ROOT" rev-parse refs/remotes/origin/main)
[ "$local_sha" = "$remote_sha" ] || {
    echo "Checkout differs from origin/main; fast-forward main before deploying." >&2; exit 2;
}
config="$HOME/.config/gway-webos-tv/deploy.env"
[ -f "$config" ] && [ ! -L "$config" ] || {
    echo "Missing private deploy configuration: $config" >&2; exit 2;
}
# This is a deployment configuration file, not a shell script: accept only one
# literal IPv4 address to avoid arbitrary execution from sourced configuration.
listen=$(sed -n 's/^GWAY_WEBOS_BRIDGE_LISTEN=//p' "$config")
case "$listen" in
    ''|*[!0-9.]*|*.*.*.*.*) echo "Invalid WireGuard IPv4 listener" >&2; exit 2 ;;
esac
[ "$(printf '%s\n' "$listen" | awk -F. 'NF==4 && $1>=1 && $1<=255 && $2>=0 && $2<=255 && $3>=0 && $3<=255 && $4>=1 && $4<=254 {print "ok"}')" = ok ] || {
    echo "Invalid listener address" >&2; exit 2;
}
[ "$listen" != "0.0.0.0" ] || { echo "Wildcard listener refused" >&2; exit 2; }

marker="$state_dir/deployed.sha"
current=$(cat "$marker" 2>/dev/null || true)
release_key="$local_sha $listen"
runtime_dir="/run/user/$(id -u)"
if [ "$current" = "$release_key" ] &&
    [ -x "$HOME/.local/bin/tv" ] &&
    [ -x "$HOME/.local/bin/gway-tv" ] &&
    XDG_RUNTIME_DIR="$runtime_dir" systemctl --user is-active --quiet gway-webos-event-bridge.service &&
    XDG_RUNTIME_DIR="$runtime_dir" systemctl --user is-enabled --quiet gway-webos-event-bridge.service &&
    "$HOME/.local/bin/tv" --help >/dev/null 2>&1; then
    echo "GWAY TV already deployed at main SHA $local_sha; no changes."
    exit 0
fi

started=$(date +%s)
ansible-playbook "$ROOT/ansible/deploy.yml" -i 'gway_tv,' -c local \
    -e "gway_webos_bridge_listen=$listen"
# A marker is only written after Ansible's post-install checks succeed.
temp="$state_dir/.deployed.sha.$$"
(umask 077; printf '%s\n' "$local_sha" > "$temp")
mv -f "$temp" "$marker"
echo "GWAY TV deployed main SHA $local_sha in $(($(date +%s) - started))s"
