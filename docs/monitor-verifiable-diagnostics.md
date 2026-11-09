# Verifiable GWAY Monitor diagnostics — implementation notes

Issue: #32.

## Current incremental implementation

- Staged webOS app includes `gway-build.json` with source Git SHA and build ID.
- Built IPK has a local `.sha256.json` sidecar with its exact SHA-256.
- Frontend includes `diagnostic.js`, a read-only helper that extracts an existing deployment card's `.status-label` and `aria-label` from the DOM. It rejects invalid/expired requests and never computes badges from collector data.
- Unit test covers positive and negative DOM cases.

## Pending before merge or deploy

1. Add the authenticated WSS request/response broker to `event_bridge.py`, with strict `monitor.diagnostic` authorization, session binding, single outstanding nonce, expiration and size bounds.
2. Wire the frontend to receive broker challenges and return DOM evidence, using the installed `gway-build.json` identity. Do not expose credentials or arbitrary DOM.
3. Add bridge integration tests for valid and denied credentials, expired/replayed nonce, disconnected TV and concurrency.
4. Ensure sidecar and staged identity are validated against the *same* exact source tree, and verify atomicity/idempotence of metadata publication.
5. Run full CI and security review. Field acceptance requires actual TV evidence; source-level tests are insufficient.

No merge or deploy is authorized by this draft.

## Protocol implementation on PR #33

- TV registers with `monitor.diagnostic.register` using its scoped `monitor.diagnostic.respond` capability.
- A separate credential explicitly granted `monitor.diagnostic.read` may request the fixed AgentOps repository. The bridge generates a cryptographically random 128-bit nonce and forwards a challenge only to the registered TV socket. At most one request is active; timeout 5 seconds.
- TV reads the current DOM, replies with badge/ARIA/build identity; bridge checks nonce, source socket, schema and maximum 1024-byte response, and consumes the pending challenge.
- **Security review required:** current protocol does not yet verify that the returned Git SHA is present in a trusted server-side build registry, and the app-side identity is self-reported. The current frontend reads `gway-build.json` synchronously; review compatibility and failure behavior before merge. Explicit operator credential provisioning is intentionally not automated.
- Tests currently cover DOM positive/negative and unprivileged WSS rejection; full two-socket authenticated WSS happy path, replay, expiry, disconnect, and concurrent requests still require tests.
- **Do not merge or deploy until full CI and security validation.**

## Verification checkpoint (PR #33)

- Separate temporary worktree on gway-001, no deployment: isolated diagnostic/packaging suite 6 passed; latest diagnostic suite 6 passed after expiry/disconnect coverage.
- GitHub Actions workflow 42559467991 was still running at last check. Full local suite exceeded the 60-second remote execution limit; **do not claim it passed**.
- Security fixes: permit explicit diagnostic-only operator login, enforce server-side nonce deadline, reject second TV registration, fail pending request when TV disconnects, asynchronously load build identity, reject dirty source trees for attestation.
- Remaining acceptance/security gaps: concurrent operator request test, build-sidecar provenance validation, live TV proof, and final CI conclusion. Treat client-reported DOM and SHA as authenticated client assertions, not cryptographic hardware attestation.

## Concurrency and IPK verification checkpoint

- Two simultaneous diagnostic operators are serialized by the existing per-bridge async lock; integration test verifies that the second nonce is not issued until the first response is consumed and that both operators receive distinct results.
- IPK sidecar now has strict schema and source/build consistency validation; actual IPK SHA-256 is verified before install. Negative test rejects tampered package bytes and inconsistent build ID. Sidecar is atomically replaced after package output.
- The sidecar proves integrity of the *local artifact against its accompanying metadata*, not that the TV currently runs that artifact. A trusted signed release or readback of installed bytes is still necessary for stronger remote provenance.
- Persistent full-suite runner started via detached process on gway-001 after `systemd-run --user` failed (no user bus). Its initial checkout precedes the latest provenance test, so a final run must use latest HEAD. Do not count a pending runner or queued CI as passed.

## Security audit follow-up

- Workflow 42560280366 for e26d8c5 completed SUCCESS across Python 3.11, Python 3.13, deployment validation, and aggregate CI.
- **Privilege escalation found and fixed:** legacy unscoped credentials previously implicitly passed `monitor.diagnostic.read` and `monitor.diagnostic.respond` because the legacy allowlist only excluded old capabilities. New diagnostic capabilities are now explicitly excluded from legacy access. Regression test confirms both denied while existing button capability remains unchanged.
- Isolated diagnostic/packaging suite at HEAD a4016a8: **10 passed in 2.43s**. GitHub Actions workflow 42561108946 was still running when inspected; latest CI is not yet verified green.
- Trust boundary: build SHA and DOM values are TV-client assertions, even over authenticated WSS; local IPK sidecar SHA-256 verifies artifact integrity, not installed TV bytes. No merge or deployment until review and real TV acceptance.

## Final review of CI 42561144830 (HEAD aec3143)

