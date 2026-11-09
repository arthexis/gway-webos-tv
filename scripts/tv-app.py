#!/usr/bin/env python3
"""Package a webOS app and optionally install or launch it on a paired TV."""

import argparse
import hashlib
import importlib.util
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



MANIFEST_SCHEMA = "gway-webos-tv/app-build/v1"
INJECTION_POINT = "var url = localStorage.getItem('gway.bridge.url') || '';"
APP_NAME = re.compile(r"[a-z0-9][a-z0-9-]*\Z")
APP_ID = re.compile(r"[a-z0-9]+(?:[.-][a-z0-9]+)+\Z")
VERSION = re.compile(r"\d+\.\d+\.\d+\Z")


def discover_apps(apps_root=None):
    """Discover only directories with a valid build manifest."""
    root = apps_root or ROOT / "apps"
    return sorted(
        p.name for p in root.iterdir()
        if p.is_dir() and not p.is_symlink() and (p / "manifest.json").is_file()
    )


def safe_relative_path(value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("Invalid manifest relative path")
    candidate = Path(value)
    if candidate.is_absolute() or any(p in (".", "..") for p in value.split("/")):
        raise ValueError("Unsafe manifest relative path")
    if not all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in value.split("/")):
        raise ValueError("Invalid manifest path component")
    return candidate


def load_manifest(source):
    """Validate local build metadata independently from webOS appinfo.json."""
    if not source.is_dir() or source.is_symlink():
        raise ValueError("App directory missing")
    if any(p.is_symlink() for p in source.rglob("*")):
        raise ValueError("App directory contains symlinks")
    path = source / "manifest.json"
    manifest = json.loads(path.read_text())
    if not isinstance(manifest, dict) or set(manifest) != {"schema", "entry", "bridge"}:
        raise ValueError("Invalid build manifest fields")
    if manifest["schema"] != MANIFEST_SCHEMA:
        raise ValueError("Unsupported build manifest schema")
    entry = safe_relative_path(manifest["entry"])
    if not (source / entry).is_file():
        raise ValueError("Manifest entry file missing")
    bridge = manifest["bridge"]
    if not isinstance(bridge, dict) or bridge.get("mode") not in ("none", "inject"):
        raise ValueError("Invalid bridge configuration")
    if bridge["mode"] == "none":
        if set(bridge) != {"mode"}:
            raise ValueError("Unexpected bridge fields")
    else:
        if set(bridge) != {"mode", "file", "config_key"} or bridge["config_key"] != "bridge_url":
            raise ValueError("Invalid bridge injection contract")
        target = source / safe_relative_path(bridge["file"])
        if not target.is_file() or target.suffix != ".js":
            raise ValueError("Bridge injection target missing")
        if target.read_text().count(INJECTION_POINT) != 1:
            raise ValueError("App endpoint injection point is missing or ambiguous")
    meta = json.loads((source / "appinfo.json").read_text())
    if not isinstance(meta, dict) or not isinstance(meta.get("id"), str) or not APP_ID.fullmatch(meta["id"]):
        raise ValueError("Invalid app ID")
    if not isinstance(meta.get("version"), str) or not VERSION.fullmatch(meta["version"]):
        raise ValueError("Invalid app version")
    if meta.get("main") != manifest["entry"]:
        raise ValueError("Manifest entry does not match webOS main")
    return manifest, meta


def source_revision():
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        capture_output=True, text=True, check=True
    ).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Invalid source revision")
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    if dirty.strip():
        raise ValueError("Cannot attest build from a dirty source tree")
    return revision


def stage_app(source, staged, manifest, config):
    revision = source_revision()
    shutil.copytree(source, staged)
    (staged / "manifest.json").unlink()
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Invalid source revision')
    (staged / 'gway-build.json').write_text(json.dumps({'schema': 1, 'git_sha': revision, 'build_id': revision[:16]}, sort_keys=True) + '\n')
    icon_spec = importlib.util.spec_from_file_location("launcher_icons", ROOT / "scripts/launcher_icons.py")
    icon_module = importlib.util.module_from_spec(icon_spec)
    icon_spec.loader.exec_module(icon_module)
    icon_module.generate_icon(source.name, staged / "icon.png")
    bridge = manifest["bridge"]
    if bridge["mode"] == "inject":
        url = endpoint_from_config(config.expanduser())
        target = staged / safe_relative_path(bridge["file"])
        contents = target.read_text()
        if contents.count(INJECTION_POINT) != 1:
            raise ValueError("App endpoint injection point is missing or ambiguous")
        target.write_text(contents.replace(
            INJECTION_POINT,
            "var url = localStorage.getItem('gway.bridge.url') || " + json.dumps(url) + ";"
        ))


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
    p.add_argument("apps", nargs="*", default=None, help="App directory names in apps/, or all")
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
        selected = args.apps or ["remote-test"]
        if "all" in selected:
            if len(selected) != 1:
                raise ValueError("all cannot be combined with app names")
            selected = discover_apps()
        if len(set(selected)) != len(selected):
            raise ValueError("Duplicate app selection")
        if args.launch and len(selected) != 1:
            raise ValueError("--launch requires exactly one selected app")
        if args.install:
            verify_device(args.device, args.host)
        for app in selected:
            if not APP_NAME.fullmatch(app):
                raise ValueError("Use an app directory name from apps/")
            source = ROOT / "apps" / app
            manifest, meta = load_manifest(source)
            app_id, version = meta["id"], meta["version"]
            with tempfile.TemporaryDirectory(prefix="gway-webos-build-") as temporary:
                root = Path(temporary)
                staged = root / "app"
                revision = source_revision()
                stage_app(source, staged, manifest, args.config)
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
            digest = hashlib.sha256(destination.read_bytes()).hexdigest()
            sidecar = destination.with_name(destination.name + '.sha256.json')
            metadata = {'schema': 1, 'app_id': app_id, 'version': version,
                        'git_sha': revision, 'build_id': revision[:16], 'ipk_sha256': digest}
            fd, temporary_metadata = tempfile.mkstemp(prefix='.webos-build-', dir=args.output_dir)
            try:
                with os.fdopen(fd, 'w') as stream:
                    json.dump(metadata, stream, sort_keys=True)
                    stream.write('\\n')
                os.replace(temporary_metadata, sidecar)
            finally:
                if os.path.exists(temporary_metadata):
                    os.unlink(temporary_metadata)
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
