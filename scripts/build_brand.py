"""Generate our simple mixer icon without external image dependencies."""

import struct
import zlib
from pathlib import Path


def make_icon(size: int) -> bytes:
    def pixel(x, y):
        x, y = x * 256 / size, y * 256 / size
        if not 16 <= x < 240 or not 16 <= y < 240:
            return (0, 0, 0, 0)
        color = (20, 31, 46, 255)
        for cx, cy in ((68, 92), (128, 160), (188, 116)):
            if cx - 3 <= x < cx + 3 and 52 <= y < 208:
                color = (88, 109, 126, 255)
            if cx - 17 <= x < cx + 17 and cy - 10 <= y < cy + 10:
                color = (65, 210, 195, 255)
        return color

    def chunk(kind, data):
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    rows = b"".join(
        b"\x00" + bytes(c for x in range(size) for c in pixel(x, y)) for y in range(size)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows, 9))
        + chunk(b"IEND", b"")
    )


if __name__ == "__main__":
    folder = Path(__file__).resolve().parents[1] / "custom_components/behringer_xair/brand"
    folder.mkdir(exist_ok=True)
    for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
        (folder / name).write_bytes(make_icon(size))
