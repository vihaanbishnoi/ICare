from __future__ import annotations

from dataclasses import asdict, dataclass
from math import atan2, degrees
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from icare_app.pose import PoseFrame


TORSO_JOINTS = np.asarray([5, 6, 11, 12], dtype=np.int64)
HIP_JOINTS = np.asarray([11, 12], dtype=np.int64)
SHOULDER_JOINTS = np.asarray([5, 6], dtype=np.int64)


@dataclass(frozen=True)
class PoseSignals:
    """Deployment signals derived from two consecutive COCO-17 poses."""

    timestamp_seconds: float
    urgency: float
    reliability: float
    downward_velocity: float
    torso_rotation_rate: float
    joint_motion_rate: float
    bbox_aspect_change_rate: float
    mean_keypoint_confidence: float
    visible_joint_fraction: float
    torso_visibility: float
    temporal_stability: float
    frame_containment: float

    def as_dict(self) -> dict[str, float]:
        return {key: round(float(value), 6) for key, value in asdict(self).items()}


class PoseSignalEstimator:
    """Compute simple, interpretable urgency and reliability scores.

    Motion components are normalized by body-box size and elapsed time. The
    constants are deployment calibration points, not learned parameters. They
    should be tuned only on validation recordings.
    """

    def __init__(
        self,
        keypoint_threshold: float = 0.30,
        urgency_smoothing: float = 0.35,
    ) -> None:
        self.keypoint_threshold = float(keypoint_threshold)
        self.urgency_smoothing = float(np.clip(urgency_smoothing, 0.0, 1.0))
        self.previous_pose: PoseFrame | None = None
        self.previous_urgency = 0.0

    def reset(self) -> None:
        self.previous_pose = None
        self.previous_urgency = 0.0

    def update(self, pose: PoseFrame) -> PoseSignals:
        current = np.asarray(pose.keypoints, dtype=np.float32)
        visible = current[:, 2] >= self.keypoint_threshold
        mean_confidence = float(np.clip(current[:, 2].mean(), 0.0, 1.0))
        visible_fraction = float(visible.mean())
        torso_visibility = float(visible[TORSO_JOINTS].mean())
        containment = self._frame_containment(pose, visible)

        downward = 0.0
        rotation = 0.0
        joint_motion = 0.0
        aspect_change = 0.0
        temporal_stability = 0.5

        previous = self.previous_pose
        if previous is not None:
            elapsed = max(pose.timestamp_seconds - previous.timestamp_seconds, 1e-3)
            previous_points = np.asarray(previous.keypoints, dtype=np.float32)
            previous_visible = previous_points[:, 2] >= self.keypoint_threshold
            shared = visible & previous_visible
            body_height = max(float(pose.bbox[3] - pose.bbox[1]), 1.0)
            body_diagonal = max(
                float(np.hypot(pose.bbox[2] - pose.bbox[0], body_height)), 1.0
            )

            if visible[HIP_JOINTS].all() and previous_visible[HIP_JOINTS].all():
                hip_y = float(current[HIP_JOINTS, 1].mean())
                previous_hip_y = float(previous_points[HIP_JOINTS, 1].mean())
                downward = max(0.0, (hip_y - previous_hip_y) / body_height / elapsed)

            current_angle = self._torso_angle(current, visible)
            previous_angle = self._torso_angle(previous_points, previous_visible)
            if current_angle is not None and previous_angle is not None:
                difference = abs(current_angle - previous_angle)
                difference = min(difference, 180.0 - difference)
                rotation = difference / elapsed

            if shared.any():
                displacement = np.linalg.norm(
                    current[shared, :2] - previous_points[shared, :2], axis=1
                )
                normalized_motion = displacement / body_diagonal / elapsed
                joint_motion = float(np.median(normalized_motion))
                # Large frame-to-frame jumps usually indicate an unstable pose.
                temporal_stability = float(
                    1.0 - np.clip(np.percentile(normalized_motion, 75) / 1.5, 0.0, 1.0)
                )
            else:
                temporal_stability = 0.0

            aspect = self._bbox_aspect(pose.bbox)
            previous_aspect = self._bbox_aspect(previous.bbox)
            aspect_change = abs(aspect - previous_aspect) / elapsed

        raw_urgency = (
            0.38 * self._saturate(downward, 1.0)
            + 0.27 * self._saturate(rotation, 120.0)
            + 0.22 * self._saturate(joint_motion, 1.0)
            + 0.13 * self._saturate(aspect_change, 1.2)
        )
        urgency = (
            self.urgency_smoothing * raw_urgency
            + (1.0 - self.urgency_smoothing) * self.previous_urgency
        )
        reliability = (
            0.30 * mean_confidence
            + 0.22 * visible_fraction
            + 0.23 * torso_visibility
            + 0.15 * temporal_stability
            + 0.10 * containment
        )

        self.previous_pose = pose
        self.previous_urgency = float(np.clip(urgency, 0.0, 1.0))
        return PoseSignals(
            timestamp_seconds=float(pose.timestamp_seconds),
            urgency=self.previous_urgency,
            reliability=float(np.clip(reliability, 0.0, 1.0)),
            downward_velocity=float(downward),
            torso_rotation_rate=float(rotation),
            joint_motion_rate=float(joint_motion),
            bbox_aspect_change_rate=float(aspect_change),
            mean_keypoint_confidence=mean_confidence,
            visible_joint_fraction=visible_fraction,
            torso_visibility=torso_visibility,
            temporal_stability=temporal_stability,
            frame_containment=containment,
        )

    @staticmethod
    def _saturate(value: float, reference: float) -> float:
        return float(np.clip(value / max(reference, 1e-6), 0.0, 1.0))

    @staticmethod
    def _bbox_aspect(bbox: np.ndarray) -> float:
        width = max(float(bbox[2] - bbox[0]), 1.0)
        height = max(float(bbox[3] - bbox[1]), 1.0)
        return width / height

    @staticmethod
    def _torso_angle(points: np.ndarray, visible: np.ndarray) -> float | None:
        if not visible[TORSO_JOINTS].all():
            return None
        shoulder = points[SHOULDER_JOINTS, :2].mean(axis=0)
        hip = points[HIP_JOINTS, :2].mean(axis=0)
        vector = shoulder - hip
        # Angle relative to the upward vertical image axis.
        return abs(degrees(atan2(float(vector[0]), float(-vector[1]))))

    @staticmethod
    def _frame_containment(pose: PoseFrame, visible: np.ndarray) -> float:
        if not visible.any():
            return 0.0
        points = pose.keypoints[visible, :2]
        inside = (
            (points[:, 0] >= 0)
            & (points[:, 0] < pose.frame_width)
            & (points[:, 1] >= 0)
            & (points[:, 1] < pose.frame_height)
        )
        return float(inside.mean())
