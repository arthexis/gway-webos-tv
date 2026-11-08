"""Data-only manifest for the existing node-owned MCP provider registry.

Ansible publishes the verified output to /etc/gway-mcp-providers/webos.json.
This module never installs, registers or starts a provider.
"""

import argparse
import json
import re
from pathlib import Path


def manifest(release=None, *, revision=None, executable=None):
    if release is not None:
        release = Path(release).resolve(strict=True)
        revision = release.name
        executable = release / "bin" / "webos-mcp"
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("release must be a pinned SHA directory")
    executable = Path(executable)
    if executable.is_symlink() or not executable.is_file() or not executable.stat().st_mode & 0o111:
        raise ValueError("installed MCP executable missing")
    return {"source_id": "webos", "revision": revision,
            "executable": str(executable), "argv": [str(executable)]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release")
    parser.add_argument("--revision")
    parser.add_argument("--executable")
    args = parser.parse_args()
    print(json.dumps(manifest(args.release, revision=args.revision, executable=args.executable), sort_keys=True))


if __name__ == "__main__":
    main()
