"""Short video clips of detected falls: cutting, encoding, storage cap and expiry.

Uploads: after analysis the clip is cut from the owner's uploaded video.
Live: camera frames are not stored continuously. A few seconds of JPEG frames stay
in memory and are written to disk only when a fall is detected.

A clip covers the model's own 4 s window before the detection plus 1 s after it, so
the fall is always inside. Each clip also gets a still picture of where the fall
began (see icare.api.danger); when the clip belongs to a room, the fall's location is
also added to that room's danger zone, which outlives the clip.

Clips live in ``<data_dir>/clips`` with their own size cap (the oldest clips are
evicted first, so the newest falls are always kept) and an expiry, and are served
only to the browser session that owns them. Files are H.264 MP4 when the local
OpenCV build can encode it, otherwise VP8 WebM; both play in current browsers.
A clip is never written in a format browsers cannot play.
"""
from __future__ import annotations

from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import logging
import math
from pathlib import Path
import threading
import time
from typing import Any, Mapping, Sequence

import cv2
import numpy as np

from icare.api.danger import ZoneManager, estimate_fall_location, render_snapshot
from icare.api.store import Store, utc_now


log = logging.getLogger(__name__)

# (OpenCV fourcc, extension, media type), in order of preference.
CODECS = (("avc1", ".mp4", "video/mp4"), ("VP80", ".webm", "video/webm"))
MAX_CLIP_WIDTH = 960      # keeps a clip small enough for the storage cap
MAX_CLIP_FPS = 30.0
LIVE_BUFFER_BYTES = 24 * 1024 * 1024
LIVE_MAX_PENDING = 6      # simultaneous unfinished live clips per session
LIVE_POST_WAIT_SECONDS = 3.0   # real time to wait for the frames after a fall before saving anyway
LIVE_LATE_FRAME_SECONDS = 1.5  # a frame this soon after the window may still close the clip
REFERENCE_SLOT_SECONDS = 1 / 6


class ClipEncodeError(Exception):
    pass


def clip_window(detected_at: float, pre: float, post: float, duration: float | None = None) -> tuple[float, float]:
    """Source-time [start, end] of a clip of length pre + post around a detection.

    The window slides, rather than shrinks, at the start or end of the source, so
    a fall near either edge still gets a full-length clip when the source allows.
    """

    length = pre + post
    start = max(0.0, detected_at - pre)
    end = start + length
    if duration is not None and end > duration:
        end = duration
        start = max(0.0, end - length)
    return start, end


def _output_size(width: int, height: int) -> tuple[int, int]:
    scale = min(1.0, MAX_CLIP_WIDTH / width)
    out_w, out_h = max(2, round(width * scale)), max(2, round(height * scale))
    return out_w - out_w % 2, out_h - out_h % 2  # H.264 needs even dimensions


class ClipWriter:
    """Incrementally encode frames into a browser-playable file."""

    def __init__(self, directory: Path, stem: str, fps: float, source_size: tuple[int, int]) -> None:
        self.size = _output_size(*source_size)
        self.frames = 0
        self._writer = None
        for fourcc, extension, media_type in CODECS:
            path = directory / f"{stem}{extension}"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*fourcc), float(fps), self.size)
            if writer.isOpened():
                self._writer, self.path, self.media_type = writer, path, media_type
                return
            writer.release()
            path.unlink(missing_ok=True)
        raise ClipEncodeError("No browser-playable video encoder (H.264 or VP8) is available in this OpenCV build.")

    def write(self, frame_bgr: np.ndarray) -> None:
        height, width = frame_bgr.shape[:2]
        if (width, height) != self.size:
            frame_bgr = cv2.resize(frame_bgr, self.size, interpolation=cv2.INTER_AREA)
        self._writer.write(frame_bgr)
        self.frames += 1

    def finish(self) -> int:
        """Close the file, check it can be read back, and return its size in bytes."""
        self._writer.release()
        self._writer = None
        if self.frames == 0 or not self.path.is_file() or self.path.stat().st_size == 0:
            self.abort()
            raise ClipEncodeError("The clip contained no frames.")
        probe = cv2.VideoCapture(str(self.path))
        try:
            readable = probe.isOpened() and probe.grab()
        finally:
            probe.release()
        if not readable:
            self.abort()
            raise ClipEncodeError("The encoded clip could not be read back.")
        return self.path.stat().st_size

    def abort(self) -> None:
        if self._writer is not None:
            self._writer.release()
            self._writer = None
        self.path.unlink(missing_ok=True)


