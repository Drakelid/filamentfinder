from __future__ import annotations

import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ICON_DIR = ROOT / "icons"
COLOR = (124, 58, 237)


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return (
        struct.pack("!I", len(data))
        + chunk_type
        + data
        + struct.pack("!I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def make_png(size: int, rgb: tuple[int, int, int]) -> bytes:
    width = height = size
    row = bytes(rgb) * width
    raw = b"".join(b"\x00" + row for _ in range(height))
    header = struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            png_chunk(b"IHDR", header),
            png_chunk(b"IDAT", zlib.compress(raw, 9)),
            png_chunk(b"IEND", b""),
        ]
    )


def main() -> None:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    for size in (16, 48, 128):
        target = ICON_DIR / f"icon{size}.png"
        target.write_bytes(make_png(size, COLOR))
        print(f"Wrote {target}")


if __name__ == "__main__":
    main()
