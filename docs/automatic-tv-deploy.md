# Automatic webOS deployment via GWay Remote

The existing `gway-001` self-hosted runner belongs to
`arthexis/gway-remote`. Its dedicated
`.github/workflows/webos-tv-deploy.yml` runs every five minutes and
can be triggered manually. This is a **CI-gated polling workflow**, not a
repository-dispatch event: no cross-repository secret is required.

On each check, GWay Remote uses the **existing local gh authentication**
on gway-001 to read `arthexis/gway-webos-tv`'s current `main` SHA
and its exact-SHA **CI** push run. Only `completed:success` may deploy.
Pending/failed CI is skipped and retried at the next check. The last
successfully deployed SHA is recorded under
`~/.local/state/gway-webos-tv/auto-deployed-sha` to avoid repeated
installs. Failed deployments do not update this receipt and retry.

The fixed workload fast-forwards a clean trusted checkout at
`/home/arthe/Repos/gway-webos-tv`, executes the existing `./deploy.sh`
(Ansible), then `scripts/auto-tv-deploy.py`.

The TV installer uses the existing paired `lab-tv` developer profile
and private local WSS build configuration. When port 3000 or 9922 is
unreachable, TV installation is skipped **without failing the node
deployment**. When online, pairing/model/certificate verification and
installation of all manifest-discovered applications are mandatory.
An online verification, package or installation failure is a real
failure.

The installer records the foreground app before installing. If the
same updated app is still in the foreground afterwards, it closes and
reopens it; otherwise it leaves the TV's current foreground alone.

## Rollout

1. Merge the GWay Remote PR that adds the scheduled runner workflow.
2. Merge this repository's auto-TV installer PR.
3. Trigger `webOS TV automatic deployment` manually in GWay Remote
   for the first end-to-end run and inspect its logs.
4. Subsequent successful webOS main CI runs are deployed on the next
   scheduled check (GitHub schedule execution may be delayed).

No token is stored in the webOS repository. The local GitHub CLI
authentication must remain functional for the runner user.
