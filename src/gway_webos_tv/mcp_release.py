"""Prepare a pinned MCP release atomically, without touching the active manifest.

Offline-testable transaction. Requires a pre-provisioned, hash-locked wheelhouse:
no dependency resolution from the network is allowed.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

SHA = re.compile(r"^[0-9a-f]{40}$")


def run(argv):
    subprocess.run(argv, check=True, env={**os.environ, "PIP_NO_INDEX": "1"})


def stage(source, root, revision, requirements, wheelhouse, *, runner=run):
    if any(Path(value).is_symlink() for value in (source, root, requirements, wheelhouse)):
        raise ValueError("symlinked staging input")
    source, root = Path(source).resolve(strict=True), Path(root).resolve(strict=True)
    requirements, wheelhouse = Path(requirements).resolve(strict=True), Path(wheelhouse).resolve(strict=True)
    if not SHA.fullmatch(revision) or not (source / "pyproject.toml").is_file():
        raise ValueError("invalid pinned release")
    if not requirements.is_file() or requirements.is_symlink() or not wheelhouse.is_dir() or wheelhouse.is_symlink():
        raise ValueError("trusted offline dependencies required")
    lock = requirements.read_text()
    if not lock.strip() or "--hash=sha256:" not in lock or "--require-hashes" not in lock:
        raise ValueError("hash-locked requirements required")
    if not any(line.strip().lower().startswith("gway-webos-tv==") for line in lock.splitlines()):
        raise ValueError("application wheel must be included in hash lock")
    for line in lock.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line == "--require-hashes":
            continue
        if "==" not in line or "--hash=sha256:" not in line or any(x in line for x in ("git+", "http:", "https:", "-e ")):
            raise ValueError("unpinned or remote dependency")
    releases = root / "releases"
    if releases.is_symlink() or not releases.is_dir():
        raise ValueError("unsafe releases directory")
    destination = releases / revision
    if destination.is_symlink():
        raise ValueError("symlinked release")
    if destination.exists():
        if not (destination / "bin/webos-mcp").is_file():
            raise ValueError("incomplete existing release")
        return False
    # Use a staged tree; the launcher resolves Python by the final path, not
    # by the staging venv's absolute console-script shebang.
    staging = Path(tempfile.mkdtemp(prefix=".webos-stage-", dir=releases))
    try:
        runner([sys.executable, "-m", "venv", str(staging)])
        python = staging / "bin/python"
        runner([str(python), "-m", "pip", "install", "--no-index", "--find-links", str(wheelhouse),
                "--require-hashes", "-r", str(requirements)])
        # Require the reviewed application wheel itself in the offline lock.
        # Installing source here would invoke an unpinned build backend.
        runner([str(python), "-m", "pip", "check"])
        launcher = staging / "bin/webos-mcp"
        launcher.write_text("#!/bin/sh\nexec \"$(dirname \"$0\")/python\" -m gway_webos_tv.mcp_stdio \"$@\"\n")
        launcher.chmod(0o755)
        runner([str(python), "-c", "import gway_webos_tv.mcp_stdio"])
        # Atomic promotion: no partial final release on install failure.
        staging.rename(destination)
        return True
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main():
    parser = argparse.ArgumentParser()
    for name in ("source", "root", "revision", "requirements", "wheelhouse"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    stage(args.source, args.root, args.revision, args.requirements, args.wheelhouse)


if __name__ == "__main__":
    main()
