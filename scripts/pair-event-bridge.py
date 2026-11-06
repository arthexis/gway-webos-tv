#!/usr/bin/env python3
"""Generate a single-use, short-lived code for TV bridge pairing."""

import hashlib
import secrets
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gway_webos_tv.event_bridge import state_directory, write_private  # noqa: E402

if not sys.stdout.isatty():
    raise SystemExit("Run this command in a private terminal; output redirection is disabled.")
code = f"{secrets.randbelow(1000000):06d}"
salt = secrets.token_hex(16)
write_private(
    state_directory() / "pending-pairing.json",
    {
        "sha256": hashlib.sha256((salt + code).encode()).hexdigest(),
        "salt": salt,
        "expires": time.time() + 120,
        "attempts_remaining": 5,
    },
)
print("Enter this code on the TV within two minutes:", code, flush=True)
