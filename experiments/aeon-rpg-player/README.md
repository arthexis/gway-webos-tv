# AEon RPG Player: native feasibility probe (#51)

This experiment is **not** the finished player. It remains outside `apps/` to avoid automatic deployment. Host binaries are not TV artifacts.

## Evidence (2026-11-27, gway-001)

- `~/planet-aeon-lab/mkxp-z`: `a8f9d9ee331034b7778d0f6c3a5603de8b87388f`; game: `dd18e021a5fabc390f7680dd0f7bfc0abb5250a1`. Game.ini confirms RGSS3 and RPGVXAce RTP. No finished executable or build.ninja found in the inspected engine build directories; prior runtime acceptance unverified.
- Federated webOS discovery available; status `provider_unavailable`. Existing CLI reports `Cannot establish a TLS connection to the TV.` Developer profile `lab-tv` exists, but device-info help invocation segfaulted in bounded execution. This does not establish an expired session. No pairing, wake, repair or deployment attempted.
- `docs/lab-tv.md` records **Hyundai HYLED3256WiM**, SDK 8.4.9 and firmware 13.48.30 (2026-11-05). Reconfirm model, firmware and CPU ABI; LG compatibility does not establish Hyundai behavior.
- Host SDL 2.26.5 build and headless smoke pass. Ruby unavailable locally; fixture validation is delegated to CI. No RGSS execution claimed.

## First increment

`sh experiments/aeon-rpg-player/check.sh` compiles and runs input unit tests and SDL host smoke. CI also generates and decodes the minimal original VX Ace fixture. To generate it, run `ruby generate_fixture.rb /path/to/new-game-dir`. It contains Game.ini and generated Scripts.rvdata2, no proprietary RTP. With a verified RGSS3 engine, D-pad moves a square, confirm toggles color and cancel exits. Not yet executed on a TV.

The SDL GameController probe selects the first recognized device, maps position-based face buttons to physical SNES labels, applies dead zone and clears state on focus loss. It detects hotplug, prints logical button transitions and displays their state. Keyboard: arrows, Enter (A), Backspace (B), X, Y, L, R, S (Start), Tab (Select). Unmapped devices are reported, not guessed. Per-game remapping, raw event diagnostics and persistent library remain open.

## Target gate

1. Restore status through the existing paired provider; confirm model, firmware, ABI and Developer Mode. Review #13, #39 and #43 before creating an independent runtime repository. No automatic registration.
2. Pin compatible native toolchain/sysroot and SDL-webOS release with verified checksums. Cross-compile using target compiler and target SDL pkg-config; validate ELF ABI and dependencies before staging an explicit native IPK with unique app ID. Document checksum and test installation without affecting existing apps. Target IPK is BLOCKED, no placeholder.
3. Compare pinned mkxp-z standalone and libretro target compilation; libretro supports GLES2 but target core availability is not established. Validate original fixture first, then Planet Aeon. Verify RTP licenses and separate engine and saves.
4. Pair SN30/SN30 Pro via normal TV settings using supported controller mode. Verify physical labels, focus, disconnect/reconnect, duplicate system navigation, dead zone. Allow SDL-webOS polling delay. USB fallback is a separate result. Physical acceptance BLOCKED, not FAIL. No root or Bluetooth stack modifications.

References: https://www.webosbrew.org/develop/guides/native/gamepad/ ; https://www.webosbrew.org/develop/guides/native/ ; https://docs.libretro.com/library/mkxp-z/ .
