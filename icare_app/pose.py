from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import perf_counter

import cv2
import numpy as np


DETECTOR_URL = (
    "https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/"
    "yolox_tiny_8xb8-300e_humanart-6f3252f9.zip"
)
POSE_URL = (
    "https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/"
    "rtmpose-s_simcc-body7_pt-body7_420e-256x192-acd4a1ef_20230504.zip"
)

@dataclass(frozen=True)
class PoseFrame:
    timestamp_seconds: float
    keypoints: np.ndarray  # (17, 3): x, y, confidence
    bbox: np.ndarray  # (4,): x1, y1, x2, y2
    detected_people: int
    frame_width: int
    frame_height: int
    inference_ms: float


class RTMPoseExtractor:
    """YOLOX-tiny person detection followed by RTMPose-s COCO-17 pose."""

    def __init__(
        self,
        device: str = "cpu",
        detection_threshold: float = 0.35,
        detection_frequency: int = 3,
    ) -> None:
        try:
            from rtmlib import RTMPose, YOLOX
        except ImportError as exc:
            raise RuntimeError(
                "RTMPose dependencies are missing. Run: "
                "python -m pip install -r requirements.txt"
            ) from exc

        self.detection_threshold = detection_threshold
        self.detection_frequency = max(1, detection_frequency)
        self.lock = Lock()
        self.frame_index = 0
        self.primary_box: np.ndarray | None = None
        self.detected_people = 0
        self.detector = YOLOX(
            DETECTOR_URL,
            model_input_size=(416, 416),
            backend="onnxruntime",
            device=device,
        )
        self.pose_estimator = RTMPose(
            POSE_URL,
            model_input_size=(192, 256),
            backend="onnxruntime",
            device=device,
            to_openpose=False,
        )

    def reset(self) -> None:
        self.frame_index = 0
        self.primary_box = None
        self.detected_people = 0

    def fork(self) -> "RTMPoseExtractor":
        """Return an extractor sharing the loaded models but with fresh tracking state.

        Each offline job forks its own extractor so detector box reuse and frame
        counters can never carry from one clip to another.
        """
        clone = object.__new__(RTMPoseExtractor)
        clone.__dict__.update(self.__dict__)
        clone.reset()
        return clone

    def extract(
        self, frame_rgb: np.ndarray, timestamp_seconds: float
    ) -> PoseFrame | None:
        started = perf_counter()
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        run_detector = (
            self.primary_box is None
            or self.frame_index % self.detection_frequency == 0
        )
        self.frame_index += 1

        if run_detector:
            with self.lock:
                boxes = np.asarray(self.detector(frame_bgr), dtype=np.float32)
            if boxes.size == 0:
                self.primary_box = None
                self.detected_people = 0
                return None
            boxes = boxes.reshape(-1, boxes.shape[-1])
            if boxes.shape[1] >= 5:
                boxes = boxes[boxes[:, 4] >= self.detection_threshold]
            if len(boxes) == 0:
                self.primary_box = None
                self.detected_people = 0
                return None
            areas = np.maximum(0, boxes[:, 2] - boxes[:, 0]) * np.maximum(
                0, boxes[:, 3] - boxes[:, 1]
            )
            primary_index = int(np.argmax(areas))
            self.primary_box = boxes[primary_index : primary_index + 1]
            self.detected_people = len(boxes)

        with self.lock:
            coordinates, scores = self.pose_estimator(
                frame_bgr, bboxes=self.primary_box
            )
        coordinates = np.asarray(coordinates, dtype=np.float32)
        scores = np.asarray(scores, dtype=np.float32)
        if coordinates.size == 0 or scores.size == 0:
            return None

        coordinates = coordinates.reshape(-1, 17, 2)[0]
        scores = scores.reshape(-1, 17)[0]
        keypoints = np.concatenate((coordinates, scores[:, None]), axis=1)
        return PoseFrame(
            timestamp_seconds=float(timestamp_seconds),
            keypoints=keypoints,
            bbox=self.primary_box[0, :4].copy(),
            detected_people=self.detected_people,
            frame_width=frame_rgb.shape[1],
            frame_height=frame_rgb.shape[0],
            inference_ms=(perf_counter() - started) * 1000,
        )
