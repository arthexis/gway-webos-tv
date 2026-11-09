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
