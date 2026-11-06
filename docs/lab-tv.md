# Lab TV developer reference

This document describes the TV used for local development. Recheck live state
before using it; the address, developer session, and installed tools can change.

## Identified device

- Manufacturer/model: Hyundai HYLED3256WiM.
- On 2026-11-05, the developer CLI reported SDK 8.4.9 and firmware 13.48.30.
- LG's [SDK version table](https://webostv.developer.lge.com/develop/tools/sdk-introduction)
  maps SDK 8.x to the webOS TV 23 generation; its documented web engine is
  [Chromium 94](https://webostv.developer.lge.com/develop/specifications/web-api-and-web-engine).
  This is a compatibility guide, not proof that every API works on this Hyundai.
- The TV's secure SSAP interface is used by `tv`/`gway-tv`. Developer Mode uses
  a separate SSH interface and key server. Remote-control pairing does not
  establish developer access.

## Developer access

On 2026-11-05, an authenticated `ares-device --system-info` request succeeded
using the `lab-tv` CLI device profile. The address can change after a restart;
confirm the TV identity and update the profile as needed. Do not put live
addresses, pairing material, passphrases, or keys in the repository.

The TV's Developer Mode app requires an LG Developer account. To set up the
developer key, enable Key Server on the TV and run this from a local terminal:

```sh
./scripts/developer-connect.sh lab-tv
```

Enter the TV-displayed passphrase into the CLI prompt, not into chat or a shell
argument. The script retrieves the key and checks system information; it does
not install an app. The profile must already be configured. See
[LG's Developer Mode guide](https://webostv.developer.lge.com/develop/getting-started/developer-mode-app)
for device registration, session extension, and the temporary nature of
developer-mode installations.

On the ARM64 lab host, webOS CLI 3.2.6 crashed with native Node add-ons enabled.
Node 24 with `NODE_OPTIONS=--no-addons` successfully listed devices and queried
the TV. The script uses the locally installed paths and allows overrides; this
workaround is host-specific and does not prove every CLI operation works.

## App and input considerations

- Build for remote navigation (arrows, OK, Back), with clear focus states.
- USB keyboards are supported by webOS generally, but a keyboard has not been
  tested on this TV. Bluetooth keyboard support is also unverified.
- The existing TV CLI can capture a native screenshot; the previously observed
  capture was 960×540 JPEG and does not establish the app's viewport size.
- On 2026-11-05, `apps/remote-test` was packaged and installed, and the TV
  reported it as the foreground app. Individual physical buttons have not yet
  been verified. Media formats and individual Luna API permissions remain
  unverified.
- On 2026-11-05, the event bridge was started on the WireGuard interface and
  a restricted edge route was configured with TLS on both hops. The TV app
  paired over WSS; a remote-control API request for LEFT reached the local
  naming script as key 37. A physical remote button remains unverified. The
  installed app was built with the edge URL injected into a temporary package;
  the repository source intentionally contains no live URL. The route limits
  source access to the lab's then-current public IPv4 address, which can change.
  The private-hop certificate requires coordinated rotation at both endpoints
  before expiry, and the edge and firewall changes must be reconciled with their
  owning deployment configuration to avoid being overwritten.
- The Watchtower operator command `gway-tv-pair` opens a two-minute pairing
  window over the TLS-protected WireGuard administrative path and displays the
  code only on an interactive terminal. App 0.4.0 uses a number-key dialog;
  simulated key events completed pairing, while physical number keys have not
  yet been checked on this TV. Existing pairings reconnect without a new code.
- App 0.5.0 uses button-name overrides from the bridge and falls back to its
  built-in names. TV-control API events confirmed an override and a fallback;
  physical button acceptance remains separate.
- Developer Mode apps are temporary: follow the TV's session expiry and
  extension behavior. Do not equate successful CLI setup with an installed app
  or physical display acceptance.

Credentials and private key material belong outside the checkout. Do not print,
copy, or commit them. Live interaction with the TV requires operator
authorization; distinguish acknowledgements from observed on-screen results.
