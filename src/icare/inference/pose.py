from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import cv2
import numpy as np


INPUT_SIZE = 640
LETTERBOX_FILL = 114  # Ultralytics' padding grey; the model was trained with it
MAX_DETECTIONS = 300
ROW_WIDTH = 6 + 17 * 3  # x1 y1 x2 y2 score class + 17 x (x, y, visibility)


@dataclass(frozen=True)
class PoseFrame:
    timestamp_seconds: float
    keypoints: np.ndarray  # (17, 3): x, y, confidence
    bbox: np.ndarray  # (4,): x1, y1, x2, y2
    detected_people: int
    frame_width: int
    frame_height: int
    inference_ms: float


class PoseModelError(RuntimeError):
    """The YOLO26 pose file is missing, altered or has an unexpected interface."""


def letterbox(frame_rgb: np.ndarray, size: int = INPUT_SIZE) -> tuple[np.ndarray, float, float, float]:
    """Resize keeping aspect ratio and pad to ``size`` square, centred (Ultralytics style).

    Returns the (1, 3, size, size) float32 RGB tensor in [0, 1], the scale and the
    left/top padding, so model coordinates map back as ``(v - pad) / scale``.
    """

    height, width = frame_rgb.shape[:2]
    scale = min(size / height, size / width)
    new_w, new_h = round(width * scale), round(height * scale)
    pad_x, pad_y = (size - new_w) / 2, (size - new_h) / 2
    resized = frame_rgb if (new_w, new_h) == (width, height) else cv2.resize(
        frame_rgb, (new_w, new_h), interpolation=cv2.INTER_LINEAR
    )
    top, left = round(pad_y - 0.1), round(pad_x - 0.1)
    canvas = cv2.copyMakeBorder(
        resized, top, size - new_h - top, left, size - new_w - left,
        cv2.BORDER_CONSTANT, value=(LETTERBOX_FILL,) * 3,
    )
    tensor = canvas.transpose(2, 0, 1)[None].astype(np.float32) / 255.0
    return np.ascontiguousarray(tensor), scale, float(left), float(top)


def decode(
    output: np.ndarray, scale: float, pad_x: float, pad_y: float,
    width: int, height: int, score_threshold: float,
) -> np.ndarray:
    """People above ``score_threshold`` as (N, 57) rows in source-frame pixels.

    The end-to-end head already removes duplicates, so no NMS is applied.
    """

    rows = np.asarray(output, dtype=np.float32).reshape(-1, ROW_WIDTH)
    rows = rows[np.isfinite(rows).all(axis=1) & (rows[:, 4] >= score_threshold)].copy()
    if not len(rows):
        return rows
    rows[:, [0, 2]] = (rows[:, [0, 2]] - pad_x) / scale
    rows[:, [1, 3]] = (rows[:, [1, 3]] - pad_y) / scale
    keypoints = rows[:, 6:].reshape(-1, 17, 3)
    keypoints[..., 0] = (keypoints[..., 0] - pad_x) / scale
    keypoints[..., 1] = (keypoints[..., 1] - pad_y) / scale
    rows[:, [0, 2]] = rows[:, [0, 2]].clip(0, width)
    rows[:, [1, 3]] = rows[:, [1, 3]].clip(0, height)
    rows[:, 6:] = keypoints.reshape(len(rows), -1)
    return rows


class Yolo26PoseExtractor:
    """One-shot YOLO26n-pose: person boxes and COCO-17 keypoints in one ONNX pass.

    Stateless per frame, so ``fork`` only needs to share the loaded session.
    """

    def __init__(self, session: Any, *, score_threshold: float = 0.35, model_version: str = "") -> None:
        self._session = session
        self._input_name = session.get_inputs()[0].name
        self.score_threshold = score_threshold
        self.model_version = model_version

    @classmethod
    def load(cls, model_path: Path, *, device: str = "cpu", score_threshold: float = 0.35) -> "Yolo26PoseExtractor":
        model_path = Path(model_path)
        metadata_path = model_path.with_suffix(".json")
        if not model_path.is_file():
            raise PoseModelError(f"Pose model not found: {model_path.name}")
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PoseModelError(f"Pose model metadata not readable: {metadata_path.name}") from exc
        digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
        if digest != metadata.get("sha256"):
            raise PoseModelError(f"{model_path.name} does not match the SHA-256 in {metadata_path.name}")
        if device != "cpu":
            raise PoseModelError(f"Only the CPU provider is supported, not {device!r}")

        import onnxruntime as ort

        session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        inputs, outputs = session.get_inputs(), session.get_outputs()
        if len(inputs) != 1 or list(inputs[0].shape) != [1, 3, INPUT_SIZE, INPUT_SIZE]:
            raise PoseModelError(f"Unexpected pose input {[(i.name, i.shape) for i in inputs]}")
        if len(outputs) != 1 or list(outputs[0].shape) != [1, MAX_DETECTIONS, ROW_WIDTH]:
            raise PoseModelError(f"Unexpected pose output {[(o.name, o.shape) for o in outputs]}")
        extractor = cls(session, score_threshold=score_threshold,
                        model_version=f"{model_path.name}@{digest[:12]}")
        # Real forward pass so a broken file fails at load, not on the first visitor.
        extractor.extract(np.full((INPUT_SIZE, INPUT_SIZE, 3), LETTERBOX_FILL, np.uint8), 0.0)
        return extractor

    def fork(self) -> "Yolo26PoseExtractor":
        return self

    def extract(self, frame_rgb: np.ndarray, timestamp_seconds: float) -> PoseFrame | None:
        started = perf_counter()
        height, width = frame_rgb.shape[:2]
        tensor, scale, pad_x, pad_y = letterbox(frame_rgb)
        output = self._session.run(None, {self._input_name: tensor})[0]
        people = decode(output, scale, pad_x, pad_y, width, height, self.score_threshold)
        if not len(people):
            return None
        areas = (people[:, 2] - people[:, 0]) * (people[:, 3] - people[:, 1])
        primary = people[int(np.argmax(areas))]  # same rule as before: the largest person
        return PoseFrame(
            timestamp_seconds=float(timestamp_seconds),
            keypoints=primary[6:].reshape(17, 3).copy(),
            bbox=primary[:4].copy(),
            detected_people=len(people),
            frame_width=width,
            frame_height=height,
            inference_ms=(perf_counter() - started) * 1000,
        )
