from __future__ import annotations

import struct
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class AnchorForgeImageProbe:
    """Native image-header facts without third-party image libraries."""

    file_format: str = "unknown"
    width: int | None = None
    height: int | None = None
    color_mode: str = "unknown"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def probe_image_bytes(raw: bytes, source_name: str = "") -> AnchorForgeImageProbe:
    """Read basic native image geometry from bytes without decoding pixels."""

    warnings: list[str] = []
    if not raw:
        return AnchorForgeImageProbe(warnings=["empty image payload"])

    try:
        if raw.startswith(b"\x89PNG\r\n\x1a\n"):
            return _probe_png(raw)
        if raw.startswith((b"GIF87a", b"GIF89a")):
            return _probe_gif(raw)
        if raw.startswith(b"\xff\xd8"):
            return _probe_jpeg(raw)
        if raw.startswith(b"BM"):
            return _probe_bmp(raw)
        if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
            return _probe_webp(raw)
        if raw.startswith((b"II*\x00", b"MM\x00*")):
            return _probe_tiff(raw)
    except Exception as exc:
        warnings.append(f"anchorforge probe failed: {exc}")

    suffix = source_name.rsplit(".", 1)[-1].upper() if "." in source_name else "unknown"
    return AnchorForgeImageProbe(file_format=suffix, warnings=warnings or ["unsupported or incomplete image header"])


def _probe_png(raw: bytes) -> AnchorForgeImageProbe:
    if len(raw) < 33 or raw[12:16] != b"IHDR":
        return AnchorForgeImageProbe(file_format="PNG", warnings=["missing PNG IHDR header"])
    width, height = struct.unpack(">II", raw[16:24])
    bit_depth = raw[24]
    color_type = raw[25]
    color_map = {
        0: "L",
        2: "RGB",
        3: "P",
        4: "LA",
        6: "RGBA",
    }
    mode = color_map.get(color_type, f"PNG_COLOR_{color_type}")
    if bit_depth not in {1, 2, 4, 8, 16}:
        mode = f"{mode}/{bit_depth}bit"
    return AnchorForgeImageProbe(file_format="PNG", width=width, height=height, color_mode=mode)


def _probe_gif(raw: bytes) -> AnchorForgeImageProbe:
    if len(raw) < 10:
        return AnchorForgeImageProbe(file_format="GIF", warnings=["incomplete GIF header"])
    width, height = struct.unpack("<HH", raw[6:10])
    return AnchorForgeImageProbe(file_format="GIF", width=width, height=height, color_mode="P")


def _probe_bmp(raw: bytes) -> AnchorForgeImageProbe:
    if len(raw) < 30:
        return AnchorForgeImageProbe(file_format="BMP", warnings=["incomplete BMP header"])
    dib_size = struct.unpack("<I", raw[14:18])[0]
    if dib_size == 12 and len(raw) >= 26:
        width, height = struct.unpack("<HH", raw[18:22])
        bits = struct.unpack("<H", raw[24:26])[0]
    elif dib_size >= 40 and len(raw) >= 30:
        width, height = struct.unpack("<ii", raw[18:26])
        bits = struct.unpack("<H", raw[28:30])[0]
        height = abs(height)
    else:
        return AnchorForgeImageProbe(file_format="BMP", warnings=[f"unsupported BMP DIB header: {dib_size}"])
    mode = "RGBA" if bits == 32 else "RGB" if bits in {16, 24} else f"{bits}bit"
    return AnchorForgeImageProbe(file_format="BMP", width=abs(width), height=height, color_mode=mode)


