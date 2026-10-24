"""Name enrolled residents from their faces (OpenCV YuNet detector + SFace recogniser).

Enrolment stores only face embeddings (128 floats per photo) in a JSON gallery,
never the photos. During analysis each tracked person's head region is checked at
most once per ``attempt_interval_seconds`` until they are named; a name is given
only after ``votes_needed`` consecutive matches to the same resident with cosine
similarity >= ``threshold`` (OpenCV's suggested SFace threshold is 0.363; measured
on the development recordings, the enrolled person scored 0.53-0.88 and other
people 0.04-0.10). Once given, a track keeps its name; one name is never given to
two people in view at once. Without the model files or a gallery, nobody is named.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import secrets
import threading
from typing import Any

import numpy as np

MODELS_DIR = Path(__file__).resolve().parents[3] / "models"
DETECTOR_FILE = "face_detection_yunet_2023mar.onnx"
RECOGNISER_FILE = "face_recognition_sface_2021dec.onnx"
NOSE, EYES, EARS = 0, (1, 2), (3, 4)


class FaceError(ValueError):
    """Enrolment input problem; ``code`` is passed through as the API error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class FaceModels:
    """Loaded YuNet + SFace. Thread-safe: OpenCV models are used under a lock."""

    def __init__(self, models_dir: Path = MODELS_DIR, detection_threshold: float = 0.8) -> None:
        import cv2

        detector, recogniser = Path(models_dir) / DETECTOR_FILE, Path(models_dir) / RECOGNISER_FILE
        if not (detector.is_file() and recogniser.is_file()):
            raise FileNotFoundError("Face models are missing from models/.")
        self._cv2 = cv2
        self._detector = cv2.FaceDetectorYN.create(str(detector), "", (320, 320), detection_threshold)
        self._recogniser = cv2.FaceRecognizerSF.create(str(recogniser), "")
        self._lock = threading.Lock()

    @classmethod
    def load(cls, models_dir: Path = MODELS_DIR) -> "FaceModels | None":
        try:
            return cls(models_dir)
        except Exception:  # noqa: BLE001 - naming is optional; missing or broken models disable it
            return None

    def faces(self, image_bgr: np.ndarray, max_side: int = 640) -> list[tuple[np.ndarray, float, np.ndarray]]:
        """(embedding, detection score, box xywh in image pixels) for every face, largest first."""
        height, width = image_bgr.shape[:2]
        scale = min(1.0, max_side / max(height, width))
        small = image_bgr if scale == 1.0 else self._cv2.resize(
            image_bgr, (max(1, round(width * scale)), max(1, round(height * scale))))
        with self._lock:
            self._detector.setInputSize((small.shape[1], small.shape[0]))
            _, found = self._detector.detect(small)
            if found is None:
                return []
            found = found.copy()
            found[:, :14] /= scale
            result = []
            for face in found:
                embedding = self._recogniser.feature(self._recogniser.alignCrop(image_bgr, face))
                result.append((_unit(embedding), float(face[-1]), face[:4].copy()))
        return sorted(result, key=lambda item: -float(item[2][2] * item[2][3]))

    def enrolment_embedding(self, image_bgr: np.ndarray) -> np.ndarray:
        """The embedding of the photo's main face; rejects photos with no clear main face."""
        faces = self.faces(image_bgr, max_side=1024)
        if not faces:
            raise FaceError("no_face", "No face was found in one of the photos. Use a clear, front-facing photo.")
        if len(faces) > 1:
            first, second = (float(f[2][2] * f[2][3]) for f in faces[:2])
            if second > first / 2:
                raise FaceError("multiple_faces", "A photo shows more than one person clearly. Use a photo of just the resident.")
        return faces[0][0]


