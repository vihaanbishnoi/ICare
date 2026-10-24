"""Where falls happen in a room: fall location, per-fall picture and the room's danger zone.

With a fixed camera the same image position means the same spot in the room, so each
fall's position can be stored and many falls overlaid over time. Positions are image
coordinates normalised to 0..1 (x of width, y of height), not floor measurements, and
they only line up while the camera does not move.

The fall location is a heuristic read from the person's pose track, not a validated
measurement: ``onset`` is where they were standing when the descent began (useful for
trip hazards and bumps), ``landing`` is where they ended up. When no clear descent can
be found the onset falls back to the landing point and is flagged ``onset_estimated``
false instead of being presented as a measured onset.

Zone data is shared by everyone using the server and kept indefinitely; it holds
coordinates and times only. The one image kept long term is a reference photo of the
room, which can be replaced.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import tempfile
import threading
from typing import Any, Mapping, Sequence

import cv2
import numpy as np

from icare.api.store import Store, utc_now


WINDOW_SECONDS = 4.5           # how much of the track before the detection is examined
MIN_CONFIDENCE = 0.30          # keypoint score needed to use a joint
ONSET_FRACTION = 0.15          # descent is "started" once 15 % of the total drop has happened
MIN_DROP = 0.20                # ...and the hips must drop by at least 20 % of body height
HIPS, SHOULDERS, ANKLES = (11, 12), (5, 6), (15, 16)

MAX_PHOTO_BYTES = 4 * 1024 * 1024
MAX_PHOTO_WIDTH = 1280
SNAPSHOT_WIDTH = 960
ROOM_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,31}$")


def valid_room(room: str | None) -> str | None:
    """A room id the API accepts, or None for 'no room'. Raises ValueError otherwise."""
    if room is None or room == "":
        return None
    if not ROOM_PATTERN.match(room):
        raise ValueError("Room names use 1 to 32 letters, digits, spaces, dots, dashes or underscores.")
    return room


# ------------------------------------------------------------------ fall location

def _mean_point(keypoints: Sequence[Sequence[float]], joints: tuple[int, ...]) -> tuple[float, float] | None:
    points = [keypoints[j] for j in joints if keypoints[j][2] >= MIN_CONFIDENCE]
    if not points:
        return None
    return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))


def _core_y(pose: Mapping[str, Any]) -> float:
    """Vertical position of the body core: hips, else shoulders, else the box centre."""
    keypoints = pose["keypoints"]
    for joints in (HIPS, SHOULDERS):
        confident = [keypoints[j] for j in joints if keypoints[j][2] >= MIN_CONFIDENCE]
        if len(confident) == len(joints):
            return sum(p[1] for p in confident) / len(confident)
    box = pose["bbox_xyxy"]
    return (box[1] + box[3]) / 2


def _feet(pose: Mapping[str, Any]) -> tuple[float, float]:
    """Where the person stands: the ankles, else the bottom centre of the box."""
    point = _mean_point(pose["keypoints"], ANKLES)
    if point is not None:
        return point
    box = pose["bbox_xyxy"]
    return ((box[0] + box[2]) / 2, box[3])


def _centre(pose: Mapping[str, Any]) -> tuple[float, float]:
    box = pose["bbox_xyxy"]
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def estimate_fall_location(
    poses: Sequence[Mapping[str, Any]], detected_at: float, frame_width: int, frame_height: int,
) -> dict[str, Any] | None:
    """Where one person's fall began and ended, from that person's own pose track.

    ``poses`` are the pose records of one tracked person (timestamp_seconds, bbox_xyxy,
    keypoints). Only poses up to the detection time are used. Returns None when there
    are too few poses to say anything.
    """

    track = sorted((p for p in poses if detected_at - WINDOW_SECONDS <= p["timestamp_seconds"] <= detected_at + 1e-6),
                   key=lambda p: p["timestamp_seconds"])
    if not track or frame_width <= 0 or frame_height <= 0:
        return None
    landing_pose = track[-1]
    landing = _centre(landing_pose)
    onset_pose, onset_seconds, estimated = landing_pose, None, False

    if len(track) >= 3:
        heights = [p["bbox_xyxy"][3] - p["bbox_xyxy"][1] for p in track]
        upright = max(heights)
        core = [_core_y(p) for p in track]
        top = min(range(len(track)), key=core.__getitem__)           # highest the body core got
        low = top + max(range(len(track) - top), key=lambda k: core[top + k])   # lowest after that
        drop = core[low] - core[top]
        if upright > 0 and drop >= MIN_DROP * upright:
            threshold = core[top] + ONSET_FRACTION * drop
            start = next(i for i in range(top, low + 1) if core[i] >= threshold)
            onset_pose, onset_seconds, estimated = track[start], float(track[start]["timestamp_seconds"]), True

    onset = _feet(onset_pose) if estimated else landing
    box = onset_pose["bbox_xyxy"]
    clip01 = lambda value: float(min(max(value, 0.0), 1.0))  # noqa: E731
    return {
        "onset_seconds": onset_seconds,
        "onset_x": clip01(onset[0] / frame_width), "onset_y": clip01(onset[1] / frame_height),
        "landing_x": clip01(landing[0] / frame_width), "landing_y": clip01(landing[1] / frame_height),
        "body_width": clip01((box[2] - box[0]) / frame_width),
        "onset_estimated": estimated,
        "frame_width": int(frame_width), "frame_height": int(frame_height),
        # The picture is taken when the descent began, or at the detection when that is unknown.
        "snapshot_seconds": onset_seconds if estimated else float(detected_at),
    }


# ----------------------------------------------------------------- per-fall picture

RED, ORANGE = (40, 40, 235), (0, 150, 255)   # BGR


def _glow(image: np.ndarray, centre: tuple[int, int], radius: int, colour: tuple[int, int, int], strength: float) -> None:
    """Blend a soft filled blob of ``colour`` into ``image``, strongest at ``centre``."""
    height, width = image.shape[:2]
    reach = radius * 2
    x0, y0 = max(0, centre[0] - reach), max(0, centre[1] - reach)
    x1, y1 = min(width, centre[0] + reach + 1), min(height, centre[1] + reach + 1)
    if x1 <= x0 or y1 <= y0:
        return
    mask = np.zeros((y1 - y0, x1 - x0), np.float32)
    cv2.circle(mask, (centre[0] - x0, centre[1] - y0), radius, 1.0, -1, cv2.LINE_AA)
    kernel = (radius * 2) | 1
    mask = cv2.GaussianBlur(mask, (kernel, kernel), radius / 2)
    peak = float(mask.max())
    if peak <= 0:
        return
    alpha = (mask / peak * strength)[..., None]
    region = image[y0:y1, x0:x1].astype(np.float32)
    image[y0:y1, x0:x1] = (region * (1 - alpha) + np.array(colour, np.float32) * alpha).astype(np.uint8)


def render_snapshot(frame_bgr: np.ndarray, location: Mapping[str, Any]) -> bytes:
    """JPEG of the frame with a red area where the fall began and an orange one where it ended."""

    image = frame_bgr.copy()
    height, width = image.shape[:2]
    radius = max(24, int(round(location["body_width"] * width * 0.7)))

    def at(x: float, y: float) -> tuple[int, int]:
        return (int(round(x * (width - 1))), int(round(y * (height - 1))))

    onset = at(location["onset_x"], location["onset_y"])
    landing = at(location["landing_x"], location["landing_y"])
    if location["onset_estimated"]:
        _glow(image, landing, int(radius * 0.8), ORANGE, 0.5)
        gap = float(np.hypot(landing[0] - onset[0], landing[1] - onset[1]))
        if gap > radius * 2.2:   # far enough apart for an arrow that starts and ends outside both areas
            ux, uy = (landing[0] - onset[0]) / gap, (landing[1] - onset[1]) / gap
            tail = (int(onset[0] + ux * radius), int(onset[1] + uy * radius))
            tip = (int(landing[0] - ux * radius * 0.9), int(landing[1] - uy * radius * 0.9))
            cv2.arrowedLine(image, tail, tip, (255, 255, 255), 2, cv2.LINE_AA, tipLength=0.15)
    _glow(image, onset, radius, RED, 0.65)
    cv2.circle(image, onset, max(6, radius // 3), (255, 255, 255), 2, cv2.LINE_AA)
    caption = ("Red area: where the fall began. Orange area: where the person landed."
               if location["onset_estimated"] else "Red area: where the person was when the fall was detected.")
    font, thickness = cv2.FONT_HERSHEY_SIMPLEX, max(1, round(width / 640))
    size = max(0.6, width / 1280)
    while size > 0.25 and cv2.getTextSize(caption, font, size, thickness)[0][0] > width - 20:
        size -= 0.05   # shrink the caption until it fits the picture
    text_height = cv2.getTextSize(caption, font, size, thickness)[0][1]
    # At the top: people's feet, where falls begin, are usually near the bottom of the frame.
    cv2.rectangle(image, (0, 0), (width, text_height + 14), (0, 0, 0), -1)
    cv2.putText(image, caption, (10, text_height + 7), font, size, (255, 255, 255), thickness, cv2.LINE_AA)
    if width > SNAPSHOT_WIDTH:
        image = cv2.resize(image, (SNAPSHOT_WIDTH, round(height * SNAPSHOT_WIDTH / width)), interpolation=cv2.INTER_AREA)
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise ValueError("The snapshot could not be encoded.")
    return encoded.tobytes()


# ------------------------------------------------------------------- room data

class ZoneManager:
    """Fall locations and the reference photo per room."""

    def __init__(self, store: Store, directory: Path) -> None:
        self.store = store
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    # photos ------------------------------------------------------------

    @staticmethod
    def _photo_name(room: str) -> str:
        return f"room-{hashlib.sha1(room.encode()).hexdigest()[:16]}.jpg"

    def startup(self) -> None:
        """Delete photo files no room refers to."""
        known = {row["file_name"] for row in self.store.room_photos()}
        for path in self.directory.iterdir():
            if path.is_file() and path.name not in known:
                path.unlink(missing_ok=True)

    def has_photo(self, room: str) -> bool:
        return self.store.get_room_photo(room) is not None

    def photo_path(self, room: str) -> Path | None:
        row = self.store.get_room_photo(room)
        path = self.directory / row["file_name"] if row else None
        return path if path is not None and path.is_file() else None

    def set_photo(self, room: str, data: bytes | np.ndarray, source: str) -> dict[str, Any]:
        """Store the room's reference photo (replacing any earlier one). Raises ValueError."""
        if isinstance(data, np.ndarray):
            image = data
        else:
            if len(data) > MAX_PHOTO_BYTES:
                raise ValueError(f"The photo must be {MAX_PHOTO_BYTES // (1024 * 1024)} MB or smaller.")
            try:
                image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR) if data else None
            except cv2.error:
                image = None
        if image is None or image.ndim != 3 or min(image.shape[:2]) < 32:
            raise ValueError("The file is not a usable image. Use a JPEG or PNG photo.")
        height, width = image.shape[:2]
        if width > MAX_PHOTO_WIDTH:
            image = cv2.resize(image, (MAX_PHOTO_WIDTH, round(height * MAX_PHOTO_WIDTH / width)), interpolation=cv2.INTER_AREA)
            height, width = image.shape[:2]
        ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 88])
        if not ok:
            raise ValueError("The photo could not be encoded.")
        name = self._photo_name(room)
        with self._lock:
            handle, temporary = tempfile.mkstemp(dir=self.directory, suffix=".part")
            with os.fdopen(handle, "wb") as file:
                file.write(encoded.tobytes())
            os.replace(temporary, self.directory / name)
            row = {"room": room, "file_name": name, "width": width, "height": height,
                   "source": source, "updated_at_utc": utc_now()}
            self.store.set_room_photo(row)
        return row

    def ensure_photo(self, room: str, frame: bytes | np.ndarray, source: str = "auto") -> bool:
        """Use ``frame`` as the room photo only if the room has none yet."""
        if self.has_photo(room):
            return False
        try:
            self.set_photo(room, frame, source)
        except ValueError:
            return False
        return True

    # falls -------------------------------------------------------------

    def record(
        self, *, fall_id: str, room: str, source_kind: str, source_id: str, track_id: int | None,
        detected_at_seconds: float, confidence: float, location: Mapping[str, Any],
    ) -> None:
        self.store.add_fall_location({
            "fall_id": fall_id, "room": room, "source_kind": source_kind, "source_id": source_id,
            "track_id": track_id, "detected_at_seconds": detected_at_seconds,
            "onset_seconds": location["onset_seconds"],
            "onset_x": location["onset_x"], "onset_y": location["onset_y"],
            "landing_x": location["landing_x"], "landing_y": location["landing_y"],
            "body_width": location["body_width"], "onset_estimated": int(location["onset_estimated"]),
            "frame_width": location["frame_width"], "frame_height": location["frame_height"],
            "confidence": confidence, "created_at_utc": utc_now(),
        })

    def remove_fall(self, room: str, fall_id: str) -> bool:
        return self.store.delete_fall_location(room, fall_id)

    def photo_url(self, room: str) -> str | None:
        from urllib.parse import quote
        row = self.store.get_room_photo(room)
        if row is None:
            return None
        return f"/api/v1/rooms/{quote(room, safe='')}/photo?v={quote(row['updated_at_utc'], safe='')}"

    def zone(self, room: str) -> dict[str, Any]:
        falls = self.store.fall_locations(room)
        photo = self.store.get_room_photo(room)
        size = (photo["width"], photo["height"]) if photo else (
            (falls[0]["frame_width"], falls[0]["frame_height"]) if falls else (None, None))
        return {
            "room": room, "frame_width": size[0], "frame_height": size[1],
            "photo_url": self.photo_url(room), "total_falls": self.store.count_fall_locations(room),
            "generated_at_utc": utc_now(),
            "falls": [{
                "fall_id": row["fall_id"], "source_kind": row["source_kind"], "track_id": row["track_id"],
                "detected_at_seconds": row["detected_at_seconds"], "onset_seconds": row["onset_seconds"],
                "created_at_utc": row["created_at_utc"], "confidence": row["confidence"],
                "onset_x": row["onset_x"], "onset_y": row["onset_y"],
                "landing_x": row["landing_x"], "landing_y": row["landing_y"],
                "body_width": row["body_width"], "onset_estimated": bool(row["onset_estimated"]),
                "frame_width": row["frame_width"], "frame_height": row["frame_height"],
            } for row in falls],
        }

    def rooms(self) -> list[dict[str, Any]]:
        summaries = {row["room"]: row for row in self.store.room_summaries()}
        photos = {row["room"] for row in self.store.room_photos()}
        return [{
            "room": room,
            "fall_count": summaries[room]["fall_count"] if room in summaries else 0,
            "last_fall_utc": summaries[room]["last_fall_utc"] if room in summaries else None,
            "has_photo": room in photos,
        } for room in sorted(set(summaries) | photos)]
