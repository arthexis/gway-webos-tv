# Ansible deployment

This playbook deploys the host-side `tv`/`gway-tv` commands, OCR prerequisites,
the Python environment, and the existing TLS WebSocket event bridge (including
`monitor.read`). It **does not** configure WireGuard, the public edge proxy,
DNS, firewall, TV pairing, or install/launch apps on the TV.

Run on gway-001 as its normal user, from a clean and up-to-date `main`
checkout. Store only the existing WireGuard listener in the private local
deployment configuration (never commit it):

```sh
mkdir -p ~/.config/gway-webos-tv
printf 'GWAY_WEBOS_BRIDGE_LISTEN=10.90.0.2\n' > ~/.config/gway-webos-tv/deploy.env
chmod 600 ~/.config/gway-webos-tv/deploy.env
./deploy.sh
```

The root `deploy.sh` is the canonical local entrypoint, like OCPP CSMS.
It refuses root, non-main or dirty checkouts, and a stale checkout relative
to `origin/main`; serializes runs with a persistent owner lock; and skips
Ansible entirely when the deployed SHA and listener match and the service
and CLI pass readiness checks. The successful deployment marker is written
only after Ansible succeeds. It never modifies network configuration.

For remote execution, use an inventory group named `gway_tv` with the target
user and pass a node-specific `gway_webos_bridge_listen` via inventory.
The address must be the node's already-configured WireGuard address. Do not
point it at `0.0.0.0`. The playbook only deploys from `main` and refuses
to replace pre-provisioned TLS credentials. The `ansible` controller must have
the repo containing this playbook; when using the local command above, update
the checkout to `main` first.

The systemd user manager must be available (`/run/user/<uid>`), and `uv`
must already be installed at `~/.local/bin/uv`. OCR installation needs sudo
privileges; for hosts with OCR preinstalled use
`-e gway_webos_install_ocr=false`.

After deployment:

```sh
XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user status gway-webos-event-bridge
tv --help
gway-remote network --json
```

Fleet is optional and uses the existing Watchtower MCP node_list API (not
a second gateway or an invented fleet_snapshot method). To enable it, provision
the private user-owned file `~/.config/gway-webos-tv/fleet.env` with mode 0600:

```text
GWAY_FLEET_MCP_URL=https://YOUR-WATCHTOWER-HOST/mcp
GWAY_FLEET_TOKEN_FILE=/absolute/path/to/existing/read-only-token
```

The token itself is never stored in this environment file; it points to an
existing private token file. No file is created, populated or modified by
Ansible. Invalid or missing configuration causes Fleet to report
`unavailable`. After changing the private file, explicitly restart the
existing user bridge through the approved deployment workflow; changing the
file alone does not restart systemd. The live node_list contract supplies
identity and reachability but no CPU/service/deployment telemetry, which stays
`unknown` rather than being invented.

The existing TV client state, TLS keys, Watchtower pairing credentials, and
app-build endpoint configuration are preserved. TV app packaging and developer
mode installation are explicit, separate operations.
