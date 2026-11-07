"""Generate distinct webOS launcher icons using only Python's standard library.

The build writes icons to the temporary staging directory, never to source.
"""
import struct
import zlib
from pathlib import Path

SIZE = 160
COLORS = {
    "gway-monitor": ((14, 42, 55), (104, 233, 185)),
    "remote-test": ((23, 39, 75), (112, 181, 255)),
}


def generate_icon(name, destination):
    if name not in COLORS:
        return False
    bg, fg = COLORS[name]
    pixels = bytearray(bg * (SIZE * SIZE))

    def put(x, y, color=fg):
        if 0 <= x < SIZE and 0 <= y < SIZE:
            p = (y * SIZE + x) * 3
            pixels[p:p + 3] = bytes(color)

    def thick_line(x0, y0, x1, y1, radius=5):
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        for step in range(steps + 1):
            x = round(x0 + (x1 - x0) * step / steps)
            y = round(y0 + (y1 - y0) * step / steps)
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if dx * dx + dy * dy <= radius * radius:
                        put(x + dx, y + dy)

    if name == "gway-monitor":
        # Bright pulse trace inside a rounded screen frame.
        for x in range(24, 137):
            for y in (35, 124):
                put(x, y)
        for y in range(35, 125):
            for x in (24, 136):
                put(x, y)
        for a, b in zip([(32, 85), (54, 85), (69, 56), (86, 108), (102, 78)],
                        [(54, 85), (69, 56), (86, 108), (102, 78), (127, 78)]):
            thick_line(*a, *b, radius=4)
    else:
        # Gamepad silhouette with D-pad and distinct round action buttons.
        for y in range(57, 109):
            for x in range(25, 135):
                if ((x - 80) / 57) ** 2 + ((y - 83) / 30) ** 2 <= 1:
                    put(x, y, (49, 82, 125))
        thick_line(46, 82, 72, 82, 5)
        thick_line(59, 69, 59, 95, 5)
        for cx, cy in ((104, 74), (119, 87)):
            for dy in range(-7, 8):
                for dx in range(-7, 8):
                    if dx * dx + dy * dy <= 49:
                        put(cx + dx, cy + dy)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)

    scanlines = b"".join(b"\x00" + pixels[y * SIZE * 3:(y + 1) * SIZE * 3] for y in range(SIZE))
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(scanlines, 9))
    png += chunk(b"IEND", b"")
    Path(destination).write_bytes(png)
    return True
