"""Per-source multi-person tracking: persistent IDs from box and joint continuity.

Detections carry no identity, so each frame is matched to existing tracks by
how well a person's box and joints continue a track. A constant-velocity
prediction keeps IDs apart when people cross; a track survives short
occlusions for ``max_age_seconds``. There is no appearance model, so a person
hidden for longer than that, or who swaps places with someone while both are
hidden, can receive a new ID.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math

import numpy as np

from icare.inference.pose import PoseFrame

JOINT_CONFIDENCE = 0.3
MIN_SHARED_JOINTS = 4
MAX_EXTRAPOLATION_SECONDS = 0.5


@dataclass
class _Track:
    track_id: int
    bbox: np.ndarray
    keypoints: np.ndarray
    last_seen: float
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(2))  # box-centre px/s

    def predicted_bbox(self, t: float) -> np.ndarray:
        dt = min(max(t - self.last_seen, 0.0), MAX_EXTRAPOLATION_SECONDS)
        shift = self.velocity * dt
        return self.bbox + np.array([shift[0], shift[1], shift[0], shift[1]])


def box_iou(a: np.ndarray, b: np.ndarray) -> float:
    width = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    height = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    overlap = width * height
    union = _area(a) + _area(b) - overlap
    return overlap / union if union > 0 else 0.0


def keypoint_similarity(track: _Track, pose: PoseFrame, t: float) -> float:
    """OKS-style agreement of joints visible in both, scaled by the track's size."""
    shared = (track.keypoints[:, 2] >= JOINT_CONFIDENCE) & (pose.keypoints[:, 2] >= JOINT_CONFIDENCE)
    if int(shared.sum()) < MIN_SHARED_JOINTS:
        return 0.0
    shift = track.predicted_bbox(t)[:2] - track.bbox[:2]
    predicted = track.keypoints[shared, :2] + shift
    scale = max(math.sqrt(_area(track.bbox)), 1.0) * 0.25
    distances = np.linalg.norm(predicted - pose.keypoints[shared, :2], axis=1)
    return float(np.mean(np.exp(-(distances ** 2) / (2 * scale ** 2))))


def _area(box: np.ndarray) -> float:
    return float(max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1]))


def _centre(box: np.ndarray) -> np.ndarray:
    return np.array([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2], dtype=np.float64)


class PersonTracker:
    """Assigns a stable integer ID (1, 2, ...) to every person in one source."""

    def __init__(self, max_age_seconds: float = 2.0, min_similarity: float = 0.1,
                 max_centre_jump: float = 1.0) -> None:
        if max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be positive")
        if not 0 < min_similarity < 1:
            raise ValueError("min_similarity must be in (0, 1)")
        self.max_age_seconds = float(max_age_seconds)
        self.min_similarity = float(min_similarity)
        # Largest centre movement between matches, in box diagonals of the track.
        self.max_centre_jump = float(max_centre_jump)
        self._tracks: dict[int, _Track] = {}
        self._next_id = 1
        self.expired: list[int] = []

    @property
    def active_ids(self) -> list[int]:
        return sorted(self._tracks)

    @property
    def ids_issued(self) -> int:
        return self._next_id - 1

    def similarity(self, track: _Track, pose: PoseFrame, t: float) -> float:
        predicted = track.predicted_bbox(t)
        diagonal = math.hypot(predicted[2] - predicted[0], predicted[3] - predicted[1])
        jump = float(np.linalg.norm(_centre(predicted) - _centre(pose.bbox)))
        if diagonal <= 0 or jump > self.max_centre_jump * diagonal:
            return 0.0
        return max(box_iou(predicted, pose.bbox), keypoint_similarity(track, pose, t))

    def update(self, people: list[PoseFrame], t: float) -> list[tuple[int, PoseFrame]]:
        """Match this frame's people to tracks; returns (track_id, pose) pairs.

        Tracks unseen for longer than ``max_age_seconds`` are removed first and
        listed in ``expired`` until the next update, so callers can free state.
        """
        self.expired = [tid for tid, track in self._tracks.items() if t - track.last_seen > self.max_age_seconds]
        for tid in self.expired:
            del self._tracks[tid]

        # Greedy best-first matching: the most certain continuation is taken first.
        pairs = []
        for tid, track in self._tracks.items():
            for index, pose in enumerate(people):
                score = self.similarity(track, pose, t)
                if score >= self.min_similarity:
                    pairs.append((score, tid, index))
        pairs.sort(key=lambda item: (-item[0], item[1], item[2]))
        assigned: dict[int, int] = {}
        used_tracks: set[int] = set()
        for _, tid, index in pairs:
            if tid in used_tracks or index in assigned:
                continue
            assigned[index] = tid
            used_tracks.add(tid)

        result = []
        for index, pose in enumerate(people):
            tid = assigned.get(index)
            bbox = np.asarray(pose.bbox, dtype=np.float64)
            if tid is None:
                tid = self._next_id
                self._next_id += 1
                self._tracks[tid] = _Track(tid, bbox, np.asarray(pose.keypoints, dtype=np.float64), t)
            else:
                track = self._tracks[tid]
                dt = t - track.last_seen
                if dt > 0:
                    observed = (_centre(bbox) - _centre(track.bbox)) / dt
                    track.velocity = 0.5 * track.velocity + 0.5 * observed
                track.bbox, track.keypoints, track.last_seen = bbox, np.asarray(pose.keypoints, dtype=np.float64), t
            result.append((tid, pose))
        result.sort(key=lambda item: item[0])
        return result
