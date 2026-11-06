---
name: gway-webos-tv
description: Develop, package, inspect, or explicitly install and test apps on the lab webOS TV using the gway-webos-tv repository and its paired developer tooling.
---

# GWAY webOS TV development

Use `/home/arthe/Repos/gway-webos-tv` for TV control, the event bridge, and TV apps. Read its `AGENTS.md` and `docs/lab-tv.md`; use `gway-ap-kiosk` for kiosk rendering. Preserve the current checkout and any existing work.

Start by checking the current TV address, saved pairing, developer profile and runtime; addresses and Developer Mode sessions change. Use the existing certificate-pinned `tv` status, not network discovery alone, to identify the TV. The SSAP pairing and the developer SSH key are separate. Never print or commit their credentials, image URLs, app pairing codes, or private captures.

The repository runner avoids a venv prelude:

- `./run.sh tv-app.py --check --host TV_ADDRESS` checks the pinned TV, developer profile address, and model. It does not attest that the developer SSH endpoint has the same certificate.
- `./run.sh tv-app.py` builds the remote-test IPK from a temporary staging copy using the local `app-build.json` endpoint; it does not install. It refuses to overwrite an existing artifact unless `--replace` is explicitly given.
- `./run.sh tv-app.py --install --launch --host TV_ADDRESS` explicitly installs, launches, and checks the foreground app. Use only when the task authorizes TV changes. The developer profile must match the given address.
- `./run.sh name-remote-button.py` registers the latest event; `--ocr --host TV_ADDRESS` is the screenshot fallback.

The ARM64 host uses its user-local Node 24 and webOS CLI with `NODE_OPTIONS=--no-addons`; the repository tools apply this workaround. The app endpoint is deployment configuration outside the checkout. Do not embed or log secrets while packaging. If Developer Mode needs a key, `./scripts/developer-connect.sh lab-tv` prompts locally; it is not the six-digit bridge pairing code.

For a lost bridge pairing, use the configured Watchtower `gway-tv-pair` command in a private terminal, then enter its single-use code with the TV remote. The event bridge has no command-execution interface. The existing public route is restricted to the lab's current public IPv4, its private-hop certificate needs rotation, and its firewall/edge changes can be overwritten by owner deployments; diagnose those layers before changing them.

Use `./run.sh tv-app.py --check` with the actual host, focused Python and Node tests, and package checks appropriate to the change. Separate source, packaged artifact, installed version, connected runtime, reported foreground state, and physical remote/display acceptance. The TV screenshot is 960×540 and does not establish the web app viewport. Do not use the stock `ares-inspect` without restricting its listener: it has bound all interfaces on this host.
