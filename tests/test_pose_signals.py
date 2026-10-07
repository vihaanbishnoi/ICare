from __future__ import annotations

import unittest
from dataclasses import dataclass

import numpy as np

from icare_app.pose_signals import PoseSignalEstimator


@dataclass(frozen=True)
class PoseFrame:
    timestamp_seconds: float
    keypoints: np.ndarray
    bbox: np.ndarray
    detected_people: int
    frame_width: int
    frame_height: int
    inference_ms: float


def pose_frame(
    timestamp: float,
    y_offset: float = 0.0,
    confidence: float = 0.95,
    outside: bool = False,
) -> PoseFrame:
    points = np.asarray(
        [
            [160, 55], [153, 50], [167, 50], [147, 53], [173, 53],
            [135, 100], [185, 100], [120, 145], [200, 145], [110, 190],
            [210, 190], [145, 205], [175, 205], [140, 275], [180, 275],
            [137, 350], [183, 350],
        ],
        dtype=np.float32,
    )
    points[:, 1] += y_offset
    if outside:
        points[:, 0] += 500
    keypoints = np.column_stack(
        [points, np.full(17, confidence, dtype=np.float32)]
    )
    return PoseFrame(
        timestamp_seconds=timestamp,
        keypoints=keypoints,
        bbox=np.asarray([100, 40 + y_offset, 220, 370 + y_offset], dtype=np.float32),
        detected_people=1,
        frame_width=320,
        frame_height=400,
        inference_ms=10.0,
    )


class PoseSignalEstimatorTests(unittest.TestCase):
    def test_stationary_pose_has_low_urgency_and_high_reliability(self) -> None:
        estimator = PoseSignalEstimator(urgency_smoothing=1.0)
        estimator.update(pose_frame(0.0))
        signals = estimator.update(pose_frame(0.5))
        self.assertLess(signals.urgency, 0.05)
        self.assertGreater(signals.reliability, 0.85)

    def test_rapid_downward_motion_increases_urgency(self) -> None:
        estimator = PoseSignalEstimator(urgency_smoothing=1.0)
        estimator.update(pose_frame(0.0))
        signals = estimator.update(pose_frame(0.2, y_offset=100.0))
        self.assertGreater(signals.downward_velocity, 0.5)
        self.assertGreater(signals.urgency, 0.15)

    def test_low_confidence_cropped_pose_has_low_reliability(self) -> None:
        estimator = PoseSignalEstimator(urgency_smoothing=1.0)
        signals = estimator.update(
            pose_frame(0.0, confidence=0.05, outside=True)
        )
        self.assertLess(signals.reliability, 0.25)


if __name__ == "__main__":
    unittest.main()
