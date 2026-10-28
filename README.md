# GWAY webOS TV

`gway-tv` controls webOS TVs, with **verified HDMI switching** and **native TV
screenshots**. It uses [bscpylgtv](https://github.com/chros73/bscpylgtv) for the webOS
protocol and keeps a short-lived connection for each command.

## Install

Python 3.11+ and [uv](https://docs.astral.sh/uv/) are required for this installation:

```sh
git clone https://github.com/arthexis/gway-webos-tv.git
cd gway-webos-tv
./scripts/install.sh
gway-tv --help
man gway-tv
```

The installer uses an isolated uv tool environment and installs a matching man
page under `~/.local/share/man/man1`. Keep `~/.local/bin` on PATH.

## Pair and control

Use a unique TV address on the LAN. Examples use a documentation address:

```sh
gway-tv --host 192.0.2.50 pair    # approve the TV's connection prompt
gway-tv status
gway-tv inputs
gway-tv hdmi 2                  # waits for HDMI 2 to become the foreground app
gway-tv screenshot              # native TV capture saved under ~/screenshots
gway-tv screenshot capture.jpg
gway-tv apps
gway-tv launch com.webos.app.browser
gway-tv --json status
```

`hdmi` and `launch` return success only after the TV confirms the expected
foreground app. A TV that acknowledges a request but never changes foreground
returns an error. Use `--wait 60` after either command for a slow app.

Screenshots come from the TV's `tv/executeOneShot` API. They can capture the HDMI
image sent by GWAY as well as TV-rendered content supported by the firmware.
The tested TV returns **960×540 JPEG**. Protected video can be excluded by the
TV. The CLI checks the actual format and never labels JPEG bytes as PNG.

## Pairing state and compatibility

The default state file is `$XDG_STATE_HOME/gway-webos-tv/device.json`, falling
back to `~/.local/state/gway-webos-tv/device.json`. Select another file with
`--state PATH` or `GWAY_TV_STATE`. A sole existing JSON pairing under
`$XDG_STATE_HOME/webos-tv/` is reused in place, including the initial GWAY pairing
format. No key needs to be copied into the checkout or supplied on the command line.

Keys are written atomically with mode `0600`. Captured images also use `0600`,
and image URLs are never printed. Keep keys and screenshots outside this repo.

Pairing requests only the permissions needed by these tools, including
`CONTROL_DISPLAY` for native screenshots. If an older pairing lacks permissions,
run `pair` again. Normal status/control commands never initiate pairing or wake
the TV. The tool checks the saved certificate fingerprint before authentication
and pins the SDK's TLS connection to that certificate. A changed certificate
fails closed. The paired model is checked before sending control commands.

When the same TV moves to a different address, use `--host NEW_ADDRESS` with
the existing state file. Run `pair` with that override to persist the new address.
Use a separate `--state` file to pair another TV.

The adapter supports bscpylgtv 0.5.x, disables state subscriptions and its
default SQLite storage, and supplies a pinned SSL context through its
`_ssl_context` compatibility hook. Local TLS tests exercise the real dependency.
No service, background worker, router change, or kiosk-rendering change is
installed by this project.

## Development

```sh
uv venv
uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m build
```

Tests use loopback TV emulators and temporary certificates, with no real-TV
credentials. Live acceptance on the operator's TV is kept separate from CI:
saved-key reconnection, HDMI selection plus foreground verification, and a
downloaded native screenshot should each be checked when changing the adapter.
