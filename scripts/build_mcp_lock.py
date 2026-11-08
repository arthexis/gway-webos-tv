"""Generate a real-hash offline lock from an operator-reviewed wheelhouse.

No network, package installation or TV access. Dependency closure is checked
with packaging.Requirement markers against the target Python environment.
"""
import argparse
import hashlib
from email.parser import Parser
from pathlib import Path
import re
from zipfile import ZipFile

from packaging.tags import sys_tags
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name, parse_wheel_filename


def build_lock(wheelhouse):
    wheelhouse = Path(wheelhouse)
    if wheelhouse.is_symlink() or not wheelhouse.is_dir():
        raise ValueError("unsafe wheelhouse")
    wheels = {}
    compatible_tags = set(sys_tags())
    for wheel in sorted(wheelhouse.iterdir()):
        if wheel.is_symlink() or not wheel.is_file() or wheel.suffix != ".whl":
            raise ValueError("wheelhouse must contain only regular wheels")
        name, version, _, wheel_tags = parse_wheel_filename(wheel.name)
        if not wheel_tags & compatible_tags:
            raise ValueError("incompatible wheel for current Python/platform: " + wheel.name)
        key = canonicalize_name(name)
        if key in wheels:
            raise ValueError("multiple wheels for package " + key)
        with ZipFile(wheel) as archive:
            metadata_paths = [p for p in archive.namelist() if p.endswith(".dist-info/METADATA")]
            if len(metadata_paths) != 1:
                raise ValueError("invalid wheel metadata")
            metadata = Parser().parsestr(archive.read(metadata_paths[0]).decode())
        wheels[key] = (str(version), hashlib.sha256(wheel.read_bytes()).hexdigest(), metadata)
    if "gway-webos-tv" not in wheels:
        raise ValueError("application wheel missing")
    for name, (_, _, metadata) in wheels.items():
        for item in metadata.get_all("Requires-Dist", []):
            requirement = Requirement(item)
            if requirement.marker and not requirement.marker.evaluate({"extra": ""}):
                continue
            dependency = canonicalize_name(requirement.name)
            if dependency not in wheels:
                raise ValueError("missing transitive dependency: " + dependency)
            if wheels[dependency][0] not in requirement.specifier:
                raise ValueError("incompatible transitive dependency: " + dependency)
    lines = ["--require-hashes"]
    for name, (version, digest, _) in sorted(wheels.items()):
        lines.append(f"{name}=={version} --hash=sha256:{digest}")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheelhouse", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = build_lock(args.wheelhouse)
    output = Path(args.output)
    if output.is_symlink():
        raise ValueError("symlinked output")
    output.write_text(result)


if __name__ == "__main__":
    main()
