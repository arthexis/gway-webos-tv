# Automatic webOS deployment via GWay Remote

The existing `gway-001` self-hosted runner belongs to
`arthexis/gway-remote`. Its dedicated
`.github/workflows/webos-tv-deploy.yml` runs every five minutes and
can be triggered manually. This is a **CI-gated polling workflow**, not a
repository-dispatch event: no cross-repository secret is required.

On each check, GWay Remote uses the **existing local gh authentication**
on gway-001 to read `arthexis/gway-webos-tv`'s current `main` SHA
and its exact-SHA **CI** push run. Only `completed:success` may deploy.
Pending/failed CI is skipped and retried at the next check. The node activation receipt is maintained by `deploy.sh` as
`~/.local/state/gway-webos-tv/deployed.sha` (SHA and listener).
The companion GWay Remote fix uses a separate
`~/.local/state/gway-webos-tv/tv-installed-sha` receipt only after
successful online TV installation. The old `auto-deployed-sha` is not
trusted because it could be written when the TV was unreachable.
CI-gated checks retry pending TV installations without redoing a healthy
node deployment.

The fixed workload fast-forwards a clean trusted checkout at
`/home/arthe/Repos/gway-webos-tv`, executes the existing `./deploy.sh`
(Ansible), then `scripts/auto-tv-deploy.py`.

The TV installer uses the existing paired `lab-tv` developer profile
and private local WSS build configuration. When port 3000 or 9922 is
unreachable, TV installation is deferred **without failing the node
deployment**. The runner must not consider such a deferment a completed
TV installation; it retries when connectivity returns. The opt-in
`--require-online` mode exits with code 10 for unavailable TV/developer
ports, while direct standalone invocation preserves code 0 on skip. When online, pairing/model/certificate verification and
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

## Retry classifications (CI-gated)

The runner treats `10` and `11` as separate **deferred** outcomes, never as
completed TV installs. `10` means port 3000 is unreachable: possible power
off, sleep, or network problem; it is not proof of the physical power state.
`11` means port 3000 responds but developer SSH on 9922 does not: suspect an
expired or disabled Developer Mode session. The local five-minute systemd
timer in `arthexis/gway-remote` #556 retries the same successful CI-gated
main revision when availability changes. Other failures remain fatal, with
no `tv-installed-sha` receipt. Never remotely turn on a TV or silently
replace pairing, model or TLS identity.
