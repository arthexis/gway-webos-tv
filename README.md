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
