"""Deterministic offline fall-analysis engine (inference contract v1).

Importing this module loads no model and touches no network: onnxruntime
and psutil are imported only inside ``load_engine`` and the helpers it calls.
The API adapter implements the same callbacks without importing HTTP code.
"""
from __future__ import annotations

import logging
import math
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Iterator, Mapping, Protocol

import numpy as np

from icare.inference.pose import DEFAULT_POSE_MODEL, PoseFrame
from icare.inference.pose_signals import PoseSignalEstimator
from icare.inference.posec3d_bridge import PoseSequenceBuffer
from icare.inference.tracking import PersonTracker


log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- errors


class EngineError(Exception):
    """Base class. ``code`` is passed through by the API as the job error code."""

    code = "engine_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ModelUnavailableError(EngineError):
    """Weights, metadata or pose models are missing or fail verification."""

    code = "model_unavailable"


class InvalidVideoError(EngineError):
    code = "invalid_video"


class NoPersonError(EngineError):
    code = "no_person"


class InsufficientCoverageError(EngineError):
    code = "insufficient_temporal_coverage"


class ModelRuntimeError(EngineError):
    """A loaded model failed or returned an invalid result while analysing a clip."""

    code = "model_error"


class AnalysisCancelled(EngineError):
    code = "cancelled"


class EngineClosedError(EngineError):
    code = "engine_closed"


# -------------------------------------------------------------------- configuration

OUTPUT_PRECISION = 4  # decimals kept for pixel coordinates in emitted records
# PoseC3D runs per person (~0.2 s each on a laptop CPU). A camera frame classifies
# at most this many due people, most overdue first, so crowds cannot stall the
# stream; recorded videos classify everyone who is due.
LIVE_PREDICTIONS_PER_FRAME = 2


@dataclass(frozen=True)
class EngineConfig:
    """Validated settings for source sampling and temporal inference."""

    model_path: Path
    pose_model_path: Path = DEFAULT_POSE_MODEL
    metadata_path: Path | None = None
    device: str = "cpu"
    sample_fps: float = 6.0
    inference_width: int = 416
    prediction_interval_seconds: float = 0.75
    # A person missing for longer than this ends the track: the temporal window
    # restarts instead of interpolating a pose across the absence. None disables.
    max_pose_gap_seconds: float | None = 1.0
    # How long an unseen person keeps their ID (occlusion, missed detections).
    track_max_age_seconds: float = 2.0

    def __post_init__(self) -> None:
        if not (math.isfinite(self.sample_fps) and self.sample_fps > 0):
            raise ValueError("sample_fps must be a positive number")
        if self.inference_width < 64:
            raise ValueError("inference_width must be at least 64 pixels")
        if self.prediction_interval_seconds < 0:
            raise ValueError("prediction_interval_seconds must not be negative")
        if not (math.isfinite(self.track_max_age_seconds) and self.track_max_age_seconds > 0):
            raise ValueError("track_max_age_seconds must be a positive number")

    @classmethod
    def from_mapping(cls, config: Mapping[str, Any]) -> "EngineConfig":
        """Build from the ``{"model_path", "device"}`` mapping the API passes.

        Unknown keys are rejected so a misspelt setting cannot be ignored silently.
        ICARE_INFERENCE_WIDTH (listed in .env.example) is honoured when the
        mapping does not set ``inference_width``.
        """

        values = dict(config)
        known = {
            "model_path", "metadata_path", "device", "sample_fps", "inference_width",
            "prediction_interval_seconds", "max_pose_gap_seconds", "pose_model_path",
            "track_max_age_seconds",
        }
        unknown = sorted(set(values) - known)
        if unknown:
            raise ValueError(f"Unknown engine settings: {', '.join(unknown)}")
        if "model_path" not in values:
            raise ValueError("model_path is required")
        values["model_path"] = Path(values["model_path"])
        if "pose_model_path" in values:
            values["pose_model_path"] = Path(values["pose_model_path"])
        if values.get("metadata_path") is not None:
            values["metadata_path"] = Path(values["metadata_path"])
        if "inference_width" not in values and os.environ.get("ICARE_INFERENCE_WIDTH"):
            values["inference_width"] = int(os.environ["ICARE_INFERENCE_WIDTH"])
        return cls(**values)


# ----------------------------------------------------------------------- boundaries


