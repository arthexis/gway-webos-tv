#!/usr/bin/env python3
"""Package a webOS app and optionally install or launch it on a paired TV."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
NODE = Path(
    os.environ.get(
        "WEBOS_NODE_BIN", Path.home() / ".local/opt/webos-node24/node_modules/node/bin/node"
    )
)
CLI = Path(
    os.environ.get(
        "WEBOS_CLI_DIR", Path.home() / ".local/opt/webos-tools/node_modules/@webos-tools/cli/bin"
    )
)


def command(tool, *args):
    env = os.environ.copy()
    env["NODE_OPTIONS"] = (env.get("NODE_OPTIONS", "") + " --no-addons").strip()
    if not NODE.is_file() or not (CLI / f"{tool}.js").is_file():
        raise ValueError("webOS CLI unavailable; configure WEBOS_NODE_BIN and WEBOS_CLI_DIR")
    result = subprocess.run(
        [str(NODE), str(CLI / f"{tool}.js"), *map(str, args)],
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if result.returncode:
        raise ValueError(f"{tool} failed; inspect the device and CLI before retrying")
    return result.stdout


def endpoint_from_config(path):
    config = json.loads(path.read_text())
    url = config.get("bridge_url") if isinstance(config, dict) else None
    if not isinstance(url, str):
        raise ValueError("Local configuration must contain bridge_url")
    parsed = urlsplit(url)
    if (
        parsed.scheme != "wss"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Bridge URL must be WSS with no credentials, query, or fragment")
    try:
        parsed.port
    except ValueError:
        raise ValueError("Invalid bridge URL port") from None
    return url


def tv_status(host):
    result = subprocess.run(
        ["tv", "--host", host, "--timeout", "10", "--json", "status"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    if result.returncode:
        raise ValueError("Paired TV status failed; verify the address and certificate pin")
    status = json.loads(result.stdout)
    if not status.get("connected") or not status.get("paired"):
        raise ValueError("TV is not connected and paired")
    return status


def verify_device(device, host):
    profile = json.loads((Path.home() / ".webos/tv/novacom-devices.json").read_text())
    matches = [x for x in profile if isinstance(x, dict) and x.get("name") == device]
    if len(matches) != 1 or matches[0].get("host") != host:
        raise ValueError("Device profile address does not match --host")
    status = tv_status(host)
    system = command("ares-device", "--device", device, "--system-info")
    match = re.search(r"^modelName\s*:\s*(.+)$", system, re.M)
    if not match or match.group(1).strip() != status.get("model"):
        raise ValueError("Developer profile and paired TV model do not match")
    print("Verified paired TV and developer profile")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("app", nargs="?", default="remote-test", help="App directory name in apps/")
    p.add_argument(
        "--config",
        type=Path,
        default=Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        / "gway-webos-tv/app-build.json",
    )
    p.add_argument("--output-dir", type=Path, default=ROOT / "dist/webos-apps")
    p.add_argument(
        "--replace", action="store_true", help="Replace an existing output package atomically"
    )
    p.add_argument(
        "--check", action="store_true", help="Only check the paired TV and developer profile"
    )
    p.add_argument("--install", action="store_true", help="Install the package on the selected TV")
    p.add_argument(
        "--launch", action="store_true", help="Launch and verify the app (requires --install)"
    )
    p.add_argument("--device", default="lab-tv", help="Configured webOS CLI device")
    p.add_argument("--host", help="Current address of the paired TV; required for --install")
    args = p.parse_args()
    try:
        if args.launch and not args.install:
            raise ValueError("--launch requires --install")
        if args.check and (args.install or args.launch):
            raise ValueError("--check cannot be combined with --install or --launch")
        if (args.install or args.check) and not args.host:
            raise ValueError("--check and --install require --host for pinned TV verification")
        if args.check:
            verify_device(args.device, args.host)
            return 0
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.app):
            raise ValueError("Use an app directory name from apps/")
        source = ROOT / "apps" / args.app
        if not source.is_dir() or any(x.is_symlink() for x in source.rglob("*")):
            raise ValueError("App directory missing or contains symlinks")
        meta = json.loads((source / "appinfo.json").read_text())
        app_id, version = meta["id"], meta["version"]
        if not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)+", app_id) or not re.fullmatch(
            r"\d+\.\d+\.\d+", version
        ):
            raise ValueError("Invalid app ID or version")
        if args.install:
            verify_device(args.device, args.host)
        with tempfile.TemporaryDirectory(prefix="gway-webos-build-") as temporary:
            root = Path(temporary)
            staged = root / "app"
            shutil.copytree(source, staged)
            if args.app in ("remote-test", "gway-monitor"):
                url = endpoint_from_config(args.config.expanduser())
                target = staged / "app.js"
                contents = target.read_text()
                old = "var url = localStorage.getItem('gway.bridge.url') || '';"
                if contents.count(old) != 1:
                    raise ValueError("App endpoint injection point is missing or ambiguous")
                target.write_text(
                    contents.replace(
                        old,
                        "var url = localStorage.getItem('gway.bridge.url') || "
                        + json.dumps(url)
                        + ";",
                    )
                )
            command("ares-package", "-o", root, staged)
            package = root / f"{app_id}_{version}_all.ipk"
            if not package.is_file():
                raise ValueError("Expected webOS package was not created")
            args.output_dir.mkdir(parents=True, exist_ok=True)
            destination = args.output_dir / package.name
            if args.replace:
                fd, temporary_output = tempfile.mkstemp(
                    prefix=".webos-package-", dir=args.output_dir
                )
                try:
                    with package.open("rb") as source_file, os.fdopen(fd, "wb") as output:
                        shutil.copyfileobj(source_file, output)
                    os.replace(temporary_output, destination)
                finally:
                    if os.path.exists(temporary_output):
                        os.unlink(temporary_output)
            else:
                with package.open("rb") as source_file, destination.open("xb") as output:
                    shutil.copyfileobj(source_file, output)
        print(f"Package: {destination}")
        if args.install:
            command("ares-install", "--device", args.device, destination)
            print("Installed on TV")
        if args.launch:
            command("ares-launch", "--device", args.device, app_id)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if tv_status(args.host).get("foreground_app") == app_id:
                    print("Confirmed app in TV foreground")
                    break
                time.sleep(1)
            else:
                raise ValueError("TV did not confirm the app in the foreground")
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as e:
        print(f"tv-app: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
