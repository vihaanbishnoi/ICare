"""One-pass YOLO26n person detection and COCO-17 pose estimation on CPU."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from threading import Lock
from time import perf_counter

import cv2
import numpy as np


DEFAULT_POSE_MODEL = Path(__file__).resolve().parents[3] / "models" / "yolo26n-pose.onnx"
INPUT_SIZE = 640


@dataclass(frozen=True)
class PoseFrame:
    timestamp_seconds: float
    keypoints: np.ndarray  # (17, 3): x, y, confidence; COCO joint order
    bbox: np.ndarray  # (4,): x1, y1, x2, y2
    detected_people: int
    frame_width: int
    frame_height: int
    inference_ms: float


class YOLOPoseExtractor:
    """A fixed, NMS-free YOLO26n-pose ONNX export; largest visible person wins.

    The model returns boxes and joints together for every sampled frame. There
    are no cached boxes or per-clip tracking state. Models are loaded locally;
    inference never downloads weights or imports PyTorch/Ultralytics.
    """

    def __init__(self, model_path: Path = DEFAULT_POSE_MODEL, device: str = "cpu",
                 detection_threshold: float = 0.35) -> None:
        if device != "cpu":
            raise ValueError("Only CPU pose inference is supported")
        if not 0 < detection_threshold <= 1:
            raise ValueError("detection_threshold must be in (0, 1]")
        model_path = Path(model_path)
        if not model_path.is_file():
            raise FileNotFoundError(f"YOLO26n-pose weights not found: {model_path.name}")
        from icare.inference.runtime import cpu_session

        self.session = cpu_session(model_path)
        inputs, outputs = self.session.get_inputs(), self.session.get_outputs()
        if (self.session.get_providers() != ["CPUExecutionProvider"]
                or len(inputs) != 1 or inputs[0].shape != [1, 3, INPUT_SIZE, INPUT_SIZE]
                or inputs[0].type != "tensor(float)"
                or len(outputs) != 1 or outputs[0].shape != [1, 300, 57]):
            raise ValueError("Expected YOLO26n-pose ONNX: float32 1x3x640x640 → 1x300x57")
        metadata = self.session.get_modelmeta().custom_metadata_map
        if metadata.get("task") != "pose" or metadata.get("kpt_shape") != "[17, 3]":
            raise ValueError("Pose model must identify COCO-17 keypoints with confidence")
        self.input_name, self.output_name = inputs[0].name, outputs[0].name
        self.detection_threshold = detection_threshold
        self.lock = Lock()
        digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
        self.model_version = f"yolo26n-pose.onnx@{digest[:12]}"
        self._predict(np.zeros((1, 3, INPUT_SIZE, INPUT_SIZE), dtype=np.float32))

    def fork(self) -> "YOLOPoseExtractor":
        """Share the immutable model; every call computes fresh detections."""
        return self

    def _predict(self, tensor: np.ndarray) -> np.ndarray:
        with self.lock:
            output = np.asarray(self.session.run([self.output_name], {self.input_name: tensor})[0])
        if output.shape != (1, 300, 57) or not np.isfinite(output).all():
            raise ValueError("YOLO26n-pose returned invalid detections")
        rows = output[0]
        if np.any((rows[:, 4] < 0) | (rows[:, 4] > 1)):
            raise ValueError("YOLO26n-pose returned invalid detection confidence")
        return rows

    def extract(self, frame_rgb: np.ndarray, timestamp_seconds: float) -> PoseFrame | None:
        started = perf_counter()
        height, width = frame_rgb.shape[:2]
        if frame_rgb.ndim != 3 or frame_rgb.shape[2] != 3 or min(height, width) < 1:
            raise ValueError("Pose input must be a non-empty RGB image")
        tensor, scale, left, top = _letterbox(frame_rgb)
        rows = self._predict(tensor)
        rows = rows[(rows[:, 4] >= self.detection_threshold) & (rows[:, 5] == 0)]
        if not len(rows):
            return None

        # Undo square padding and resize, so both boxes and joints use frame pixels.
        boxes = (rows[:, :4] - np.array([left, top, left, top])) / scale
        boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, width)
        boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, height)
        areas = np.maximum(0, boxes[:, 2] - boxes[:, 0]) * np.maximum(0, boxes[:, 3] - boxes[:, 1])
        visible = areas > 0
        rows, boxes, areas = rows[visible], boxes[visible], areas[visible]
        if not len(rows):
            return None
        primary = int(np.argmax(areas))
        keypoints = rows[primary, 6:].reshape(17, 3).copy()
        if np.any((keypoints[:, 2] < 0) | (keypoints[:, 2] > 1)):
            raise ValueError("YOLO26n-pose returned invalid keypoint confidence")
        keypoints[:, 0] = ((keypoints[:, 0] - left) / scale).clip(0, width)
        keypoints[:, 1] = ((keypoints[:, 1] - top) / scale).clip(0, height)
        return PoseFrame(
            timestamp_seconds=float(timestamp_seconds), keypoints=keypoints,
            bbox=boxes[primary].astype(np.float32), detected_people=len(rows),
            frame_width=width, frame_height=height,
            inference_ms=(perf_counter() - started) * 1000,
        )


def _letterbox(frame_rgb: np.ndarray) -> tuple[np.ndarray, float, int, int]:
    """Keep aspect ratio, center on a 114-gray square, normalize RGB to NCHW."""
    height, width = frame_rgb.shape[:2]
    scale = min(INPUT_SIZE / height, INPUT_SIZE / width)
    resized_width, resized_height = round(width * scale), round(height * scale)
    left = round((INPUT_SIZE - resized_width) / 2 - 0.1)
    top = round((INPUT_SIZE - resized_height) / 2 - 0.1)
    image = np.full((INPUT_SIZE, INPUT_SIZE, 3), 114, dtype=np.uint8)
    image[top:top + resized_height, left:left + resized_width] = cv2.resize(
        frame_rgb, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
    tensor = np.ascontiguousarray(image.transpose(2, 0, 1)[None], dtype=np.float32) / 255.0
    return tensor, scale, left, top
