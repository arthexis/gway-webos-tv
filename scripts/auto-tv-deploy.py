#!/usr/bin/env python3
"""Best-effort TV availability, strict identity checks and both app installs.

Only an unreachable TV/developer port is optional. A reachable but untrusted
device, failed package or failed installation is a real deployment error.
"""
import importlib.util
import json
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEVICE = "lab-tv"


def profile_host(home):
    path = home / ".webos/tv/novacom-devices.json"
    profiles = json.loads(path.read_text())
    matches = [p for p in profiles if isinstance(p, dict) and p.get("name") == DEVICE]
    if len(matches) != 1 or not isinstance(matches[0].get("host"), str):
        raise ValueError("Missing or ambiguous pinned lab-tv developer profile")
    host = matches[0]["host"]
    # The SDK profile is authoritative for address, not untrusted CI payloads.
    return host


def port_available(host, port, timeout=3):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, TimeoutError):
        return False


def run(home=None, cli=None, probe=port_available):
    home = home or Path.home()
    host = profile_host(home)
    if not probe(host, 3000):
        print("TV unavailable (webOS port 3000); skipping optional TV installation")
        return 0
    if not probe(host, 9922):
        print("TV developer SSH unavailable (port 9922); skipping optional TV installation")
        return 0
    if cli is None:
        spec = importlib.util.spec_from_file_location("tv_app", ROOT / "scripts/tv-app.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
    # When the device is reachable, pairing/model/certificate checks are mandatory.
    cli.verify_device(DEVICE, host)
    foreground_before = cli.tv_status(host).get("foreground_app")
    args = ["tv-app.py", "all", "--replace", "--install", "--device", DEVICE, "--host", host]
    previous = sys.argv
    try:
        sys.argv = args
        rc = cli.main()
    finally:
        sys.argv = previous
    if rc != 0:
        raise RuntimeError("webOS app installation failed")
    # Refresh only if the updated app was already foreground and still is.
    installed_ids = []
    for app in cli.discover_apps():
        _, meta = cli.load_manifest(ROOT / "apps" / app)
        installed_ids.append(meta["id"])
    if foreground_before in installed_ids:
        foreground_after = cli.tv_status(host).get("foreground_app")
        if foreground_after == foreground_before:
            cli.command("ares-launch", "--device", DEVICE, foreground_before)
            print("Refreshed already-foreground webOS app:", foreground_before)
        else:
            print("Foreground changed during install; not launching any app")
    else:
        print("Different app in foreground; leaving TV unchanged")
    print("webOS applications installed successfully")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
        print(f"auto-tv-deploy: {error}", file=sys.stderr)
        sys.exit(1)
