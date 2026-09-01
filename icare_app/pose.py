from __future__ import annotations

from dataclasses import dataclass
from threading import Condition, Lock, Thread
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

# COCO-17 joint connections (zero based).
COCO_EDGES = (
    (0, 1), (0, 2), (1, 3), (2, 4),
    (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 11), (6, 12), (11, 12),
    (11, 13), (13, 15), (12, 14), (14, 16),
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
        keypoint_threshold: float = 0.30,
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
        self.keypoint_threshold = keypoint_threshold
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

    def draw(self, frame_rgb: np.ndarray, pose: PoseFrame | None) -> np.ndarray:
        if pose is None:
            return frame_rgb
        output = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        scale_x = frame_rgb.shape[1] / pose.frame_width
        scale_y = frame_rgb.shape[0] / pose.frame_height
        points = pose.keypoints.copy()
        points[:, 0] *= scale_x
        points[:, 1] *= scale_y
        bbox = pose.bbox * np.array([scale_x, scale_y, scale_x, scale_y])
        x1, y1, x2, y2 = np.rint(bbox).astype(int)
        cv2.rectangle(output, (x1, y1), (x2, y2), (72, 210, 255), 2)

        for first, second in COCO_EDGES:
            if (
                points[first, 2] >= self.keypoint_threshold
                and points[second, 2] >= self.keypoint_threshold
            ):
                p1 = tuple(np.rint(points[first, :2]).astype(int))
                p2 = tuple(np.rint(points[second, :2]).astype(int))
                cv2.line(output, p1, p2, (80, 220, 110), 2, cv2.LINE_AA)
        for x, y, confidence in points:
            if confidence >= self.keypoint_threshold:
                cv2.circle(output, (round(float(x)), round(float(y))), 3, (245, 90, 80), -1)

        cv2.putText(
            output,
            f"RTMPose | {pose.inference_ms:.0f} ms | people: {pose.detected_people}",
            (max(8, x1), max(24, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (72, 210, 255),
            2,
            cv2.LINE_AA,
        )
        return cv2.cvtColor(output, cv2.COLOR_BGR2RGB)


class PosePreviewBackend:
    """Pose visualization now; PoseC3D probability is connected after training."""

    available = False
    name = "RTMPose ready; PoseC3D pending"

    def __init__(self, device: str = "cpu", inference_width: int = 640) -> None:
        from icare_app.posec3d_bridge import PoseSequenceBuffer

        self.extractor = RTMPoseExtractor(device=device)
        self.inference_width = inference_width
        self.sequence_buffer = PoseSequenceBuffer()
        self.latest_pose: PoseFrame | None = None
        self.latest_error: str | None = None
        self._condition = Condition()
        self._pending: tuple[np.ndarray, float, int] | None = None
        self._generation = 0
        self._worker = Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def reset(self) -> None:
        with self._condition:
            self._generation += 1
            self._pending = None
            self.latest_pose = None
            self.latest_error = None
            self.sequence_buffer.clear()
            self.extractor.reset()

    def process_frame(self, frame_rgb: np.ndarray, timestamp_seconds: float):
        height, width = frame_rgb.shape[:2]
        if width > self.inference_width:
            scale = self.inference_width / width
            inference_frame = cv2.resize(
                frame_rgb,
                (self.inference_width, max(1, round(height * scale))),
                interpolation=cv2.INTER_AREA,
            )
        else:
            inference_frame = frame_rgb.copy()
        with self._condition:
            # Overwrite instead of enqueueing: stale frames are deliberately dropped.
            self._pending = (
                inference_frame,
                float(timestamp_seconds),
                self._generation,
            )
            self._condition.notify()
        return None

    def annotate_frame(self, frame_rgb: np.ndarray) -> np.ndarray:
        with self._condition:
            pose = self.latest_pose
            pose_count = self.sequence_buffer.pose_count
            coverage = self.sequence_buffer.coverage_seconds
            error = self.latest_error
        output = self.extractor.draw(frame_rgb, pose)
        message = (
            f"Pose buffer: {pose_count}/6 | {coverage:.1f}/2.0 s"
            if error is None
            else f"Inference error: {error[:70]}"
        )
        cv2.putText(
            output,
            message,
            (16, max(124, output.shape[0] - 18)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        return output

    def on_pose_ready(self, pose: PoseFrame) -> None:
        """Extension point for the PoseC3D backend."""
        del pose

    def _worker_loop(self) -> None:
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._pending is not None)
                frame_rgb, timestamp_seconds, generation = self._pending
                self._pending = None
            try:
                pose = self.extractor.extract(frame_rgb, timestamp_seconds)
            except Exception as exc:
                with self._condition:
                    if generation == self._generation:
                        self.latest_error = f"{type(exc).__name__}: {exc}"
                continue
            with self._condition:
                if generation == self._generation:
                    self.latest_error = None
                    self.latest_pose = pose
                    if pose is not None:
                        self.sequence_buffer.append(pose)
            if pose is not None and generation == self._generation:
                try:
                    self.on_pose_ready(pose)
                except Exception as exc:
                    with self._condition:
                        if generation == self._generation:
                            self.latest_error = f"{type(exc).__name__}: {exc}"
