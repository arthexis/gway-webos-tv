#!/usr/bin/env python3
"""Add explicit local images to the private GWAY Monitor image roll."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gway_webos_tv.image_roll import add_image  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("images", nargs="+", type=Path)
args = parser.parse_args()
for image in args.images:
    add_image(image)
print(f"Added {len(args.images)} image(s).")