class FaceGallery:
    """Enrolled residents in a JSON file, re-read when the file changes."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._mtime: float | None = None
        self.residents: list[dict[str, Any]] = []
        self._names: list[str] = []
        self._matrix = np.zeros((0, 128), dtype=np.float32)
        self.refresh()

    def refresh(self) -> None:
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            mtime = None
        if mtime == self._mtime:
            return
        self._mtime = mtime
        self.residents = read_gallery(self.path)
        rows, names = [], []
        for resident in self.residents:
            for embedding in resident.get("embeddings", []):
                rows.append(_unit(np.asarray(embedding, dtype=np.float32)))
                names.append(resident["name"])
        self._names = names
        self._matrix = np.stack(rows) if rows else np.zeros((0, 128), dtype=np.float32)

    def best(self, embedding: np.ndarray) -> tuple[str | None, float]:
        if not len(self._names):
            return None, 0.0
        scores = self._matrix @ _unit(embedding).reshape(-1)
        index = int(np.argmax(scores))
        return self._names[index], float(scores[index])


@dataclass
class _Candidate:
    name: str | None = None
    votes: int = 0
    last_attempt: float = float("-inf")


@dataclass
class SessionIdentities:
    """Per-source naming of track IDs. Feed full-resolution RGB frames and their poses."""

    models: FaceModels
    gallery: FaceGallery
    threshold: float = 0.40
    votes_needed: int = 2
    attempt_interval_seconds: float = 1.0
    max_attempts_per_frame: int = 2
    names: dict[int, str] = field(default_factory=dict)
    _candidates: dict[int, _Candidate] = field(default_factory=dict)
    _last_refresh: float = float("-inf")

    def update(self, frame_rgb: np.ndarray, t: float, people: list[tuple[int, Any]], active: set[int]) -> None:
        """``people`` are (track_id, PoseFrame) in frame pixels; ``active`` are IDs still tracked."""
        if t - self._last_refresh >= 2.0:
            self.gallery.refresh()
            self._last_refresh = t
        for track_id in [k for k in self.names if k not in active]:
            del self.names[track_id]
        for track_id in [k for k in self._candidates if k not in active]:
            del self._candidates[track_id]
        if not self.gallery.residents:
            return
        attempts = 0
        for track_id, pose in people:
            if track_id in self.names or attempts >= self.max_attempts_per_frame:
                continue
            candidate = self._candidates.setdefault(track_id, _Candidate())
            if t - candidate.last_attempt < self.attempt_interval_seconds:
                continue
            region = head_region(pose.keypoints, pose.bbox, frame_rgb.shape)
            if region is None:
                continue
            candidate.last_attempt = t
            attempts += 1
            x1, y1, x2, y2 = region
            crop = np.ascontiguousarray(frame_rgb[y1:y2, x1:x2, ::-1])
            faces = self.models.faces(crop, max_side=320)
            name, score = (self.gallery.best(faces[0][0]) if faces else (None, 0.0))
            taken = set(self.names.values())
            if name is None or score < self.threshold or name in taken:
                candidate.name, candidate.votes = None, 0
                continue
            candidate.votes = candidate.votes + 1 if candidate.name == name else 1
            candidate.name = name
            if candidate.votes >= self.votes_needed:
                self.names[track_id] = name


def head_region(keypoints: np.ndarray, bbox: np.ndarray, shape) -> tuple[int, int, int, int] | None:
    """A square around the visible face joints, or the top of the body box; None if too small."""
    height, width = shape[:2]
    points = np.asarray(keypoints, dtype=np.float64)
    face = points[[NOSE, *EYES, *EARS]]
    visible = face[face[:, 2] >= 0.3]
    box_w = max(float(bbox[2] - bbox[0]), 1.0)
    if len(visible) >= 2:
        centre = visible[:, :2].mean(axis=0)
        spread = float(np.ptp(visible[:, 0])) if len(visible) > 1 else 0.0
        side = max(spread * 2.6, box_w * 0.45)
    else:
        return None  # face joints not visible: the person is turned away or occluded
    side = max(side, 48.0)
    x1, y1 = int(max(0, centre[0] - side / 2)), int(max(0, centre[1] - side * 0.55))
    x2, y2 = int(min(width, centre[0] + side / 2)), int(min(height, centre[1] + side * 0.6))
    if x2 - x1 < 32 or y2 - y1 < 32:
        return None
    return x1, y1, x2, y2


# ----------------------------------------------------------------- gallery file


def read_gallery(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [r for r in data.get("residents", []) if isinstance(r, dict) and r.get("name")]


def write_gallery(path: Path, residents: list[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"residents": residents}), encoding="utf-8")
    os.replace(temporary, path)


def new_resident(name: str, room: str | None, embeddings: list[np.ndarray]) -> dict[str, Any]:
    return {"resident_id": secrets.token_urlsafe(8), "name": name, "room": room or None,
            "embeddings": [[round(float(v), 6) for v in _unit(e).reshape(-1)] for e in embeddings],
            "created_at_utc": datetime.now(timezone.utc).isoformat()}


def _unit(vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(vector, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm > 0 and math.isfinite(norm) else vector
