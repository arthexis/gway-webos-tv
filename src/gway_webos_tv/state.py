"""Owner-only pairing state, compatible with the initial host-local TV pairing."""

import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


class TVError(Exception):
    """An operator-facing error safe to print."""


PERMISSIONS = [
    "LAUNCH",
    "CONTROL_AUDIO",
    "CONTROL_DISPLAY",
    "CONTROL_INPUT_TV",
    "CONTROL_INPUT_TEXT",
    "CONTROL_MOUSE_AND_KEYBOARD",
    "READ_INPUT_DEVICE_LIST",
    "READ_INSTALLED_APPS",
    "READ_RUNNING_APPS",
]


def default_manifest() -> dict:
    return {
        "manifestVersion": 1,
        "appVersion": "1.0",
        "appId": "org.arthexis.gway.tv",
        "localizedAppNames": {"": "GWAY TV"},
        "permissions": list(PERMISSIONS),
    }


def default_state_path() -> Path:
    if path := os.environ.get("GWAY_TV_STATE"):
        return Path(path).expanduser()
    base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
    current = base / "gway-webos-tv/device.json"
    if current.exists():
        return current
    legacy = sorted((base / "webos-tv").glob("*.json"))
    if len(legacy) == 1:
        return legacy[0]  # Reuse an existing pairing in place; do not copy its key.
    return current


@dataclass
class Device:
    host: str
    client_key: str | None = field(default=None, repr=False)
    fingerprint: str | None = None
    model: str | None = None
    manifest: dict = field(default_factory=default_manifest, repr=False)


def load_state(path: Path, *, required: bool = True) -> Device | None:
    try:
        with path.open() as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise TVError("Pairing state must be a regular file.")
            if info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise TVError("Pairing state must be owned by this user with mode 0600.")
            data = json.load(stream)
    except FileNotFoundError:
        if required:
            raise TVError("No saved pairing. Run gway-tv --host TV_ADDRESS pair first.") from None
        return None
    except (OSError, ValueError):
        raise TVError("Cannot read pairing state; check the file and permissions.") from None
    if not isinstance(data, dict):
        raise TVError("Invalid pairing state.")
    host, key, fingerprint = data.get("ip"), data.get("client-key"), data.get("certificate_sha256")
    if not isinstance(host, str) or not isinstance(key, str) or not key:
        raise TVError("Pairing state is missing the TV address or client key.")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", fingerprint):
        raise TVError("Pairing state must contain a SHA-256 certificate fingerprint.")
    manifest = data.get("manifest", default_manifest())
    if not isinstance(manifest, dict) or not isinstance(manifest.get("permissions"), list):
        raise TVError("Invalid pairing manifest.")
    return Device(host, key, fingerprint.lower(), data.get("model"), manifest)


def save_state(path: Path, device: Device) -> None:
    if not device.client_key or not device.fingerprint:
        raise TVError("Refusing to save incomplete pairing state.")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    data = {
        "ip": device.host,
        "client-key": device.client_key,
        "certificate_sha256": device.fingerprint,
        "model": device.model,
        "manifest": device.manifest,
    }
    fd, temporary = tempfile.mkstemp(prefix=".device-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
