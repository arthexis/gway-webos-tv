"""Private image cache grouped into capture sessions separated by five-minute gaps."""

import base64
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps

LIMIT = 10
SET_SECONDS = 300
MAX_INPUT = 25 * 1024 * 1024


def roll_dir():
    return (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        / "gway-webos-tv"
        / "image-roll"
    )


def _metadata(path):
    try:
        nanoseconds = int(path.stem.split("-")[0])
        recorded = nanoseconds / 1_000_000_000
    except (ValueError, IndexError):
        return None
    try:
        data = json.loads(path.with_suffix(".json").read_text())
        filename = data.get("filename")
    except (OSError, ValueError, AttributeError):
        filename = None
    if not isinstance(filename, str) or not filename or len(filename) > 255:
        filename = path.name
    return {
        "id": path.stem,
        "filename": filename,
        "captured_at": datetime.fromtimestamp(recorded, timezone.utc).isoformat(),
        "_time": recorded,
        "_path": path,
    }


def _sets(directory):
    entries = sorted(
        filter(None, (_metadata(p) for p in directory.glob("*.jpg"))), key=lambda x: x["_time"]
    )
    grouped = []
    for entry in entries:
        if not grouped or entry["_time"] - grouped[-1][-1]["_time"] >= SET_SECONDS:
            grouped.append([])
        grouped[-1].append(entry)
    return list(reversed([list(reversed(group)) for group in grouped]))


def add_image(path, directory=None, *, filename=None, captured_at=None):
    directory = directory or roll_dir()
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_INPUT:
        raise ValueError("Image unavailable or too large")
    with Image.open(path) as source:
        source.seek(0)
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((1920, 1080))
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".image-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as output:
            image.save(output, "JPEG", quality=82, optimize=True)
        timestamp_ns = time.time_ns() if captured_at is None else int(captured_at * 1_000_000_000)
        target = directory / f"{timestamp_ns}-{os.urandom(4).hex()}.jpg"
        label = Path(filename or path.name).name[:255]
        fd2, metadata = tempfile.mkstemp(prefix=".meta-", dir=directory)
        try:
            with os.fdopen(fd2, "w") as output:
                json.dump({"filename": label}, output)
            os.replace(metadata, target.with_suffix(".json"))
            os.replace(name, target)
        finally:
            Path(metadata).unlink(missing_ok=True)
        for group in _sets(directory)[LIMIT:]:
            for entry in group:
                entry["_path"].unlink(missing_ok=True)
                entry["_path"].with_suffix(".json").unlink(missing_ok=True)
    finally:
        Path(name).unlink(missing_ok=True)


def images(directory=None):
    groups = _sets(directory or roll_dir())[:LIMIT]
    return [
        [{k: v for k, v in entry.items() if not k.startswith("_")} for entry in group]
        for group in groups
    ]


def image_data(image_id, directory=None):
    if not isinstance(image_id, str) or not image_id.replace("-", "").isalnum():
        return None
    directory = directory or roll_dir()
    # Only expose an image that belongs to a currently retained set.
    for group in _sets(directory)[:LIMIT]:
        for entry in group:
            if entry["id"] == image_id:
                try:
                    data = entry["_path"].read_bytes()
                    if len(data) <= 4 * 1024 * 1024:
                        return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")
                except OSError:
                    return None
    return None