class _Plan:
    """One clip to be cut from a video: frame range and running state."""

    def __init__(self, clip_id: str, start_index: int, end_index: int,
                 location: Mapping[str, Any] | None = None, snap_index: int | None = None) -> None:
        self.clip_id, self.start_index, self.end_index = clip_id, start_index, end_index
        self.writer: ClipWriter | None = None
        self.seen = self.emitted = 0
        self.first_index: int | None = None
        self.last_index: int | None = None
        self.location, self.snap_index = location, snap_index
        self.snap_frame: np.ndarray | None = None
        self.snap_distance: int | None = None


class ClipManager:
    def __init__(
        self, store: Store, directory: Path, *, max_bytes: int, retention_seconds: float,
        pre_seconds: float, post_seconds: float, max_per_job: int, zones: ZoneManager | None = None,
    ) -> None:
        self.store = store
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self.retention_seconds = retention_seconds
        self.pre_seconds = pre_seconds
        self.post_seconds = post_seconds
        self.max_per_job = max_per_job
        self.zones = zones  # room danger-zone data; None keeps clips only
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="icare-clip")

    @classmethod
    def from_settings(cls, store: Store, settings) -> "ClipManager":
        return cls(
            store, settings.data_dir / "clips", max_bytes=settings.max_clip_storage_bytes,
            retention_seconds=settings.clip_retention_seconds, pre_seconds=settings.clip_pre_seconds,
            post_seconds=settings.clip_post_seconds, max_per_job=settings.max_clips_per_job,
            zones=ZoneManager(store, settings.data_dir / "rooms"),
        )

    # ------------------------------------------------------------------ housekeeping

    def startup(self) -> None:
        """Fail clips interrupted by a restart and delete files no clip row owns."""
        self.store.fail_interrupted_clips()
        known = self.store.clip_file_names()
        for path in self.directory.iterdir():
            if path.is_file() and path.name not in known:
                path.unlink(missing_ok=True)
        if self.zones is not None:
            self.zones.startup()

    def close(self) -> None:
        self._pool.shutdown(wait=True)

    def remove_expired(self) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=self.retention_seconds)).isoformat()
        for row in self.store.clips_created_before(cutoff):
            self._remove(row)

    def delete(self, clip_id: str) -> None:
        row = self.store.get_clip(clip_id)
        if row is not None:
            self._remove(row)

    def delete_for_source(self, source_id: str) -> None:
        """Remove every clip of a deleted or expired job (room danger-zone data is kept)."""
        for row in self.store.clips_for_source(source_id):
            self._remove(row)

    def _remove(self, row: dict[str, Any]) -> None:
        for name in (row.get("file_name"), row.get("snapshot_file")):
            if name:
                self._file(name).unlink(missing_ok=True)
        self.store.delete_clip(row["clip_id"])

    def _file(self, name: str) -> Path:
        if Path(name).name != name:
            raise ValueError("Clip file names must not contain directories.")
        return self.directory / name

    # --------------------------------------------------------------------- lookups

    def expires_at(self, created_at_utc: str) -> str:
        return (datetime.fromisoformat(created_at_utc) + timedelta(seconds=self.retention_seconds)).isoformat()

    def is_expired(self, row: dict[str, Any]) -> bool:
        return datetime.fromisoformat(row["created_at_utc"]) + timedelta(seconds=self.retention_seconds) <= datetime.now(timezone.utc)

    def owned(self, clip_id: str, owner: str) -> dict[str, Any] | None:
        """An unexpired clip of this browser session, else None (expired ones are removed)."""
        row = self.store.get_clip(clip_id)
        if row is None or row["owner"] != owner:
            return None
        if self.is_expired(row):
            self._remove(row)
            return None
        return row

    def path_of(self, row: dict[str, Any]) -> Path | None:
        if row["status"] != "ready" or not row.get("file_name"):
            return None
        path = self._file(row["file_name"])
        return path if path.is_file() else None

    def snapshot_path(self, row: dict[str, Any]) -> Path | None:
        if not row.get("snapshot_file"):
            return None
        path = self._file(row["snapshot_file"])
        return path if path.is_file() else None

    def document(self, row: dict[str, Any]) -> dict[str, Any]:
        ready = row["status"] == "ready"
        return {
            "clip_id": row["clip_id"], "source_kind": row["source_kind"], "source_id": row["source_id"],
            "track_id": row["track_id"], "identity": row.get("identity"), "status": row["status"], "room": row.get("room"),
            "detected_at_seconds": row["detected_at_seconds"], "confidence": row["confidence"],
            "clip_start_seconds": row["clip_start_seconds"], "duration_seconds": row["duration_seconds"],
            "created_at_utc": row["created_at_utc"], "expires_at_utc": self.expires_at(row["created_at_utc"]),
            "size_bytes": row["size_bytes"] if ready else None,
            "media_type": row["media_type"] if ready else None,
            "video_url": f"/api/v1/clips/{row['clip_id']}/video" if ready else None,
            "snapshot_url": f"/api/v1/clips/{row['clip_id']}/snapshot" if row.get("snapshot_file") else None,
            "error_message": row["error_message"],
        }

    def listing(self, owner: str) -> dict[str, Any]:
        self.remove_expired()
        return {
            "clips": [self.document(row) for row in self.store.list_clips(owner)],
            "storage_used_bytes": self.store.clip_bytes(),
            "storage_cap_bytes": self.max_bytes,
            "retention_seconds": self.retention_seconds,
        }

    # ------------------------------------------------------------- creating records

    def create_pending(
        self, *, clip_id: str, owner: str, source_kind: str, source_id: str, track_id: int | None,
        detected_at: float, confidence: float, clip_start: float | None = None, room: str | None = None,
        identity: str | None = None,
    ) -> None:
        self.store.add_clip({
            "clip_id": clip_id, "owner": owner, "source_kind": source_kind, "source_id": source_id,
            "track_id": track_id, "identity": identity, "status": "pending", "detected_at_seconds": detected_at,
            "confidence": confidence, "clip_start_seconds": clip_start, "created_at_utc": utc_now(),
            "room": room,
        })

    def _fail(self, clip_id: str, message: str) -> None:
        log.warning("Fall clip %s not saved: %s", clip_id, message)
        self.store.update_clip(clip_id, status="failed", error_message=message)

    def _save_snapshot(self, clip_id: str, frame_bgr: np.ndarray, location: Mapping[str, Any]) -> None:
        """Store the per-fall picture; its size counts towards the clip storage cap."""
        try:
            data = render_snapshot(frame_bgr, location)
        except Exception:  # noqa: BLE001 - the picture is optional
            log.exception("Could not draw the snapshot for clip %s", clip_id)
            return
        with self._lock:
            row = self.store.get_clip(clip_id)
            if row is None:
                return
            name = f"{clip_id}.jpg"
            self._file(name).write_bytes(data)
            self.store.update_clip(clip_id, snapshot_file=name, size_bytes=row["size_bytes"] + len(data))

    def _commit(self, clip_id: str, path: Path, media_type: str, start: float, duration: float) -> None:
        """Make a finished file visible, evicting the oldest clips to respect the cap."""
        video = path.stat().st_size
        with self._lock:
            row = self.store.get_clip(clip_id)
            if row is None:  # the job or clip was deleted while it was being encoded
                path.unlink(missing_ok=True)
                return
            picture = row["size_bytes"]  # the snapshot, already counted
            if picture + video > self.max_bytes:
                path.unlink(missing_ok=True)
                self._fail(clip_id, "The clip is larger than the clip storage limit.")
                return
            used = self.store.clip_bytes()
            for old in self.store.ready_clips_oldest_first():
                if used + video <= self.max_bytes:
                    break
                used -= old["size_bytes"]
                self._remove(old)
            saved = self.store.update_clip(
                clip_id, status="ready", file_name=path.name, media_type=media_type, size_bytes=picture + video,
                clip_start_seconds=start, duration_seconds=duration, error_message=None,
            )
            if not saved:
                path.unlink(missing_ok=True)

    # ------------------------------------------------------------- fall locations

    def locate_falls(
        self, poses: Sequence[Mapping[str, Any]], incidents: Sequence[Mapping[str, Any]],
        frame_width: int, frame_height: int,
    ) -> dict[str, dict[str, Any]]:
        """Where each incident's fall began and ended, from its own person's pose track."""
        tracks: dict[Any, list[Mapping[str, Any]]] = defaultdict(list)
        for pose in poses:
            tracks[pose.get("track_id")].append(pose)
        found = {}
        for incident in incidents:
            location = estimate_fall_location(
                tracks.get(incident.get("track_id"), []), incident["detected_at_seconds"], frame_width, frame_height)
            if location is not None:
                found[incident["incident_id"]] = location
        return found

    def record_locations(
        self, room: str | None, source_kind: str, source_id: str,
        incidents: Sequence[Mapping[str, Any]], locations: Mapping[str, Mapping[str, Any]],
    ) -> None:
        """Add confirmed falls to the room's danger zone (kept after the clip expires)."""
        if not room or self.zones is None:
            return
        for incident in incidents:
            location = locations.get(incident["incident_id"])
            if location is not None:
                self.zones.record(
                    fall_id=incident["incident_id"], room=room, source_kind=source_kind, source_id=source_id,
                    track_id=incident.get("track_id"), detected_at_seconds=incident["detected_at_seconds"],
                    confidence=incident["confidence"], location=location)

    def reference_photo_from_video(self, room: str | None, video_path: Path, pose_times: Sequence[float]) -> None:
        """Use a frame without anyone in it as the room photo, if the room has none yet."""
        if not room or self.zones is None or self.zones.has_photo(room):
            return
        cap = cv2.VideoCapture(str(video_path))
        try:
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            if not cap.isOpened() or not math.isfinite(fps) or fps <= 0:
                return
            times = sorted(pose_times)
            target = 0
            count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            for slot in range(int(count / fps / REFERENCE_SLOT_SECONDS) + 1):
                at = slot * REFERENCE_SLOT_SECONDS
                if all(abs(at - t) > REFERENCE_SLOT_SECONDS * 0.6 for t in times):
                    target = round(at * fps)
                    break
            frame = None
            for index in range(target + 1):
                if not cap.grab():
                    break
                if index == target:
                    ok, decoded = cap.retrieve()
                    frame = decoded if ok else None
            if frame is not None:
                self.zones.ensure_photo(room, frame)
        finally:
            cap.release()

    # ------------------------------------------------------------------ uploads

    def cut_from_video(
        self, owner: str, job_id: str, video_path: Path, incidents: Sequence[dict[str, Any]],
        duration: float | None, cancel_event: threading.Event, *,
        room: str | None = None, locations: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        """Cut one clip per incident (up to the per-job limit) in a single pass.

        Sets ``clip_id`` on each incident that gets a clip. Failures are recorded
        on the clip, never raised: a clip is a convenience, not part of the result.
        """

        locations = locations or {}
        cap = cv2.VideoCapture(str(video_path))
        try:
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            if not cap.isOpened() or not math.isfinite(fps) or fps <= 0:
                raise ClipEncodeError("The uploaded video could not be reopened to cut a clip.")
            plans: list[_Plan] = []
            for incident in list(incidents)[: self.max_per_job]:
                start, end = clip_window(incident["detected_at_seconds"], self.pre_seconds, self.post_seconds, duration)
                clip_id = incident["incident_id"]
                self.create_pending(
                    clip_id=clip_id, owner=owner, source_kind="upload", source_id=job_id,
                    track_id=incident.get("track_id"), detected_at=incident["detected_at_seconds"],
                    confidence=incident["confidence"], clip_start=start, room=room, identity=incident.get("identity"),
                )
                incident["clip_id"] = clip_id
                location = locations.get(clip_id)
                plans.append(_Plan(
                    clip_id, math.ceil(start * fps - 1e-9), math.floor(end * fps + 1e-9), location,
                    round(location["snapshot_seconds"] * fps) if location else None))
            self._cut(cap, fps, plans, cancel_event)
        except Exception as error:  # noqa: BLE001 - the job result must not depend on clips
            log.exception("Could not cut fall clips for job %s", job_id)
            for incident in incidents:
                clip_id = incident.get("clip_id")
                row = self.store.get_clip(clip_id) if clip_id else None
                if row is not None and row["status"] == "pending":
                    self._fail(clip_id, str(error) or "The clip could not be created.")
        finally:
            cap.release()

    def _cut(self, cap: cv2.VideoCapture, fps: float, plans: list[_Plan], cancel_event: threading.Event) -> None:
        ratio = min(1.0, MAX_CLIP_FPS / fps)
        last_needed = max((plan.end_index for plan in plans), default=-1)
        index = 0
        try:
            while index <= last_needed and cap.grab():
                if cancel_event.is_set():
                    return
                active = [plan for plan in plans if plan.start_index <= index <= plan.end_index]
                if active:
                    ok, frame = cap.retrieve()
                    if ok and frame is not None:
                        for plan in active:
                            self._feed(plan, frame, index, fps, ratio)
                index += 1
        finally:
            cancelled = cancel_event.is_set()
            for plan in plans:
                self._finish(plan, fps, cancelled)

    def _feed(self, plan: _Plan, frame: np.ndarray, index: int, fps: float, ratio: float) -> None:
        if plan.writer is None:
            height, width = frame.shape[:2]
            try:
                plan.writer = ClipWriter(self.directory, plan.clip_id, min(fps, MAX_CLIP_FPS), (width, height))
            except ClipEncodeError as error:
                self._fail(plan.clip_id, str(error))
                plan.start_index, plan.end_index = 1, 0  # never active again
                return
        if plan.first_index is None:
            plan.first_index = index
        plan.last_index = index
        if plan.snap_index is not None:
            distance = abs(index - plan.snap_index)
            if plan.snap_distance is None or distance < plan.snap_distance:
                plan.snap_frame, plan.snap_distance = frame.copy(), distance
        plan.seen += 1
        if int(plan.seen * ratio) > plan.emitted:
            plan.emitted += 1
            plan.writer.write(frame)

    def _finish(self, plan: _Plan, fps: float, cancelled: bool) -> None:
        writer = plan.writer
        if writer is None:
            row = self.store.get_clip(plan.clip_id)
            if row is not None and row["status"] == "pending":
                if cancelled:
                    self.store.delete_clip(plan.clip_id)
                else:
                    self._fail(plan.clip_id, "The uploaded video had no frames in the clip window.")
            return
        if cancelled:
            writer.abort()
            self.store.delete_clip(plan.clip_id)
            return
        if plan.location is not None and plan.snap_frame is not None:
            self._save_snapshot(plan.clip_id, plan.snap_frame, plan.location)
        try:
            writer.finish()
        except ClipEncodeError as error:
            self._fail(plan.clip_id, str(error))
            return
        start = plan.first_index / fps
        duration = (plan.last_index - plan.first_index + 1) / fps
        self._commit(plan.clip_id, writer.path, writer.media_type, start, duration)

    # --------------------------------------------------------------------- live

    def submit_live_clip(
        self, clip_id: str, frames: list[tuple[float, bytes]], location: Mapping[str, Any] | None = None,
    ) -> None:
        """Encode a finished live window on the clip thread, off the frame path."""
        try:
            self._pool.submit(self._encode_live, clip_id, frames, location)
        except RuntimeError:  # the app is shutting down
            self._fail(clip_id, "The server stopped before the clip was saved.")

    def _encode_live(
        self, clip_id: str, frames: list[tuple[float, bytes]], location: Mapping[str, Any] | None,
    ) -> None:
        writer = None
        try:
            images = [cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR) for _, data in frames]
            kept = [(ts, image) for (ts, _), image in zip(frames, images) if image is not None]
            if len(kept) < 2:
                raise ClipEncodeError("Too few camera frames were captured around the fall.")
            if location is not None:
                nearest = min(kept, key=lambda item: abs(item[0] - location["snapshot_seconds"]))
                self._save_snapshot(clip_id, nearest[1], location)
            span = kept[-1][0] - kept[0][0]
            fps = min(MAX_CLIP_FPS, max(1.0, (len(kept) - 1) / span)) if span > 0 else 6.0
            height, width = kept[0][1].shape[:2]
            writer = ClipWriter(self.directory, clip_id, fps, (width, height))
            for _, image in kept:
                writer.write(image)
            writer.finish()
            self._commit(clip_id, writer.path, writer.media_type, kept[0][0], span + 1.0 / fps)
        except Exception as error:  # noqa: BLE001
            if writer is not None:
                writer.abort()
            self._fail(clip_id, str(error) or "The clip could not be created.")


