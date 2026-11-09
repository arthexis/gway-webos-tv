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