def _probe_jpeg(raw: bytes) -> AnchorForgeImageProbe:
    offset = 2
    sof_markers = set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0))
    while offset + 4 <= len(raw):
        if raw[offset] != 0xFF:
            offset += 1
            continue
        while offset < len(raw) and raw[offset] == 0xFF:
            offset += 1
        if offset >= len(raw):
            break
        marker = raw[offset]
        offset += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if offset + 2 > len(raw):
            break
        segment_length = struct.unpack(">H", raw[offset:offset + 2])[0]
        if segment_length < 2 or offset + segment_length > len(raw):
            break
        if marker in sof_markers and segment_length >= 7:
            precision = raw[offset + 2]
            height, width = struct.unpack(">HH", raw[offset + 3:offset + 7])
            components = raw[offset + 7] if segment_length >= 8 else 0
            mode = {1: "L", 3: "YCbCr", 4: "CMYK"}.get(components, f"{components}components")
            if precision != 8:
                mode = f"{mode}/{precision}bit"
            return AnchorForgeImageProbe(file_format="JPEG", width=width, height=height, color_mode=mode)
        offset += segment_length
    return AnchorForgeImageProbe(file_format="JPEG", warnings=["JPEG SOF geometry marker not found"])


def _probe_webp(raw: bytes) -> AnchorForgeImageProbe:
    offset = 12
    while offset + 8 <= len(raw):
        chunk_type = raw[offset:offset + 4]
        chunk_size = struct.unpack("<I", raw[offset + 4:offset + 8])[0]
        data_start = offset + 8
        data_end = data_start + chunk_size
        if data_end > len(raw):
            return AnchorForgeImageProbe(file_format="WEBP", warnings=["incomplete WEBP chunk"])
        data = raw[data_start:data_end]
        if chunk_type == b"VP8X" and len(data) >= 10:
            width = 1 + int.from_bytes(data[4:7], "little")
            height = 1 + int.from_bytes(data[7:10], "little")
            return AnchorForgeImageProbe(file_format="WEBP", width=width, height=height, color_mode="RGBA" if data[0] & 0x10 else "RGB")
        if chunk_type == b"VP8L" and len(data) >= 5 and data[0] == 0x2F:
            bits = int.from_bytes(data[1:5], "little")
            width = 1 + (bits & 0x3FFF)
            height = 1 + ((bits >> 14) & 0x3FFF)
            return AnchorForgeImageProbe(file_format="WEBP", width=width, height=height, color_mode="RGBA")
        if chunk_type == b"VP8 " and len(data) >= 10 and data[3:6] == b"\x9d\x01\x2a":
            width = struct.unpack("<H", data[6:8])[0] & 0x3FFF
            height = struct.unpack("<H", data[8:10])[0] & 0x3FFF
            return AnchorForgeImageProbe(file_format="WEBP", width=width, height=height, color_mode="RGB")
        offset = data_end + (chunk_size % 2)
    return AnchorForgeImageProbe(file_format="WEBP", warnings=["WEBP geometry chunk not found"])


def _probe_tiff(raw: bytes) -> AnchorForgeImageProbe:
    endian = "<" if raw.startswith(b"II") else ">"
    if len(raw) < 8:
        return AnchorForgeImageProbe(file_format="TIFF", warnings=["incomplete TIFF header"])
    ifd_offset = struct.unpack(endian + "I", raw[4:8])[0]
    if ifd_offset + 2 > len(raw):
        return AnchorForgeImageProbe(file_format="TIFF", warnings=["TIFF IFD offset outside payload"])
    entry_count = struct.unpack(endian + "H", raw[ifd_offset:ifd_offset + 2])[0]
    width: int | None = None
    height: int | None = None
    bits: int | None = None
    entries_start = ifd_offset + 2
    for index in range(entry_count):
        start = entries_start + index * 12
        if start + 12 > len(raw):
            break
        tag, field_type, count = struct.unpack(endian + "HHI", raw[start:start + 8])
        value_bytes = raw[start + 8:start + 12]
        value = _tiff_inline_value(value_bytes, endian, field_type)
        if tag == 256:
            width = value
        elif tag == 257:
            height = value
        elif tag == 258:
            bits = value
    mode = "RGB" if bits in {8, 16} else f"{bits}bit" if bits else "unknown"
    return AnchorForgeImageProbe(file_format="TIFF", width=width, height=height, color_mode=mode)


def _tiff_inline_value(value_bytes: bytes, endian: str, field_type: int) -> int | None:
    if field_type == 3:
        return struct.unpack(endian + "H", value_bytes[:2])[0]
    if field_type == 4:
        return struct.unpack(endian + "I", value_bytes)[0]
    return None
