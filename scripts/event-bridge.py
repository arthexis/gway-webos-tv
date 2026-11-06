#!/usr/bin/env python3
"""Run the webOS paired event bridge."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gway_webos_tv.event_bridge import main  # noqa: E402

if __name__ == "__main__":
    main()
