# Automatic webOS TV deployment via GWay Remote

On a successful **CI** workflow run for a push to `main`, the
`Deploy webOS TV via GWay Remote` workflow sends a fixed
`webos-tv-deploy` `repository_dispatch` to `arthexis/gway-remote`.
The dispatch token is stored as `GWAY_REMOTE_DISPATCH_TOKEN` in the
**gway-webos-tv** Actions secrets and must have permission to dispatch
events to **gway-remote**. A manual `workflow_dispatch` can retry.

GWay Remote verifies that the source is exactly
`arthexis/gway-webos-tv` and the requested SHA is the **current**
`main` tip. Only its registered `gway-001` runner runs the workload.
No arbitrary command, host, or branch is accepted from the payload.

The runner updates the clean checkout at
`/home/arthe/Repos/gway-webos-tv` using a fast-forward, verifies the
SHA and runs the existing `./deploy.sh` (Ansible). Only after successful
node deployment does `scripts/auto-tv-deploy.py` check the paired
`lab-tv` developer profile. If the TV control port (3000) or developer
SSH port (9922) is unreachable, TV installation is **skipped with
success**; the GWAY 001 deployment still succeeds.

When both ports are available, the script validates the TV's existing
pairing, certificate pin, model and developer profile. It builds and
installs **all** manifest-discovered webOS applications with `--replace`
without changing the foreground when a different app is active. If an updated app was already foreground and remains foreground after installation, it is closed and relaunched, with foreground confirmation. A reachable but
untrusted TV or a failed package/install is a **real failure**, not an
offline skip. The private WSS build config and pairing keys stay on
gway-001; nothing is placed in GitHub Actions.

### Deployment results

The calling workflow confirms **dispatch only**. Inspect
`arthexis/gway-remote` → Actions → **Remote workloads** for actual
GWAY 001 / TV results. A skipped offline TV install does not mean the
apps are current; the next successful main deployment or manual
workflow dispatch will retry. No background polling or auto-wake is
performed.

### Rollout order

1. Merge the GWay Remote PR that admits `webos-tv-deploy`.
2. Configure/verify `GWAY_REMOTE_DISPATCH_TOKEN` in the webOS repo.
3. Merge this repo's CI workflow PR.
4. Verify the cross-repo dispatch and remote runner receipt.

The existing `CI` workflow remains the only PR validation gate.
