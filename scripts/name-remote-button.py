#!/usr/bin/env python3
"""Name the last key displayed by the running GWAY Remote Test app."""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gway_webos_tv.client import TV  # noqa: E402
from gway_webos_tv.remote_ocr import read_code  # noqa: E402
from gway_webos_tv.state import TVError, default_state_path, load_state  # noqa: E402

APP_ID = "com.arthexis.gway.remotetest"
DEFAULT_NAMES = {
    13: "OK / Enter",
    19: "Pause",
    37: "Left",
    38: "Up",
    39: "Right",
    40: "Down",
    403: "Red",
    404: "Green",
    405: "Yellow",
    406: "Blue",
    412: "Rewind",
    413: "Stop",
    415: "Play",
    417: "Fast forward",
    461: "Back",
}


async def capture(host):
    device = load_state(default_state_path())
    if host:
        device.host = host
    tv = TV(device, timeout=15)
    try:
        await tv.connect()
        if (await tv.status())["foreground_app"] != APP_ID:
            raise TVError("Open GWAY Remote Test on the TV first.")
        data, _ = await tv.capture()
        return data
    finally:
        await tv.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", help="Current address of the already paired TV")
    parser.add_argument("--ocr", action="store_true", help="Use the screenshot OCR fallback")
    args = parser.parse_args()
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = base / "gway-webos-tv" / "button-names.json"
    try:
        if args.ocr:
            data = asyncio.run(capture(args.host))
            try:
                code = read_code(data)
            except ValueError:
                value = input(
                    "Could not read the code. Enter the key code shown on the TV: "
                ).strip()
                if not re.fullmatch(r"[1-9][0-9]{0,4}", value):
                    raise ValueError("Enter the positive numeric code shown on the TV.") from None
                code = int(value)
        else:
            state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
            event = json.loads((state / "gway-webos-tv/bridge/last-button.json").read_text())
            code, received = event["code"], event["received_at"]
            if (
                type(code) is not int
                or not 1 <= code <= 65535
                or not isinstance(received, (float, int))
                or not 0 <= time.time() - received <= 300
            ):
                raise ValueError(
                    "Last button is invalid or older than five minutes; press it again."
                )
        names = json.loads(path.read_text()) if path.exists() else {}
        if not isinstance(names, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in names.items()
        ):
            raise ValueError("Invalid button names file.")
        current = names.get(str(code), DEFAULT_NAMES.get(code))
        print(f"Detected key code: {code}")
        print(f"Current name: {current or '(unnamed)'}")
        if input("Is this the intended key code? [y/N] ").strip().lower() != "y":
            print("Cancelled; no changes made.")
            return
        name = input("New name (leave blank to keep current): ").strip()
        if not name:
            print("No changes made.")
            return
        if len(name) > 100 or any(ord(c) < 32 for c in name):
            raise ValueError("Use a name of at most 100 printable characters.")
        names[str(code)] = name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".button-names-", dir=path.parent)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(names, stream, indent=2, ensure_ascii=False)
                stream.write("\n")
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        print(f"Saved name for key {code} in {path}.")
    except (
        TVError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
        EOFError,
    ) as error:
        print(f"Cannot register button: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
