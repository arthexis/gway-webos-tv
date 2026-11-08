"""Offline-only wheelhouse verifier; no installation or network access.

The operator prepares a wheelhouse separately using a reviewed lock. This
verifier checks every pinned wheel hash and the application's presence before
any release staging is allowed.
"""
import argparse
import hashlib
from pathlib import Path
import re

ENTRY = re.compile(r"^([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+!-]+)\s+--hash=sha256:([0-9a-f]{64})$")


def verify(lockfile, wheelhouse):
    lockfile, wheelhouse = Path(lockfile), Path(wheelhouse)
    if lockfile.is_symlink() or wheelhouse.is_symlink() or not wheelhouse.is_dir():
        raise ValueError("unsafe wheelhouse")
    lines = lockfile.read_text().splitlines()
    if not lines or lines[0].strip() != "--require-hashes":
        raise ValueError("hash mode required")
    packages = set()
    for line in lines[1:]:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = ENTRY.fullmatch(line)
        if not match:
            raise ValueError("unsupported lock entry")
        name, version, digest = match.groups()
        normalized = name.lower().replace("-", "_").replace(".", "_")
        if normalized in packages:
            raise ValueError("duplicate package")
        packages.add(normalized)
        candidates = [p for p in wheelhouse.iterdir() if p.is_file() and not p.is_symlink()
                      and p.suffix == ".whl" and p.name.lower().startswith(normalized + "-" + version.lower() + "-")]
        if not candidates or not any(hashlib.sha256(p.read_bytes()).hexdigest() == digest for p in candidates):
            raise ValueError("missing or mismatched wheel: " + name)
    if "gway_webos_tv" not in packages:
        raise ValueError("missing application wheel")
    if not packages:
        raise ValueError("empty lock")
    return len(packages)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lockfile", required=True)
    parser.add_argument("--wheelhouse", required=True)
    args = parser.parse_args()
    print(verify(args.lockfile, args.wheelhouse))


if __name__ == "__main__":
    main()
