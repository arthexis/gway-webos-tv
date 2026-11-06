# Ansible deployment

This playbook deploys the host-side `tv`/`gway-tv` commands, OCR prerequisites,
the Python environment, and the existing TLS WebSocket event bridge (including
`monitor.read`). It **does not** configure WireGuard, the public edge proxy,
DNS, firewall, TV pairing, or install/launch apps on the TV.

Run on gway-001 as its normal user after the change is merged into `main`:

```sh
cd ~/Repos/gway-webos-tv
ansible-playbook -i 'gway_tv,' -c local \
  ansible/deploy.yml -e gway_webos_bridge_listen=10.90.0.2 \
  --limit gway_tv
```

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

The existing TV client state, TLS keys, Watchtower pairing credentials, and
app-build endpoint configuration are preserved. TV app packaging and developer
mode installation are explicit, separate operations.
