"""Data-only manifest for the existing node-owned MCP provider registry.

Ansible publishes the verified output to /etc/gway-mcp-providers/webos.json.
This module never installs, registers or starts a provider.
"""

import argparse
import json
import re
from pathlib import Path


def manifest(release):
    release = Path(release).resolve(strict=True)
    if not re.fullmatch(r"[0-9a-f]{40}", release.name):
        raise ValueError("release must be a pinned SHA directory")
    executable = release / "bin" / "webos-mcp"
    if executable.is_symlink() or not executable.is_file() or not executable.stat().st_mode & 0o111:
        raise ValueError("installed MCP executable missing")
    return {"source_id": "webos", "revision": release.name,
            "executable": str(executable), "argv": [str(executable)]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", required=True)
    args = parser.parse_args()
    print(json.dumps(manifest(args.release), sort_keys=True))


if __name__ == "__main__":
    main()
