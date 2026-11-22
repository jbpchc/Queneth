"""Identify JPEG/PNG/WebP by magic bytes and read their pixel size.

Used for local-disk uploads, where we can't rely on Cloudinary's checks.
The declared Content-Type is never trusted on its own.
"""

import struct
from dataclasses import dataclass


@dataclass(frozen=True)
class ImageInfo:
    content_type: str
    ext: str
    width: int | None
    height: int | None


def sniff(data: bytes) -> ImageInfo | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return ImageInfo("image/png", "png", width, height)
    if data.startswith(b"\xff\xd8\xff"):
        w, h = _jpeg_size(data)
        return ImageInfo("image/jpeg", "jpg", w, h)
    if len(data) >= 30 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        w, h = _webp_size(data)
        return ImageInfo("image/webp", "webp", w, h)
    return None


def _jpeg_size(data: bytes) -> tuple[int | None, int | None]:
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        # SOF0–SOF15 except DHT (C4), JPG (C8) and DAC (CC) carry the frame size.
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack(">HH", data[i + 5 : i + 9])
            return width, height
        (length,) = struct.unpack(">H", data[i + 2 : i + 4])
        i += 2 + length
    return None, None


def _webp_size(data: bytes) -> tuple[int | None, int | None]:
    chunk = data[12:16]
    if chunk == b"VP8 " and len(data) >= 30:
        w, h = struct.unpack("<HH", data[26:30])
        return w & 0x3FFF, h & 0x3FFF
    if chunk == b"VP8L" and len(data) >= 25:
        b = data[21:25]
        width = 1 + (((b[1] & 0x3F) << 8) | b[0])
        height = 1 + (((b[3] & 0x0F) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
        return width, height
    if chunk == b"VP8X" and len(data) >= 30:
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return width, height
    return None, None
