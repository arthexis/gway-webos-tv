#!/usr/bin/env python3
"""Generate a single-use, short-lived code for TV bridge pairing."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gway_webos_tv.event_bridge import open_local_pairing_window

if not sys.stdout.isatty():
    raise SystemExit("Run this command in a private terminal; output redirection is disabled.")
print("Enter this code on the TV within two minutes:", open_local_pairing_window(), flush=True)