class PoseExtractor(Protocol):
    """Pose source. ``fork`` returns a clip-safe source with no stale tracking state."""

    def fork(self) -> "PoseExtractor": ...

    def extract_all(self, frame_rgb: np.ndarray, timestamp_seconds: float) -> list[PoseFrame]:
        """COCO-17 poses of every detected person in ``frame_rgb`` coordinates."""


class TemporalClassifier(Protocol):
    model_version: str

    def predict(self, tensor: np.ndarray) -> float:
        """Fall probability in [0, 1] for one (1, 17, 48, 64, 64) float32 window."""

    def close(self) -> None: ...


class ResourceSampler:
    """Process-level CPU/RSS samples (psutil). Empty when psutil is unavailable.

    cpu_percent is the share of one core used by this whole process (all threads,
    so it may exceed 100) since the previous sample. rss is resident memory in MB.
    """

    def __init__(self) -> None:
        self._process = None
        self.cpu: list[float] = []
        self.rss_mb: list[float] = []
        try:
            import psutil

            self._process = psutil.Process()
            self._process.cpu_percent(interval=None)  # baseline for the first delta
        except (ImportError, OSError):
            self._process = None

    def sample(self) -> None:
        if self._process is None:
            return
        try:
            self.cpu.append(float(self._process.cpu_percent(interval=None)))
            self.rss_mb.append(float(self._process.memory_info().rss / (1024 * 1024)))
        except OSError:
            pass


# ------------------------------------------------------------------- frame sampling


@dataclass(frozen=True)
class SourceFrame:
    index: int
    timestamp_seconds: float
    frame_rgb: np.ndarray


