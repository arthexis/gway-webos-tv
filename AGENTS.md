# GWAY webOS TV

This repository owns the `gway-tv` CLI. Kiosk rendering belongs to
`arthexis/gway-ap-kiosk`; TV control must not change kiosk or network configuration.

Use `bscpylgtv` for webOS protocol operations. Keep the compatibility adapter
small and test it against the supported dependency version.

Pairing keys, captured image URLs, live network identifiers, and screenshots
belong outside this checkout. Examples and tests use documentation addresses.
Never print a client key or place it in command arguments. Normal commands
require saved pairing and must not silently initiate pairing or wake a TV.

Run `python -m pytest`, `ruff check .`, and `ruff format --check .` before pushing.
Tests use loopback emulators, not real TVs. Live checks require the operator's
authorization; distinguish API acceptance from confirmed foreground state.
