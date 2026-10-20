"""Bounded camera JPEG decoding, executed in the isolated model process."""
import cv2
import numpy as np

from icare.inference.engine import EngineError

MAX_FRAME_BYTES = 1024 * 1024
MAX_FRAME_PIXELS = 1920 * 1080


class InvalidCameraFrame(EngineError):
    code = "invalid_frame"


def jpeg_dimensions(data: bytes) -> tuple[int, int]:
    if not data.startswith(b"\xff\xd8") or len(data) > MAX_FRAME_BYTES:
        raise InvalidCameraFrame("Expected a JPEG camera frame no larger than 1 MB.")
    offset = 2
    while offset + 4 <= len(data):
        if data[offset] != 255:
            break
        while offset < len(data) and data[offset] == 255:
            offset += 1
        if offset >= len(data):
            break
        marker = data[offset]
        offset += 1
        if marker in (0xD9, 0xDA):
            break
        size = int.from_bytes(data[offset:offset + 2], 'big')
        if size < 2 or offset + size > len(data):
            break
        if marker in (0xC0, 0xC1, 0xC2):
            if size < 8:
                break
            height = int.from_bytes(data[offset + 3:offset + 5], 'big')
            width = int.from_bytes(data[offset + 5:offset + 7], 'big')
            if min(width, height) < 1 or max(width, height) > 1920 or width * height > MAX_FRAME_PIXELS:
                raise InvalidCameraFrame("Camera frame dimensions exceed the supported limit.")
            return width, height
        offset += size
    raise InvalidCameraFrame("The camera frame has an invalid JPEG header.")


def decode_camera_frame(data: bytes):
    width, height = jpeg_dimensions(data)
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.shape[:2] != (height, width):
        raise InvalidCameraFrame("The camera frame could not be decoded.")
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
