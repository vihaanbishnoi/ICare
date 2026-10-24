"""Synthetic people for tests. These exercise plumbing, never model accuracy."""
from __future__ import annotations

import numpy as np

from icare.inference.pose import PoseFrame

# Relative COCO-17 joint positions for an upright person in a unit box (x, y).
UPRIGHT = np.array([
    [.50, .06], [.46, .04], [.54, .04], [.42, .06], [.58, .06],              # head
    [.35, .22], [.65, .22], [.28, .40], [.72, .40], [.25, .55], [.75, .55],  # arms
    [.40, .55], [.60, .55], [.40, .76], [.60, .76], [.40, .97], [.60, .97],  # legs
], dtype=np.float32)


def person(t: float, x: float, y: float, w: float = 60, h: float = 180,
           lying: float = 0.0, confidence: float = 0.9) -> PoseFrame:
    """A person standing with feet at (x + w/2, y + h); ``lying`` 0..1 tips them over.

    Rotation is about the feet towards +x, so lying=1 puts the head at foot level,
    changing box shape and joint layout the way a real fall does.
    """
    angle = lying * np.pi / 2
    feet = np.array([x + w * 0.5, y + h])
    rel = (UPRIGHT - np.array([0.5, 1.0])) * np.array([w, h])  # feet at origin, head up (-y)
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    points = feet + rel @ rotation.T
    keypoints = np.concatenate([points, np.full((17, 1), confidence)], axis=1).astype(np.float32)
    lo, hi = points.min(axis=0) - 4, points.max(axis=0) + 4
    return PoseFrame(timestamp_seconds=t, keypoints=keypoints,
                     bbox=np.array([lo[0], lo[1], hi[0], hi[1]], dtype=np.float32),
                     detected_people=1, frame_width=1280, frame_height=720, inference_ms=1.0)


def times(seconds: float, fps: float = 6.0):
    return [round(i / fps, 6) for i in range(int(round(seconds * fps)))]


class DescentClassifier:
    """Stand-in for PoseC3D: P(fall) from how far the hips drop inside ONE window.

    It reads only the heatmap tensor it is given, so a high value proves that this
    person's own window contained a fall. It is not a model of real falls.
    """

    model_version = "test-descent-classifier"

    def __init__(self):
        self.calls = 0

    def predict(self, tensor):
        self.calls += 1
        hips = tensor[0, 11:13].sum(axis=0)                     # (T, 64, 64)
        rows = np.arange(hips.shape[1], dtype=np.float32)[None, :, None]
        mass = hips.sum(axis=(1, 2))
        centre = (hips * rows).sum(axis=(1, 2)) / np.maximum(mass, 1e-6)
        descent = (centre[-8:].mean() - centre[:8].mean()) / hips.shape[1]
        return float(np.clip(descent / 0.15, 0.0, 1.0)) * 0.98 + 0.01

    def close(self):
        pass


class ScriptedPeople:
    """Pose extractor returning a scripted list of people for each timestamp."""

    model_version = None

    def __init__(self, script):
        self.script = script  # callable t -> list[PoseFrame]

    def fork(self):
        return self

    def extract_all(self, frame_rgb, timestamp_seconds):
        return self.script(round(timestamp_seconds, 6))
