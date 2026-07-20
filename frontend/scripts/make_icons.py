"""
make_icons.py — Generate the extension's toolbar icons.

Placeholder artwork: an indigo rounded square with a white envelope. Written
with zlib/struct rather than Pillow so it runs with no dependencies. Replace
`public/icons/` with real artwork whenever design catches up.

    python scripts/make_icons.py
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

SIZES = (16, 32, 48, 128)
OUT_DIR = Path(__file__).resolve().parent.parent / "public" / "icons"

BG = (79, 70, 229)  # indigo-600
FG = (255, 255, 255)


def _rounded(x: int, y: int, size: int, radius: float) -> bool:
    """True if (x, y) falls inside a rounded square of `size`."""
    cx = min(x, size - 1 - x)
    cy = min(y, size - 1 - y)
    if cx >= radius or cy >= radius:
        return True
    dx = radius - cx
    dy = radius - cy
    return dx * dx + dy * dy <= radius * radius


def _envelope(x: int, y: int, size: int) -> bool:
    """True if (x, y) is part of the envelope glyph."""
    left, right = 0.22 * size, 0.78 * size
    top, bottom = 0.32 * size, 0.68 * size
    if not (left <= x <= right and top <= y <= bottom):
        return False

    stroke = max(1.0, size / 16)

    # Body outline.
    if (
        x - left < stroke
        or right - x < stroke
        or y - top < stroke
        or bottom - y < stroke
    ):
        return True

    # Flap: two diagonals from the top corners meeting at the centre.
    mid_x = (left + right) / 2
    span = mid_x - left
    if span > 0:
        progress = abs(x - mid_x) / span          # 1 at the edges, 0 at centre
        flap_y = top + (1 - progress) * (bottom - top) * 0.52
        if abs(y - flap_y) < stroke:
            return True

    return False


def _png(size: int) -> bytes:
    rows = bytearray()
    for y in range(size):
        rows.append(0)  # PNG filter type 0 for this scanline
        for x in range(size):
            if not _rounded(x, y, size, radius=size * 0.22):
                rows.extend((0, 0, 0, 0))  # transparent outside the corners
            elif _envelope(x, y, size):
                rows.extend((*FG, 255))
            else:
                rows.extend((*BG, 255))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for size in SIZES:
        path = OUT_DIR / f"icon-{size}.png"
        path.write_bytes(_png(size))
        print(f"wrote {path.relative_to(OUT_DIR.parent.parent)} ({path.stat().st_size} B)")


if __name__ == "__main__":
    main()