class LiveClipRecorder:
    """Rolling in-memory buffer of one camera session's recent frames and poses.

    Nothing is written until a fall is detected: ``trigger`` copies the last
    ``pre`` seconds, later frames are appended until ``post`` seconds have passed,
    and the finished window is handed to the clip thread. The recent poses are kept
    only to work out where the fall began; they are never stored.
    """

    def __init__(self, manager: ClipManager, owner: str, session_id: str, room: str | None = None) -> None:
        self.manager, self.owner, self.session_id, self.room = manager, owner, session_id, room
        self._lock = threading.Lock()
        self._frames: deque[tuple[float, bytes]] = deque()
        self._poses: deque[tuple[float, list[Mapping[str, Any]]]] = deque()
        self._size: tuple[int, int] | None = None
        self._bytes = 0
        self._pending: list[dict[str, Any]] = []

    def add_frame(
        self, timestamp: float, jpeg: bytes, poses: Sequence[Mapping[str, Any]] = (),
        size: tuple[int, int] | None = None,
    ) -> None:
        finished = []
        with self._lock:
            self._frames.append((timestamp, jpeg))
            self._bytes += len(jpeg)
            if size is not None:
                self._size = size
            if poses:
                self._poses.append((timestamp, list(poses)))
            horizon = timestamp - self.manager.pre_seconds - 1.0
            while self._frames and (self._frames[0][0] < horizon or self._bytes > LIVE_BUFFER_BYTES):
                self._bytes -= len(self._frames.popleft()[1])
            while self._poses and self._poses[0][0] < horizon:
                self._poses.popleft()
            for pending in list(self._pending):
                if timestamp <= pending["end"]:
                    pending["frames"].append((timestamp, jpeg))
                    continue
                # Analysis can stall, so the next frame may land past the window: keep it
                # when it is close, so the clip still ends after the fall rather than at it.
                if timestamp <= pending["end"] + LIVE_LATE_FRAME_SECONDS:
                    pending["frames"].append((timestamp, jpeg))
                self._pending.remove(pending)
                finished.append(pending)
        for pending in finished:
            self._dispatch(pending)

    def flush_due(self) -> None:
        """Save clips whose after-frames never came (the camera stalled), after a real-time wait."""
        now = time.monotonic()
        with self._lock:
            due = [pending for pending in self._pending if now >= pending["deadline"]]
            self._pending = [pending for pending in self._pending if pending not in due]
        for pending in due:
            self._dispatch(pending)

    def trigger(self, *, clip_id: str, track_id: int | None, detected_at: float, confidence: float,
                identity: str | None = None) -> str | None:
        """Start a clip for a detection on the frame just added. Returns its id, or None."""
        start = detected_at - self.manager.pre_seconds
        with self._lock:
            if len(self._pending) >= LIVE_MAX_PENDING:
                return None
            location = None
            if self._size is not None:
                track = [pose for _, poses in self._poses for pose in poses if pose.get("track_id") == track_id]
                location = estimate_fall_location(track, detected_at, *self._size)
            self.manager.create_pending(
                clip_id=clip_id, owner=self.owner, source_kind="live", source_id=self.session_id,
                track_id=track_id, detected_at=detected_at, confidence=confidence,
                clip_start=max(0.0, start), room=self.room, identity=identity,
            )
            if location is not None and self.room and self.manager.zones is not None:
                self.manager.zones.record(
                    fall_id=clip_id, room=self.room, source_kind="live", source_id=self.session_id,
                    track_id=track_id, detected_at_seconds=detected_at, confidence=confidence, location=location)
            self._pending.append({
                "clip_id": clip_id, "end": detected_at + self.manager.post_seconds, "location": location,
                "deadline": time.monotonic() + self.manager.post_seconds + LIVE_POST_WAIT_SECONDS,
                "frames": [(ts, data) for ts, data in self._frames if start <= ts <= detected_at],
            })
        return clip_id

    def close(self) -> None:
        """The session ended: save every unfinished clip with the frames it has."""
        with self._lock:
            remaining, self._pending = self._pending, []
            self._frames.clear()
            self._poses.clear()
            self._bytes = 0
        for pending in remaining:
            self._dispatch(pending)

    def _dispatch(self, pending: Mapping[str, Any]) -> None:
        self.manager.submit_live_clip(pending["clip_id"], pending["frames"], pending["location"])
