from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

from icare_app.pose import PoseFrame


@dataclass(frozen=True)
class PoseC3DInput:
    """One timestamped PoseC3D input window."""

    tensor: np.ndarray  # (1, 17, 48, 64, 64), float32
    start_seconds: float
    end_seconds: float
    source_pose_count: int


class PoseSequenceBuffer:
    """Timestamp-aware rolling pose buffer with uniform temporal resampling."""

    def __init__(
        self,
        window_seconds: float = 4.0,
        clip_len: int = 48,
        minimum_poses: int = 6,
        minimum_coverage_seconds: float = 2.0,
    ) -> None:
        self.window_seconds = float(window_seconds)
        self.clip_len = int(clip_len)
        self.minimum_poses = int(minimum_poses)
        self.minimum_coverage_seconds = float(minimum_coverage_seconds)
        self._poses: deque[PoseFrame] = deque()

    def clear(self) -> None:
        self._poses.clear()

    def append(self, pose: PoseFrame) -> None:
        if self._poses and pose.timestamp_seconds <= self._poses[-1].timestamp_seconds:
            return
        self._poses.append(pose)
        cutoff = pose.timestamp_seconds - self.window_seconds
        while len(self._poses) > 1 and self._poses[1].timestamp_seconds < cutoff:
            self._poses.popleft()

    @property
    def pose_count(self) -> int:
        return len(self._poses)

    @property
    def coverage_seconds(self) -> float:
        if len(self._poses) < 2:
            return 0.0
        return float(
            self._poses[-1].timestamp_seconds - self._poses[0].timestamp_seconds
        )

    @property
    def ready(self) -> bool:
        if len(self._poses) < self.minimum_poses:
            return False
        return self.coverage_seconds >= self.minimum_coverage_seconds

    def build(self) -> PoseC3DInput | None:
        if not self.ready:
            return None

        poses = list(self._poses)
        timestamps = np.asarray([pose.timestamp_seconds for pose in poses], dtype=np.float64)
        start = max(timestamps[0], timestamps[-1] - self.window_seconds)
        target_times = np.linspace(start, timestamps[-1], self.clip_len)

        keypoints = np.stack([pose.keypoints for pose in poses]).astype(np.float32)
        sampled = np.empty((self.clip_len, 17, 3), dtype=np.float32)
        for joint in range(17):
            for channel in range(3):
                sampled[:, joint, channel] = np.interp(
                    target_times,
                    timestamps,
                    keypoints[:, joint, channel],
                )

        heatmaps = pose_sequence_to_heatmaps(sampled)
        return PoseC3DInput(
            tensor=heatmaps[None],
            start_seconds=float(target_times[0]),
            end_seconds=float(target_times[-1]),
            source_pose_count=len(poses),
        )


def pose_sequence_to_heatmaps(
    keypoints: np.ndarray,
    image_size: int = 64,
    sigma: float = 0.6,
    padding: float = 0.25,
    confidence_threshold: float = 0.01,
) -> np.ndarray:
    """Convert T×17×3 COCO poses to PoseC3D joint heatmaps C×T×H×W.

    This mirrors the deployed parts of the validation pipeline: PoseCompact with
    a square crop, resize/center crop to 64×64, GeneratePoseTarget with keypoint
    scores, and NCTHW_Heatmap formatting.
    """

    points = np.asarray(keypoints, dtype=np.float32)
    if points.ndim != 3 or points.shape[1:] != (17, 3):
        raise ValueError(f"Expected (T, 17, 3), received {points.shape}")

    valid = points[..., 2] >= confidence_threshold
    if not np.any(valid):
        return np.zeros((17, len(points), image_size, image_size), dtype=np.float32)

    valid_x = points[..., 0][valid]
    valid_y = points[..., 1][valid]
    min_x, max_x = float(valid_x.min()), float(valid_x.max())
    min_y, max_y = float(valid_y.min()), float(valid_y.max())
    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)

    # PoseCompact padding=0.25 and hw_ratio=1.0: expand a global square box.
    side = max(width, height) * (1.0 + padding)
    center_x = (min_x + max_x) * 0.5
    center_y = (min_y + max_y) * 0.5
    origin_x = center_x - side * 0.5
    origin_y = center_y - side * 0.5

    transformed = points.copy()
    transformed[..., 0] = (transformed[..., 0] - origin_x) * (image_size / side)
    transformed[..., 1] = (transformed[..., 1] - origin_y) * (image_size / side)

    heatmaps = np.zeros((17, len(points), image_size, image_size), dtype=np.float32)
    radius = max(1, int(3 * sigma))
    for frame_index in range(len(points)):
        for joint_index in range(17):
            confidence = float(transformed[frame_index, joint_index, 2])
            if confidence < confidence_threshold:
                continue
            x = float(transformed[frame_index, joint_index, 0])
            y = float(transformed[frame_index, joint_index, 1])
            left = max(0, int(np.floor(x - radius)))
            right = min(image_size, int(np.ceil(x + radius + 1)))
            top = max(0, int(np.floor(y - radius)))
            bottom = min(image_size, int(np.ceil(y + radius + 1)))
            if left >= right or top >= bottom:
                continue
            grid_y, grid_x = np.mgrid[top:bottom, left:right]
            gaussian = np.exp(-((grid_x - x) ** 2 + (grid_y - y) ** 2) / (2 * sigma**2))
            heatmaps[joint_index, frame_index, top:bottom, left:right] = (
                gaussian * confidence
            )
    return heatmaps
