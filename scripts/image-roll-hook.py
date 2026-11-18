#!/usr/bin/env python3
"""Collect image-bearing tool results into the private Monitor roll.

Only explicitly returned image blocks/data URLs and explicit screenshot file paths
are considered. Never print image content or tool arguments.
"""

import base64
import fcntl
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gway_webos_tv.image_roll import MAX_INPUT, add_image, roll_dir  # noqa: E402


def candidates(value):
    if isinstance(value, dict):
        if value.get("type") == "image" and isinstance(value.get("data"), str):
            yield ("base64", value["data"])
        for key, item in value.items():
            if (
                key in ("image_url", "url")
                and isinstance(item, str)
                and item.startswith("data:image/")
            ):
                yield ("dataurl", item)
            elif key in ("path", "file_path", "image_path", "output_path") and isinstance(
                item, str
            ):
                yield ("path", item)
            elif isinstance(item, (dict, list)):
                yield from candidates(item)
    elif isinstance(value, list):
        for item in value:
            yield from candidates(item)


def main():
    try:
        event = json.load(sys.stdin)
        directory = roll_dir()
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (directory / ".lock").open("a") as lock:
            os.chmod(directory / ".lock", 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX)
            seen = set()
            for kind, value in candidates(event.get("tool_response")):
                if kind == "path":
                    path = Path(value)
                    if not path.is_absolute() or path.suffix.lower() not in (
                        ".png",
                        ".jpg",
                        ".jpeg",
                        ".webp",
                    ):
                        continue
                    identity = ("path", str(path))
                    if identity not in seen:
                        add_image(path, directory)
                        seen.add(identity)
                else:
                    encoded = value.split(",", 1)[-1] if kind == "dataurl" else value
                    if len(encoded) > MAX_INPUT * 2 or not re.fullmatch(
                        r"[A-Za-z0-9+/=\s]+", encoded
                    ):
                        continue
                    raw = base64.b64decode(encoded, validate=True)
                    if len(raw) > MAX_INPUT:
                        continue
                    import hashlib

                    identity = ("data", hashlib.sha256(raw).digest())
                    if identity in seen:
                        continue
                    fd, name = tempfile.mkstemp(prefix=".incoming-", dir=directory)
                    try:
                        with os.fdopen(fd, "wb") as f:
                            f.write(raw)
                        add_image(
                            name,
                            directory,
                            filename="generated-"
                            + __import__("datetime").datetime.now().strftime("%Y%m%d-%H%M%S")
                            + ".png",
                        )
                    finally:
                        Path(name).unlink(missing_ok=True)
                    seen.add(identity)
    except Exception:
        # Image capture is best effort and must never break the originating tool.
        return


if __name__ == "__main__":
    main()
