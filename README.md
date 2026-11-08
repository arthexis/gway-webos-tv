# GWAY webOS TV

`tv` (also available as `gway-tv`) controls webOS TVs, with **YouTube navigation**,
**verified HDMI switching**, and **native TV screenshots**. It uses
[bscpylgtv](https://github.com/chros73/bscpylgtv) for the webOS
protocol and keeps a short-lived connection for each command.

## Install

Python 3.11+ and [uv](https://docs.astral.sh/uv/) are required for this installation:

```sh
git clone https://github.com/arthexis/gway-webos-tv.git
cd gway-webos-tv
./scripts/install.sh
tv --help
man tv
```

The installer uses an isolated uv tool environment and installs a matching man
page under `~/.local/share/man/man1`. Keep `~/.local/bin` on PATH.

YouTube navigation also needs local OCR. On Debian/Raspberry Pi OS:

```sh
sudo apt-get install tesseract-ocr tesseract-ocr-eng
```

## YouTube and quick captures

```sh
tv youtube                        # switch apps and select the first saved profile if shown
tv youtube search "chatgpt"        # also works from another app or an older search
tv youtube search openai codex     # unquoted words are joined with spaces
tv sc                             # native TV capture saved privately under ~/screenshots
tv sc capture.jpg                 # refuses overwrite and checks the actual image format
tv --json youtube search "chatgpt"
tv yt                             # short form of youtube
tv yts "chatgpt"                   # direct shortcut for youtube search
```

`youtube`/`yt` and `search`/`s` can be mixed: `tv youtube s "chatgpt"` and
`tv yt search "chatgpt"` run the same workflow as the full command.

YouTube commands recognize the classic English/Spanish TV interface from native
captures using local Tesseract OCR. They select the first **saved** account only
when the profile chooser is visible. New-account login, QR codes, and account
challenges require manual completion. The commands preserve an already selected
profile, and search stops on the verified results page without opening a video.

Search clears the old query and operates YouTube's own on-screen keyboard: on
the tested TV, the text-entry API acknowledged text without displaying it.
Upward movement goes through a column without vowels or N, avoiding their
accent popups. Intermediate movements run continuously; captures check the
destination and the completed query rather than grey autocomplete fragments.
Queries support a-z, ñ, digits, spaces, and hyphens, up to 120 characters.
`--wait` controls each screen-readiness deadline (default 30 seconds); typing a
long query can take longer. Unknown layouts or unconfirmed changes return an
error with a private diagnostic capture instead of reporting success.

Ordinary commands never pair or grant permissions automatically. After updating
an older installation, run `tv pair` if remote-button permissions are missing.
The screenshot commands do not need OCR and reuse the native `tv/executeOneShot`
capture path, URL checks, format checks, certificate pin, and owner-only files.

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

## Grouped CLI commands (A1–A3)

The canonical commands group related operations without adding another executable:

```sh
tv apps list
tv apps launch com.webos.app.browser
tv inputs list
tv inputs select 2 --wait 60
tv screen capture
tv screen capture capture.jpg
tv --json inputs list
tv --json inputs select 2
tv --json screen capture capture.jpg
```

Existing `tv apps`, `tv launch`, `tv inputs`, `tv hdmi`, `tv screenshot`,
and `tv sc` remain supported with the same arguments, behavior, and JSON
result shapes. `tv` and `gway-tv` still share the same entrypoint.

## Pairing code and YouTube aliases (A4)

`tv pair code` is the canonical form of `tv pair --code`. Both open the
same local interactive pairing window. For security, both reject `--json`
and non-interactive output; the code is never returned as machine-readable
output. Plain `tv pair` continues to perform normal TV pairing.

`tv youtube`, `tv yt`, `tv youtube search QUERY`, `tv yt s QUERY`, and
`tv yts QUERY` remain supported. The search aliases share the same
validation and execution handler, including `--json` results.

## Federated MCP provider (A6)

The node-local `webos-mcp` stdio executable implements the existing MCP
JSON-RPC provider contract (`initialize`, `tools/list`, `tools/call`).
It advertises exactly two local names: `read` and `execute`. The existing
GWay federation prefixes these as `webos__read` and `webos__execute` when
the `webos` source is registered on the node. It does **not** create another
Watchtower gateway or transport.

- `read`: `status`, `inputs.list`, `apps.list`.
- `execute`: `inputs.select`, `apps.launch`, `screen.capture`,
  `youtube.open`, `youtube.search`.
- `pair` and `pair.code` are intentionally not exposed, and arbitrary
  shell commands are rejected.

**Security boundary:** Run `webos-mcp` only as a trusted node-local provider
behind the existing authenticated GWay federation. Watchtower enforces OAuth
scope from the read-only/execute classification before forwarding. The local
stdio provider is not an OAuth endpoint; direct access to its process must be
restricted by the node deployment. No deployment or registration is performed
by A6 itself.

**Scope compatibility note:** The intended read scope is `gway:remote`, but
the current live Watchtower catalog reports `gway:read` for existing read
tools. The gateway's actual authorization mapping must be reconciled before
production registration; do not assume the new provider is exposed until
that is verified. Execute uses `gway:execute`.

## Pairing state and compatibility

The default state file is `$XDG_STATE_HOME/gway-webos-tv/device.json`, falling
back to `~/.local/state/gway-webos-tv/device.json`. Select another file with
`--state PATH` or `GWAY_TV_STATE`. A sole existing JSON pairing under
`$XDG_STATE_HOME/webos-tv/` is reused in place, including the initial GWAY pairing
format. No key needs to be copied into the checkout or supplied on the command line.

Keys are written atomically with mode `0600`. Captured images also use `0600`,
and image URLs are never printed. Keep keys and screenshots outside this repo.

Pairing requests only the permissions needed by these tools, including
`CONTROL_DISPLAY` for native screenshots.
`CONTROL_INPUT_TEXT` and `CONTROL_MOUSE_AND_KEYBOARD` enable text and button input.
If an older pairing lacks permissions,
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
The CLI installer does not install the optional event bridge, change the
router, or alter kiosk rendering.

## Development

See [the lab TV developer reference](docs/lab-tv.md) for the tested device,
developer connection, and known limitations.

The `apps/remote-test` developer app displays key events from the TV remote or
keyboard without suppressing their default behavior. An optional TLS event
bridge allows the app to send button codes directly to this host. The bridge
accepts only paired button events; it does not execute actions. The TV must
resolve the bridge hostname and trust its TLS certificate. Provisioning is
deployment-specific; see the lab reference for the current host's setup.

Start the bridge on the intended interface with a trusted certificate and key:

```sh
./run.sh event-bridge.py --listen LOCAL_ADDRESS --cert CERT_PATH --key KEY_PATH
```

The TV app's `wss://` endpoint is configured at packaging time and is not
displayed. On the bridge host, run `tv pair --code` in a private interactive terminal
to generate a six-digit code (or use `./run.sh pair-event-bridge.py`). Enter it on the TV with the number buttons and press OK;
Back erases a digit. If the dialog is closed while disconnected, press OK to
open it. Codes expire after two minutes, are single-use, and allow at most five
attempts. The bridge stores a salted hash only during the pairing window. The
app stores its device credential in local storage; the bridge retains only its
hash in owner-only state. A new pairing replaces that credential. The Watchtower
pairing command has a dedicated credential and can only open a pairing window;
it does not execute other commands. Keep all credentials and private keys out
of this repository. The TV verifies the TLS certificate.

After a button press, run `./run.sh name-remote-button.py` to review and name
the most recent event (within five minutes). Names are stored privately under
`~/.config/gway-webos-tv/`. The bridge returns the saved override for each press,
and the TV app uses its built-in label when no override exists. Changes apply on
the next press without reconnecting. The screenshot-based fallback remains available as
`./run.sh name-remote-button.py --ocr --host TV_ADDRESS` and requires Tesseract.
System-handled keys may not reach the app, or may exit it before registration.

Use `./run.sh SCRIPT [ARG ...]` to run Python or shell scripts from `scripts/`
with the repository virtual environment on the path, without activating it.

For the lab app, `./run.sh tv-app.py` builds an IPK in `dist/webos-apps/` using
the endpoint in the private local `~/.config/gway-webos-tv/app-build.json` file
(`{"bridge_url": "wss://example.test/path"}`). It stages a copy and leaves
source files untouched. Existing packages are preserved unless `--replace` is
provided. Check the current TV without installing, or explicitly install and
launch, with:

```sh
./run.sh tv-app.py --check --host TV_ADDRESS
./run.sh tv-app.py --install --launch --replace --host TV_ADDRESS
./run.sh tv-app.py gway-monitor --install --replace --host TV_ADDRESS
./run.sh tv-app.py remote-test gway-monitor --install --replace --host TV_ADDRESS
./run.sh tv-app.py all --install --replace --host TV_ADDRESS
```

The check compares the developer profile's address and reported model with the
certificate-pinned TV connection. It does not independently attest the SSH host
key. `--install` changes the TV; `--launch` also changes the foreground app and requires exactly one selected app. With no app argument, `remote-test` remains the default. `all` selects every app directory in `apps/`.

For a TV already registered with the webOS CLI, retrieve its developer key and
check the connection interactively (enable Key Server in the TV's Developer
Mode app first):

```sh
./scripts/developer-connect.sh lab-tv
```

Enter the passphrase displayed on the TV at the prompt. The script defaults to
the user-local Node and webOS CLI paths used on this host, disables native Node
add-ons for ARM compatibility, and accepts `WEBOS_NODE_BIN` and `WEBOS_CLI_DIR`
overrides. The developer key is handled by the CLI, outside this checkout.

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