- GitHub Actions: **SUCCESS**. Python 3.11 and 3.13 each completed tests and distribution build; deployment validation completed syntax, marker regression and Ansible syntax; aggregate CI completed successfully.
- WSS coverage includes two authenticated clients, unauthorized operator/TV, replay, server nonce deadline, TV disconnect, and concurrent operator serialization; isolated tests were 10 passed on gway-001. No live TV session or independent installed-IPK byte readback was performed.
- **Merge-readiness: conditional / not field-accepted.** Transport authorization and replay controls are covered, but the responder credential authenticates a client, not the specific installed app. Returned `git_sha`, `build_id`, DOM label and ARIA are client assertions. External IPK SHA-256 is checked against local bytes; no cryptographic link to installed TV bytes. Operator credentials need explicit provisioning. Actual TV-visible AgentOps badge remains unobserved.
- Keep PR draft, #32 open and do not deploy or merge pending a separately authorized field acceptance and provenance decision.

## Read-only TV acceptance procedure — audit of 2026-11-09

### Verified CI

Workflow **42561263560** for `63c21b3134e0cd8a1e07fcfba9a6557338470b04` completed **SUCCESS**. Python 3.11 and 3.13 test/build jobs, deployment validation and aggregate gate each completed successfully.

### 1. Establish independent identity of the local artifact (no TV mutation)

1. Select the previously produced, immutable `com.arthexis.gway.monitor_<version>_all.ipk` and its matching `.sha256.json` sidecar from a trusted build output. Do **not** rebuild, reinstall, launch, or replace packages during read-only acceptance.
2. Run `verify_package_sidecar(package, sidecar)` locally: it checks exact package bytes against the recorded SHA-256 and checks schema, app ID/version and Git SHA/build ID relationship. Record file path, actual computed digest, source commit and provenance of the artifact. An unsigned sidecar can be edited together with an IPK; therefore an independently trusted build record or signed digest is required for supply-chain integrity.
3. Compare the developer profile and read-only paired-TV identity if available; `ares-install --listfull` or app version only establishes presence/version, **not the installed package SHA-256**. Do not substitute a screenshot, `ares-inspect`, a Git SHA reported by the app, or a reconstructed IPK for installed-byte verification.

### 2. Read the actual DOM over authenticated WSS (no screenshots or ares-inspect)

1. Verify from existing configuration that the running bridge has the diagnostic code and a registered GWAY Monitor TV session with explicit `monitor.diagnostic.respond`; the requesting operator must have distinct `monitor.diagnostic.read`. **The draft code is not deployed**, so the new protocol cannot be tested on the actual TV until separately authorized installation.
2. With the **Deployments channel visible on the TV**, send exactly one `monitor.diagnostic.request` for `arthexis/gway-agent-ops` from an authenticated read-only WSS operator session. The bridge issues a fresh random 128-bit nonce and a five-second challenge to its registered TV socket; record the challenge nonce, bridge identity, requesting session, receipt timestamp and whether the response arrived before the server deadline. Never record credentials.
3. Inspect `monitor.diagnostic.result`: require matching nonce, TV socket, `channel=deployments`, `visible=true`, non-null `card.repository=arthexis/gway-agent-ops`, `card.badge=Installed`, and `card.aria_label=Installed`; record `observed_at`, `git_sha`, `build_id` and exact response size. A null card, `unavailable`, expired response or mismatched value is **not** a successful acceptance.
4. The TV-side code reads `#deployments #deployment-list > article`, matches the rendered `h2` and reads `.status-badge .status-label` plus `aria-label` from the DOM. It does **not** recompute status from collector JSON. This is stronger evidence of the *client-reported visible DOM* than a collector snapshot, but the bridge still trusts a credential-bearing client to report it accurately.

### 3. Exact installed IPK SHA: proof boundary and decision

**Current implementation cannot independently establish the exact SHA-256 of the IPK installed on webOS.** The external sidecar attests only the locally built IPK; the client-supplied `git_sha`/`build_id` are not installed-byte hashes. webOS may unpack or transform the package, so hashing application files would not generally reproduce the original IPK digest. A trustworthy installed-package receipt from the TV/package manager that binds the exact artifact digest to the installed app, or an independently authenticated device-side package readback with a defined byte-for-byte comparison, is required. If neither exists, record **NOT VERIFIABLE** rather than asserting equivalence. No package-manager readback interface has been demonstrated here.

### Security and release decision

- WSS scope, nonce, replay, expiry, disconnect and concurrency have automated tests; read-only diagnostics cannot trigger deployment. Operator read access and TV responder permission must be separately provisioned.
- A credential compromise or malicious TV client can fabricate DOM and build identity; nonce/session correlation does not make the client trustworthy. Do not interpret the badge as proof of the installed IPK.
- **CI: PASS. Protocol automated tests: PASS. Actual TV DOM: NOT TESTED. Exact installed IPK SHA: NOT VERIFIABLE with current evidence. Merge readiness: HOLD / DRAFT.** No merge or deployment authorized.