class OpenCvFrameSource:
    """Sequential decoder yielding the frames chosen by a deterministic rule.

    Sample slot k lies at k / sample_fps source seconds and is served by decoded
    frame round(k * fps / sample_fps). Only video timestamps (frame_index / fps)
    are used, never wall-clock decoding speed, so a clip always yields the same
    samples. When sample_fps >= fps every frame is used once.
    """

    def __init__(self, path: Path, sample_fps: float) -> None:
        import cv2

        self._cv2 = cv2
        self._sample_fps = float(sample_fps)
        self._capture = cv2.VideoCapture(str(path))
        if not self._capture.isOpened():
            self._capture.release()
            raise InvalidVideoError("The file could not be opened as a video.")
        fps = float(self._capture.get(cv2.CAP_PROP_FPS) or 0.0)
        if not (math.isfinite(fps) and 0.0 < fps <= 1000.0):
            self._capture.release()
            raise InvalidVideoError("The video does not report a usable frame rate.")
        self.fps = fps
        reported = float(self._capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        self.frame_count_reported = int(reported) if math.isfinite(reported) and reported > 0 else None
        self.frames_decoded = 0
        self.undecodable_samples = 0

    def close(self) -> None:
        self._capture.release()

    def samples(self) -> Iterator[SourceFrame]:
        cv2 = self._cv2
        index = 0
        slot = 0
        target = 0
        while self._capture.grab():
            self.frames_decoded = index + 1
            if index == target:
                ok, frame_bgr = self._capture.retrieve()
                if ok and frame_bgr is not None:
                    yield SourceFrame(
                        index, index / self.fps, cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                    )
                else:
                    self.undecodable_samples += 1
                while target <= index:
                    slot += 1
                    target = math.floor(slot * self.fps / self._sample_fps + 0.5)
            index += 1


def _resize_for_inference(frame_rgb: np.ndarray, width: int) -> np.ndarray:
    import cv2

    height_src, width_src = frame_rgb.shape[:2]
    if width_src <= width:
        return frame_rgb
    height = max(1, round(height_src * width / width_src))
    return cv2.resize(frame_rgb, (width, height), interpolation=cv2.INTER_AREA)


# ----------------------------------------------------------------------------- engine

PoseCallback = Callable[[Mapping[str, Any]], None]
PredictionCallback = Callable[[Mapping[str, Any]], None]
ProgressCallback = Callable[[float | None], None]


class PoseC3DEngine:
    """Pose extraction + PoseC3D over a whole clip, one clip at a time.

    All per-clip state (pose session, temporal buffer, signal estimator, records)
    is created inside ``analyze_video`` and discarded when it returns, so clips
    cannot influence each other. Only the loaded, read-only models are shared; a
    lock admits one clip at a time (higher concurrency needs measured capacity).
    """

    def __init__(
        self,
        config: EngineConfig,
        extractor: PoseExtractor,
        classifier: TemporalClassifier,
        *,
        window_seconds: float = 4.0,
        clip_len: int = 48,
        minimum_poses: int = 6,
        minimum_coverage_seconds: float = 2.0,
        info: Mapping[str, Any] | None = None,
    ) -> None:
        self.config = config
        pose_version = getattr(extractor, "model_version", None)
        self.model_version: str | None = (
            f"{classifier.model_version}+{pose_version}" if pose_version else classifier.model_version
        )
        self._extractor: PoseExtractor | None = extractor
        self._classifier: TemporalClassifier | None = classifier
        self._buffer_settings = {
            "window_seconds": window_seconds,
            "clip_len": clip_len,
            "minimum_poses": minimum_poses,
            "minimum_coverage_seconds": minimum_coverage_seconds,
        }
        self._info = dict(info or {})
        self._job_lock = threading.Lock()
        self._closed = threading.Event()

    @property
    def ready(self) -> bool:
        return not self._closed.is_set() and self._classifier is not None

    def describe(self) -> dict[str, Any]:
        """Settings and verified model facts, for readiness and provenance records."""

        return {
            **self._info,
            "model_version": self.model_version,
            "device": self.config.device,
            "sample_fps": self.config.sample_fps,
            "inference_width": self.config.inference_width,
            "prediction_interval_seconds": self.config.prediction_interval_seconds,
            "max_pose_gap_seconds": self.config.max_pose_gap_seconds,
            "pose_architecture": "YOLO26n-pose",
            "track_max_age_seconds": self.config.track_max_age_seconds,
            **{key: value for key, value in self._buffer_settings.items()},
        }

    def close(self) -> None:
        """Stop accepting clips, wait briefly for a running one, release the models."""

        self._closed.set()
        if self._job_lock.acquire(timeout=10):
            try:
                classifier, self._classifier = self._classifier, None
                self._extractor = None
                if classifier is not None:
                    classifier.close()
            finally:
                self._job_lock.release()

    # ------------------------------------------------------------------ analysis

    def analyze_video(
        self,
        video_path: str | Path,
        *,
        on_pose: PoseCallback,
        on_prediction: PredictionCallback,
        on_progress: ProgressCallback,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        """Analyse one clip and return its summary after the final prediction.

        Records are emitted in video-time order through the callbacks. Failures
        raise EngineError subclasses whose ``code`` identifies the cause. An
        exception raised by a callback (for example the API's cancellation from
        on_progress) propagates after the clip's resources are released.
        """

        cancel = cancel_event if cancel_event is not None else threading.Event()
        self._acquire(cancel)
        try:
            self._check_live(cancel)
            return self._analyze(Path(video_path), on_pose, on_prediction, on_progress, cancel)
        finally:
            self._job_lock.release()

    def _acquire(self, cancel: threading.Event) -> None:
        while not self._job_lock.acquire(timeout=0.1):
            self._check_live(cancel)
        # Closed while waiting: release immediately and report distinctly.
        if self._closed.is_set():
            self._job_lock.release()
            raise EngineClosedError("The engine has been closed.")

    def _check_live(self, cancel: threading.Event) -> None:
        if self._closed.is_set():
            raise EngineClosedError("The engine has been closed.")
        if cancel.is_set():
            raise AnalysisCancelled("The analysis was cancelled.")

    def start_stream(self, max_predictions_per_frame: int | None = LIVE_PREDICTIONS_PER_FRAME) -> "FrameSession":
        """Reserve the model for a fresh camera session until close()."""
        if not self._job_lock.acquire(blocking=False):
            raise ModelRuntimeError("The model is already processing another source.")
        try:
            self._check_live(threading.Event())
            return FrameSession(self, release=self._job_lock.release,
                                max_predictions_per_frame=max_predictions_per_frame)
        except BaseException:
            self._job_lock.release()
            raise

    def _analyze(self, path, on_pose, on_prediction, on_progress, cancel):
        if not path.is_file():
            raise InvalidVideoError("The video file does not exist.")
        started = perf_counter()
        source = OpenCvFrameSource(path, self.config.sample_fps)
        session = FrameSession(self)
        try:
            on_progress(0.0)
            for item in source.samples():
                self._check_live(cancel)
                record = session.process_frame(item.frame_rgb, item.timestamp_seconds)
                for pose in record["poses"]:
                    on_pose(pose)
                for prediction in record["predictions"]:
                    on_prediction(prediction)
                total = source.frame_count_reported
                on_progress(min((item.index + 1) / total, 0.99) if total else None)
            self._check_live(cancel)
            if source.frames_decoded == 0 or session.frame_size is None:
                raise InvalidVideoError("No frame of the video could be decoded.")
            for prediction in session.finish():
                on_prediction(prediction)
            if session.poses_emitted == 0:
                raise NoPersonError("No person was detected in the sampled frames.")
            if session.predictions_emitted == 0:
                raise InsufficientCoverageError(
                    f"{session.poses_emitted} pose(s) found, but the model needs at least "
                    f"{self._buffer_settings['minimum_poses']} poses spanning "
                    f"{self._buffer_settings['minimum_coverage_seconds']:g} s of one person's continuous track.")
            width, height = session.frame_size
            return {
                "duration_seconds": round(source.frames_decoded / source.fps, 6),
                "frame_width": width, "frame_height": height,
                "metrics": {**_metrics(source, session.resources, session.sampled,
                    session.frames_with_people, session.predictions_emitted, session.track_resets,
                    session.pose_ms_total, perf_counter() - started, self.config),
                    "pose_records": session.poses_emitted,
                    "people_tracked": session.tracker.ids_issued,
                    "max_people_in_frame": session.max_people_in_frame},
            }
        finally:
            source.close()
            session.close()


@dataclass
class _Person:
    """Temporal state of one tracked person; nothing here is shared between people."""

    buffer: PoseSequenceBuffer
    signals: PoseSignalEstimator
    last_pose_t: float | None = None
    last_prediction_t: float = float("-inf")
    latest_signals: Any = None


class FrameSession:
    """Per-source state shared by recorded-video and live-camera execution.

    Every person gets their own track ID, pose window, signals and prediction
    cadence, so one person's movement can never enter another's model input.
    Uses capture timestamps, not completion time. Sparse or interrupted capture
    keeps the original coverage/gap checks; it never fabricates missing poses.
    """

    def __init__(self, engine: PoseC3DEngine, release=lambda: None,
                 max_predictions_per_frame: int | None = None):
        assert engine._extractor is not None and engine._classifier is not None
        if max_predictions_per_frame is not None and max_predictions_per_frame < 1:
            raise ValueError("max_predictions_per_frame must be at least 1")
        self.engine = engine
        self.extractor = engine._extractor.fork()
        self.classifier = engine._classifier
        self.tracker = PersonTracker(max_age_seconds=engine.config.track_max_age_seconds)
        self.people: dict[int, _Person] = {}
        self.max_predictions_per_frame = max_predictions_per_frame
        self.resources = ResourceSampler()
        self.frame_size = None
        self.sampled = self.poses_emitted = self.frames_with_people = 0
        self.predictions_emitted = self.track_resets = self.max_people_in_frame = 0
        self.pose_ms_total = 0.0
        self.last_frame_t = None
        self._release, self.closed = release, False

    def close(self):
        if not self.closed:
            self.closed = True
            self.people.clear()
            self._release()

    def _person(self, track_id: int) -> _Person:
        if track_id not in self.people:
            self.people[track_id] = _Person(PoseSequenceBuffer(**self.engine._buffer_settings), PoseSignalEstimator())
        return self.people[track_id]

    def process_frame(self, frame_rgb: np.ndarray, timestamp_seconds: float) -> dict:
        if self.closed or self.engine._closed.is_set():
            raise EngineClosedError("The source session is closed.")
        t = float(timestamp_seconds)
        if not math.isfinite(t) or t < 0 or (self.last_frame_t is not None and t <= self.last_frame_t):
            raise InvalidVideoError("Capture timestamps must be finite, nonnegative and increasing.")
        height, width = frame_rgb.shape[:2]
        if self.frame_size is not None and self.frame_size != (width, height):
            raise InvalidVideoError("The video changes resolution part-way through.")
        self.frame_size, self.last_frame_t = (width, height), t
        self.sampled += 1
        frame = _resize_for_inference(frame_rgb, self.engine.config.inference_width)
        try:
            found = self.extractor.extract_all(frame, t)
        except EngineError:
            raise
        except Exception as exc:
            raise ModelRuntimeError(f"Pose estimation failed: {type(exc).__name__}: {exc}") from exc
        poses = [_to_source_coordinates(pose, width / frame.shape[1], height / frame.shape[0], width, height)
                 for pose in found]
        assignments = self.tracker.update(poses, t)
        for track_id in self.tracker.expired:
            self.people.pop(track_id, None)  # bounded memory: forgotten people free their window
        if poses:
            self.frames_with_people += 1
            self.pose_ms_total += float(found[0].inference_ms)  # one model pass serves everyone
            self.max_people_in_frame = max(self.max_people_in_frame, len(poses))

        pose_records, people, due = [], [], []
        gap = self.engine.config.max_pose_gap_seconds
        for track_id, pose in assignments:
            person = self._person(track_id)
            if person.last_pose_t is not None and gap is not None and t - person.last_pose_t > gap:
                person.buffer.clear()
                person.signals.reset()
                self.track_resets += 1
            person.last_pose_t = t
            person.latest_signals = person.signals.update(pose)
            person.buffer.append(pose)
            self.poses_emitted += 1
            pose_records.append(_pose_record(pose, track_id))
            interval = self.engine.config.prediction_interval_seconds
            if person.buffer.ready and t - person.last_prediction_t >= interval:
                due.append(track_id)
            people.append({"track_id": track_id,
                           "status": "monitoring" if person.buffer.ready else "warming_up",
                           "coverage_seconds": person.buffer.coverage_seconds,
                           "pose_count": person.buffer.pose_count})
        # Most overdue first; live sessions may cap the work done per frame.
        due.sort(key=lambda tid: (self.people[tid].last_prediction_t, tid))
        if self.max_predictions_per_frame is not None:
            due = due[:self.max_predictions_per_frame]
        predictions = [p for p in (self._predict(tid) for tid in sorted(due)) if p is not None]
        status = ("no_person" if not people else
                  "monitoring" if any(p["status"] == "monitoring" for p in people) else "warming_up")
        return {"timestamp_seconds": _seconds(t), "poses": pose_records, "predictions": predictions,
                "people": people, "status": status, "track_resets": self.track_resets,
                "frame_width": width, "frame_height": height}

    def _predict(self, track_id: int):
        person = self.people[track_id]
        model_input = person.buffer.build()
        if model_input is None:
            return None
        started = perf_counter()
        try:
            probability = self.classifier.predict(model_input.tensor)
        except EngineError:
            raise
        except Exception as exc:
            raise ModelRuntimeError(f"PoseC3D inference failed: {type(exc).__name__}: {exc}") from exc
        inference_ms = (perf_counter() - started) * 1000.0
        probability = _checked_probability(probability)
        self.resources.sample()
        self.predictions_emitted += 1
        person.last_prediction_t = float(model_input.end_seconds)
        return {"track_id": track_id, "timestamp_seconds": _seconds(model_input.end_seconds),
                "fall_probability": probability,
                "window_start_seconds": _seconds(model_input.start_seconds),
                "source_pose_count": int(model_input.source_pose_count), "inference_ms": round(inference_ms, 3),
                "urgency": _optional(person.latest_signals, "urgency"),
                "reliability": _optional(person.latest_signals, "reliability")}

    def finish(self) -> list[dict]:
        """Offline-only drain: classify each person's final valid window once."""
        final = []
        for track_id in sorted(self.people):
            person = self.people[track_id]
            if person.buffer.ready and person.last_pose_t is not None and person.last_pose_t > person.last_prediction_t:
                prediction = self._predict(track_id)
                if prediction is not None:
                    final.append(prediction)
        return final


# ----------------------------------------------------------------------------- helpers


def _seconds(value: float) -> float:
    return round(float(value), 6)


def _optional(signals: Any, name: str) -> float | None:
    return None if signals is None else round(float(getattr(signals, name)), 6)


def _checked_probability(value: Any) -> float:
    probability = float(value)
    if not math.isfinite(probability) or not -1e-6 <= probability <= 1.0 + 1e-6:
        raise ModelRuntimeError(f"PoseC3D returned an invalid probability: {value!r}")
    return min(max(probability, 0.0), 1.0)  # only float rounding noise is absorbed


def _to_source_coordinates(
    pose: PoseFrame, scale_x: float, scale_y: float, width: int, height: int
) -> PoseFrame:
    keypoints = np.asarray(pose.keypoints, dtype=np.float64)
    bbox = np.asarray(pose.bbox, dtype=np.float64).reshape(-1)[:4]
    if keypoints.shape != (17, 3) or bbox.shape != (4,) or not (
        np.isfinite(keypoints).all() and np.isfinite(bbox).all()
    ):
        raise ModelRuntimeError("Pose estimation returned a malformed or non-finite pose.")
    keypoints = keypoints.copy()
    keypoints[:, 0] *= scale_x
    keypoints[:, 1] *= scale_y
    bbox = bbox * np.array([scale_x, scale_y, scale_x, scale_y])
    return PoseFrame(
        timestamp_seconds=float(pose.timestamp_seconds),
        keypoints=keypoints.astype(np.float32),
        bbox=bbox.astype(np.float32),
        detected_people=pose.detected_people,
        frame_width=width,
        frame_height=height,
        inference_ms=pose.inference_ms,
    )


def _pose_record(pose: PoseFrame, track_id: int) -> dict[str, Any]:
    return {
        "track_id": track_id,
        "timestamp_seconds": _seconds(pose.timestamp_seconds),
        "bbox_xyxy": [round(float(v), OUTPUT_PRECISION) for v in pose.bbox],
        "keypoints": [
            [round(float(x), OUTPUT_PRECISION), round(float(y), OUTPUT_PRECISION),
             round(float(c), OUTPUT_PRECISION)]
            for x, y, c in pose.keypoints
        ],
    }


def _metrics(
    source: OpenCvFrameSource,
    resources: ResourceSampler,
    sampled: int,
    poses: int,
    predictions: int,
    track_resets: int,
    pose_ms_total: float,
    wall_seconds: float,
    config: EngineConfig,
) -> dict[str, float | int | None]:
    """Measured values only; anything not measured stays None (never zero)."""

    def mean(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 3) if values else None

    return {
        "source_fps": round(source.fps, 6),
        "frames_decoded": source.frames_decoded,
        "frames_reported_by_container": source.frame_count_reported,
        "undecodable_sampled_frames": source.undecodable_samples,
        "sample_fps_requested": config.sample_fps,
        "sampled_frames": sampled,
        "frames_with_person": poses,
        "frames_without_person": sampled - poses,
        "track_resets": track_resets,
        "posec3d_calls": predictions,
        "mean_pose_inference_ms": round(pose_ms_total / poses, 3) if poses else None,
        "engine_wall_seconds": round(wall_seconds, 3),
        "processed_frames_per_second": round(sampled / wall_seconds, 3) if wall_seconds > 0 else None,
        "process_cpu_percent_mean": mean(resources.cpu),
        "process_cpu_percent_max": round(max(resources.cpu), 3) if resources.cpu else None,
        "process_rss_mb_peak": round(max(resources.rss_mb), 3) if resources.rss_mb else None,
    }


# ----------------------------------------------------------------------------- loading


def load_engine(config: Mapping[str, Any] | EngineConfig) -> PoseC3DEngine:
    """Load and verify everything, then return a ready engine.

    Raises ModelUnavailableError (code ``model_unavailable``) when the weights,
    metadata, ONNX interface or pose model cannot be verified. Both models must
    exist locally; loading or inference never fetches weights from the network.
    """

    from icare.inference import engine_model

    settings = config if isinstance(config, EngineConfig) else EngineConfig.from_mapping(config)
    if settings.device != "cpu":
        raise ModelUnavailableError(
            f"Only the CPU provider is supported in this release, not {settings.device!r}."
        )
    metadata = engine_model.load_metadata(settings)
    classifier = engine_model.OnnxTemporalClassifier.load(settings.model_path, metadata)
    try:
        extractor = engine_model.load_pose_extractor(settings)
    except Exception:
        classifier.close()
        raise
    engine = PoseC3DEngine(
        settings,
        extractor,
        classifier,
        window_seconds=float(metadata["window_seconds"]),
        clip_len=int(metadata["clip_len"]),
        info={"architecture": metadata["architecture"], "classes": list(metadata["classes"])},
    )
    log.info("Engine ready: %s", engine.model_version)
    return engine
