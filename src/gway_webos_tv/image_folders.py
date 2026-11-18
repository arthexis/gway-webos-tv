"""Import newly written images from explicitly configured local folders."""

import fcntl
import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path

from .image_roll import add_image, roll_dir


def config_path():
    return (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        / "gway-webos-tv"
        / "image-folders.json"
    )


def scan_folders(config=None, directory=None, now=None):
    directory = directory or roll_dir()
    now = time.time() if now is None else now
    try:
        settings = json.loads((config or config_path()).read_text())
        folders = settings["folders"]
        if not isinstance(folders, list):
            return
    except (OSError, ValueError, KeyError, TypeError):
        return
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (directory / ".lock").open("a") as lock:
        os.chmod(directory / ".lock", 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        db_path = directory / ".folder-index.sqlite"
        fd = os.open(db_path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        with sqlite3.connect(db_path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS seen (fingerprint TEXT PRIMARY KEY, seen_at REAL NOT NULL)"
            )
            pending = []
            scheduled = set()
            for setting in folders:
                if not isinstance(setting, dict) or not isinstance(setting.get("path"), str):
                    continue
                root = Path(setting["path"]).expanduser()
                since = setting.get("since", 0)
                if (
                    not root.is_absolute()
                    or root.is_symlink()
                    or not root.is_dir()
                    or not isinstance(since, (int, float))
                ):
                    continue
                for current, dirs, files in os.walk(root, followlinks=False):
                    dirs[:] = [d for d in dirs if not (Path(current) / d).is_symlink()]
                    for name in files:
                        path = Path(current) / name
                        if (
                            path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp")
                            or path.is_symlink()
                        ):
                            continue
                        try:
                            stat = path.stat()
                            if (
                                not path.is_file()
                                or stat.st_mtime < since
                                or stat.st_mtime > now - 2
                            ):
                                continue
                            digest = hashlib.sha256(
                                (
                                    str(path)
                                    + "\0"
                                    + str(stat.st_mtime_ns)
                                    + "\0"
                                    + str(stat.st_size)
                                ).encode()
                            ).hexdigest()
                            if (
                                digest not in scheduled
                                and db.execute(
                                    "SELECT 1 FROM seen WHERE fingerprint=?", (digest,)
                                ).fetchone()
                                is None
                            ):
                                pending.append((stat.st_mtime, path, digest))
                                scheduled.add(digest)
                        except OSError:
                            continue
            for stamp, path, digest in sorted(pending):
                try:
                    add_image(path, directory, captured_at=stamp)
                    db.execute("INSERT OR IGNORE INTO seen VALUES (?, ?)", (digest, now))
                except (OSError, ValueError):
                    continue
            db.execute(
                "DELETE FROM seen WHERE fingerprint NOT IN (SELECT fingerprint FROM seen ORDER BY seen_at DESC LIMIT 20000)"
            )
