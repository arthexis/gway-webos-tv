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

## Second increment: distribution reference

`game_store.py` is a Linux host-side reference, not code installed on webOS. The manifest specifies game ID, title, engine, version, ZIP SHA-256, Game.ini entry, and input profile. It stages verified ZIP contents in an isolated directory, rejects traversal, symlinks, reserved paths and case collisions, retains releases, atomically selects a version and provides a separate saves directory. `select` rolls back and `deactivate` hides a game without removing saves. The caller must provide a manifest from the authorized distribution channel and a private library root; this is not signature verification, tamper-proof storage, or power-loss durability. The engine still must be adapted to write saves there instead of in the game directory. `check.sh` runs the reference tests. No private game data is copied.

### Live reachability recheck

Original CI 46000110835 and native probe 46000111061 both PASS. Existing Node 24 CLI works with NODE_OPTIONS=--no-addons; `ares-device --device lab-tv --system-info` now runs but times out. Saved profile TCP 3001 fails with EHOSTUNREACH; 9922 times out; route is eth0, neighbor FAILED, and bounded SSDP MediaRenderer discovery had zero replies. Current target identity, ABI and firmware remain unverified. No profile, credentials, network or services changed. Operator: turn on the TV, verify its network and Developer Mode session, confirm the saved address still matches before any profile update. Do not re-pair or renew a key merely because the host cannot reach it.

The unofficial native-toolchain publishes an ARM64-host/ARM-target SDK; RetroArch also has distinct ARM and AArch64 builds. Do not infer the target ABI from gway-001 (AArch64) or the webOS SDK version. A published mkxp-z libretro core is not proof of a compatible prebuilt webOS core. References: https://github.com/webosbrew/native-toolchain ; https://www.webosbrew.org/develop/guides/native-app/ ; https://github.com/libretro/RetroArch/blob/master/.github/workflows/webOS.yml .

### Live target recovered (2026-11-27)

The saved LAN address had changed. A bounded check of existing LAN neighbors found the two expected TCP services. Existing SSAP certificate pin and model matched; only the address fields in the pairing and lab-tv developer profile were changed, preserving keys. Default SSAP, federated MCP, and Developer Mode now pass. Live model HYLED3256WiM, firmware 13.48.30, SDK 8.4.9, board KF23F_ATSC_US. `uname -m` = aarch64, `getconf LONG_BIT` = 32, interpreter `/lib/ld-linux.so.3`, non-root developer UID 6396. System SDL2, EGL and GLES2 present; developer storage ~760 MB free. Select ARM EABI 32-bit target, not ARM64 host binaries. The mkxp-z checkout supports a GLES build option but target dependencies and RGSS remain unbuilt.

SDK tag `webos-d7ed7ee.6`, Linux AArch64 host archive SHA256 `45a2d12ff557457d92cde4fddaa77a6f1090fca03adc43bb74397e5e0c379501` (recorded from the official HTTPS release asset, not an independently published upstream digest). Local extraction timed out under the 60-second broker limit; no changes to limits. Target workflow uses a dedicated ARM GitHub runner, checks the pinned hash, relocates SDK, builds the unique native input probe IPK and publishes a CI artifact only. Install only after reviewing exact CI revision, ELF linkage and artifact checksum, using existing Developer Mode. This is not the mkxp-z runtime or a completed RPG player. No app has yet been installed by this change. Physical controller tests and full engine, native library UI, save redirection remain pending.
