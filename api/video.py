"""MP4 content checks without decoding: file type box and container duration."""
from __future__ import annotations

from pathlib import Path
import struct


class InvalidVideo(ValueError):
    pass


def mp4_duration_seconds(path: Path) -> float:
    """Validate that the file is an MP4 and return its movie-header duration."""

    with path.open("rb") as file:
        header = file.read(12)
        if len(header) < 12 or header[4:8] != b"ftyp":
            raise InvalidVideo("File is not an MP4 video.")
        file.seek(0, 2)
        size = file.tell()
        moov = _find_box(file, 0, size, b"moov")
        if moov is None:
            raise InvalidVideo("MP4 has no movie header.")
        mvhd = _find_box(file, *moov, b"mvhd")
        if mvhd is None:
            raise InvalidVideo("MP4 has no movie header.")
        file.seek(mvhd[0])
        version = file.read(4)[0]
        if version == 1:
            file.seek(16, 1)
            timescale, duration = struct.unpack(">IQ", file.read(12))
        else:
            file.seek(8, 1)
            timescale, duration = struct.unpack(">II", file.read(8))
    if timescale == 0:
        raise InvalidVideo("MP4 has an invalid timescale.")
    return duration / timescale


def _find_box(file, start: int, end: int, kind: bytes) -> tuple[int, int] | None:
    """Return (payload_start, payload_end) of the first child box of ``kind``."""

    position = start
    while position + 8 <= end:
        file.seek(position)
        size, box_type = struct.unpack(">I4s", file.read(8))
        header = 8
        if size == 1:
            size = struct.unpack(">Q", file.read(8))[0]
            header = 16
        elif size == 0:
            size = end - position
        if size < header:
            return None
        if box_type == kind:
            return position + header, position + size
        position += size
    return None
