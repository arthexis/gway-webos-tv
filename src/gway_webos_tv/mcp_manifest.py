"""Render the node-owned MCP provider manifest for an installed executable."""

import argparse
import json
import re
from pathlib import Path


def manifest(revision, executable):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("revision must be a full commit SHA")
    executable = Path(executable)
    if (executable.is_symlink() or not executable.is_file()
            or not executable.stat().st_mode & 0o111):
        raise ValueError("installed MCP executable missing")
    return {"source_id": "webos", "revision": revision,
            "executable": str(executable), "argv": [str(executable)]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", required=True)
    parser.add_argument("--executable", required=True)
    args = parser.parse_args()
    print(json.dumps(manifest(args.revision, args.executable), sort_keys=True))


if __name__ == "__main__":
    main()
