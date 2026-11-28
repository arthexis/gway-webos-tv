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

### Physical input probe milestone

PR #52 revision 68ba44c49e080249996fbbf91e225050d39487d0: all three CI runs passed (46003089424, 46003089646, 46003089631). Target artifact 15198683098, ZIP SHA-256 1491a8fadc2764e3edd15e26ffa70ed3c618e5711316376728de0cbe37ee4831, IPK SHA-256 1584f58dcc5efecd59159fbd059c03c38a3e5e235336e8ae1b1d83b46657eaa5. Both digests independently checked on gway-001. ELF32 ARM EABI5 soft-float, interpreter /lib/ld-linux.so.3, dependencies SDL2 and libc, GLIBC_2.4. Installed only com.arthexis.aeon.inputprobe 0.1.0 through authenticated Developer Mode; existing GWAY Monitor and Remote Test remain installed. MCP foreground confirmation and native TV screenshot (960x540) show the SDL controller diagram. No 8BitDo in visible kernel input inventory; pairing and physical button acceptance still pending. Probe remains in foreground for operator testing. No root or Bluetooth configuration changed.

### Engine candidate

Upstream mkxp-z libretro PR revision ef4d336850bf749b531386522109a165c002354b had a successful LR webOS job 73507352989 (run 25087335805 overall failed, no reusable webOS artifact). This is a separate experimental revision from the existing standalone checkout a8f9d9e. The new isolated core workflow reproduces its two-stage build with version-pinned WASI SDK 30 and Binaryen 126 (download hashes logged, not independently pinned yet), previously verified ARM SDK, ABI checks and libretro exports. No candidate core is deployed or claimed compatible until build, license/dependencies and native frontend/game acceptance pass. No proprietary assets are distributed.

### First AEon player bundle (private lab evaluation)

The operator located the TV's native Bluetooth controller pairing UI. Use that UI; in-app pairing/privileged services are no longer required for this increment. Actual 8BitDo input is still unverified. Do not change Bluetooth/audio configuration from the app.

The original core run 46004673740 passed WASI stage one and ARM Meson configuration, but GCC crashed in FLAC window.c (vector multiply RTL). The corrective workflow disables NEON optimization, compiler tree vectorization and LTO, and verifies observed stage-one archive hashes. These are build compatibility changes, not a claim that audio works. The separate native frontend is webosbrew/RetroArch v1.22.2 ARM GLES2 IPK, upstream SHA256 `0b8ead78b49f02097986a14776d1d90ce856184a11290e8c3640f1001b02d4e3`; actual package downloaded and verified. ARM ELF EABI5 soft-float and GLIBC <= 2.31 checks passed for frontend and its three included libraries. TV getconf confirmed glibc 2.31. The package is distinct from stock RetroArch and existing GWay apps.

Target CI produces `aeon-webos-player-inputs` (launcher and reproducible original fixture, with hashes) separately from the existing probe. Core CI produces `aeon-webos-arm-core-candidate` if successful. Download exact artifacts from successful reviewed revisions, verify the artifact digest and each SHA256SUMS, review core dependencies/exports and target GLIBC, and acquire RetroArch COPYING from the pinned tag. The operator-local assembly tool extracts only allowlisted files from the pinned frontend IPK, verifies component SHA-256 and ARM32 EABI/GLIBC, adds original icon, launcher, test fixture, license files and provenance, then calls the existing ares-package CLI:

```sh
python3 experiments/aeon-rpg-player/bundle_player.py \
  --frontend /private/inputs/com.retroarch.webos_1.22.2_arm.ipk \
  --core /private/inputs/mkxp-z_libretro.so --core-sha <verified-core-sha256> \
  --launcher /private/inputs/launcher --launcher-sha <verified-launcher-sha256> \
  --fixture /private/inputs/fixture.zip --fixture-sha <verified-fixture-sha256> \
  --frontend-license /private/inputs/RetroArch-COPYING \
  --core-license /private/inputs/mkxp-z-COPYING --output /private/new-output
```

The expected package is `com.arthexis.aeon.rpgplayer_0.1.0_arm.ipk`, assembled locally only (no automatic deployment or public combined package). The launcher boots the fixture through RetroArch, initializes separate `system`, `saves`, `states`, `games` and config paths under `/media/internal/.aeon-rpg-player` if writable, otherwise HOME. It refuses non-private or wrong-owner data directories; does not overwrite config. On the TV's developer SSH session `/media/developer` is not writable and `/media/internal` is writable; actual native jail write access and persistence across update/reinstall still require acceptance. RetroArch's content browser is the initial library interface; custom library UI, host store transport, secure updates and physical save/input tests are still open. The game checkout `dd18e02` has uncommitted RGSS script changes, lacks Audio/Graphics directories and declares RPGVXAce RTP. Do not distribute uncommitted game data or copyrighted RTP in CI; after fixture acceptance use an operator-reviewed private release and legally available RTP. RetroArch GPLv3 and core GPLv2 licensing and corresponding-source obligations need review before redistribution; this bundle is for private lab evaluation only.
