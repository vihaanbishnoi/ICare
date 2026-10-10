"""Engine v1 lifecycle tests (Person 1).

ScriptedExtractor and ScriptedClassifier are labelled TEST ADAPTERS. Their output
is derived from synthetic geometry and is not model output, accuracy evidence or a
benchmark. Video decoding is real OpenCV. Tests using the real PoseC3D ONNX file
run only where onnxruntime is installed and use synthetic poses, so their
probabilities say nothing about real-world detection quality.
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
import shutil
import tempfile
import threading
import unittest

import cv2
import numpy as np

from icare_app import engine as engine_module
from icare_app.engine import (
    AnalysisCancelled,
    EngineClosedError,
    EngineConfig,
    InsufficientCoverageError,
    InvalidVideoError,
    ModelRuntimeError,
    ModelUnavailableError,
    NoPersonError,
    PoseC3DEngine,
    load_engine,
)
from icare_app.pose import PoseFrame, RTMPoseExtractor
from icare_app.posec3d_bridge import pose_sequence_to_heatmaps


ROOT = Path(__file__).resolve().parents[1]
HAS_ONNXRUNTIME = importlib.util.find_spec("onnxruntime") is not None
DARK, BRIGHT = 40, 200  # frame brightness selects which scripted "clip style" is produced


def write_clip(path: Path, *, fps: float, seconds: float, size=(320, 240), value=DARK) -> Path:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, size)
    if not writer.isOpened():
        raise unittest.SkipTest("OpenCV cannot write MJPG video in this environment")
    frame = np.full((size[1], size[0], 3), value, dtype=np.uint8)
    for _ in range(round(fps * seconds)):
        writer.write(frame)
    writer.release()
    return path


class ScriptedExtractor:
    """TEST ADAPTER: synthetic stick figure, pose derived from time and frame brightness.

    Dark clips stand still; bright clips drop towards the floor from t = 3 s.
    """

    def __init__(self, visible=lambda t: True, fail_at: float | None = None, bad_pose=False) -> None:
        self.visible = visible
        self.fail_at = fail_at
        self.bad_pose = bad_pose
        self.sessions = 0
        self.shapes: list[tuple[int, ...]] = []
        self.lock = threading.Lock()

    def fork(self):
        with self.lock:
            self.sessions += 1
        return self

    def extract(self, frame_rgb, t):
        with self.lock:
            self.shapes.append(frame_rgb.shape)
        if self.fail_at is not None and t >= self.fail_at:
            raise RuntimeError("scripted pose failure")
        if not self.visible(t):
            return None
        h, w = frame_rgb.shape[:2]
        falling = frame_rgb.mean() > 100
        drop = min(max(t - 3.0, 0.0), 1.0) * 0.5 if falling else 0.0
        points = np.zeros((17, 3), np.float32)
        for k in range(17):
            points[k] = (w * (0.5 + 0.015 * (k - 8)), h * (0.15 + 0.05 * k + drop), 0.9)
        if self.bad_pose:
            points[3, 0] = np.nan
        bbox = np.array([w * 0.35, h * (0.1 + drop), w * 0.65, h * (0.95 + drop * 0.05)], np.float32)
        return PoseFrame(float(t), points, bbox, 1, w, h, 2.0)


class ScriptedClassifier:
    """TEST ADAPTER: deterministic function of the heatmap window, not a trained model."""

    model_version = "test-adapter-not-a-model"

    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls = 0
        self.closed = False
        self.shapes: list[tuple[int, ...]] = []

    def predict(self, tensor):
        self.calls += 1
        self.shapes.append((tensor.shape, str(tensor.dtype)))
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        ys = np.arange(64, dtype=np.float32)[None, None, :, None]

        def centroid(window):
            return float((window * ys).sum() / max(float(window.sum()), 1e-6))

        shift = centroid(tensor[0][:, 40:]) - centroid(tensor[0][:, :8])
        return float(1.0 / (1.0 + math.exp(-(shift - 2.0))))

    def close(self):
        self.closed = True


def collect(engine, path, **kwargs):
    poses, predictions, progress = [], [], []
    summary = engine.analyze_video(
        path,
        on_pose=poses.append,
        on_prediction=predictions.append,
        on_progress=progress.append,
        **kwargs,
    )
    return summary, poses, predictions, progress


def comparable(predictions):
    """Predictions without wall-clock inference time, for exact equality checks."""

    return [{k: v for k, v in p.items() if k != "inference_ms"} for p in predictions]


class EngineTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="icare-engine-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def make_engine(self, extractor=None, classifier=None, **config) -> PoseC3DEngine:
        settings = EngineConfig(model_path=self.tmp / "unused.onnx", **config)
        self.extractor = extractor or ScriptedExtractor()
        self.classifier = classifier or ScriptedClassifier()
        return PoseC3DEngine(settings, self.extractor, self.classifier)


class SamplingTests(EngineTestCase):
    def test_samples_by_video_timestamp_for_30_and_25_fps(self) -> None:
        for fps in (30, 25):
            with self.subTest(fps=fps):
                clip = write_clip(self.tmp / f"clip{fps}.avi", fps=fps, seconds=5)
                _, poses, _, _ = collect(self.make_engine(), clip)
                frames = round(fps * 5)
                expected = []
                for k in range(frames):
                    index = math.floor(k * fps / 6 + 0.5)
                    if index >= frames:
                        break
                    expected.append(index / fps)
                self.assertEqual([p["timestamp_seconds"] for p in poses], [round(t, 6) for t in expected])

    def test_every_frame_used_when_sample_rate_exceeds_source_rate(self) -> None:
        clip = write_clip(self.tmp / "slow.avi", fps=5, seconds=3)
        _, poses, _, _ = collect(self.make_engine(sample_fps=30), clip)
        self.assertEqual(len(poses), 15)

    def test_same_clip_gives_identical_samples_every_time(self) -> None:
        clip = write_clip(self.tmp / "clip.avi", fps=30, seconds=4)
        first = collect(self.make_engine(), clip)
        second = collect(self.make_engine(), clip)
        self.assertEqual(first[1], second[1])
        self.assertEqual(comparable(first[2]), comparable(second[2]))

    def test_summary_reports_source_dimensions_and_decoded_duration(self) -> None:
        clip = write_clip(self.tmp / "wide.avi", fps=25, seconds=4, size=(832, 468))
        extractor = ScriptedExtractor()
        summary, poses, _, _ = collect(self.make_engine(extractor), clip)
        self.assertEqual((summary["frame_width"], summary["frame_height"]), (832, 468))
        self.assertAlmostEqual(summary["duration_seconds"], 4.0, places=3)
        # The model saw a 416-wide frame, but emitted coordinates are source pixels.
        self.assertEqual(extractor.shapes[0][:2], (234, 416))
        self.assertAlmostEqual(poses[0]["keypoints"][8][0], 832 * 0.5, delta=0.01)
        self.assertAlmostEqual(poses[0]["bbox_xyxy"][2], 832 * 0.65, delta=0.01)
        self.assertAlmostEqual(poses[0]["bbox_xyxy"][3], 468 * 0.95, delta=0.01)


class CompletionTests(EngineTestCase):
    def test_final_window_is_classified_before_returning(self) -> None:
        clip = write_clip(self.tmp / "clip.avi", fps=30, seconds=5)
        engine = self.make_engine()
        _, poses, predictions, _ = collect(engine, clip)
        self.assertEqual(predictions[-1]["timestamp_seconds"], poses[-1]["timestamp_seconds"])
        # The interval rule alone would have skipped this one; the drain added it.
        spacing = predictions[-1]["timestamp_seconds"] - predictions[-2]["timestamp_seconds"]
        self.assertLess(spacing, engine.config.prediction_interval_seconds)

    def test_prediction_record_fields_and_window_limits(self) -> None:
        clip = write_clip(self.tmp / "clip.avi", fps=30, seconds=6)
        _, poses, predictions, _ = collect(self.make_engine(), clip)
        for record in predictions:
            self.assertEqual(
                set(record),
                {"timestamp_seconds", "fall_probability", "window_start_seconds",
                 "source_pose_count", "inference_ms", "urgency", "reliability"},
            )
            self.assertTrue(0.0 <= record["fall_probability"] <= 1.0)
            self.assertLessEqual(record["timestamp_seconds"] - record["window_start_seconds"], 4.0 + 1e-6)
            self.assertGreaterEqual(record["source_pose_count"], 6)
            self.assertIsNotNone(record["urgency"])
            self.assertIsNotNone(record["reliability"])
        self.assertTrue(all(len(p["keypoints"]) == 17 for p in poses))
        self.assertTrue(all(isinstance(p["timestamp_seconds"], float) for p in poses))
        json.dumps(poses + predictions)  # plain JSON types only
        shape, dtype = self.classifier.shapes[0]
        self.assertEqual((shape, dtype), ((1, 17, 48, 64, 64), "float32"))

    def test_progress_is_monotonic_and_stays_below_one(self) -> None:
        clip = write_clip(self.tmp / "clip.avi", fps=30, seconds=4)
        _, _, _, progress = collect(self.make_engine(), clip)
        self.assertEqual(progress[0], 0.0)
        self.assertEqual(progress, sorted(progress))
        self.assertLess(progress[-1], 1.0)

    def test_metrics_are_measured_or_none(self) -> None:
        clip = write_clip(self.tmp / "clip.avi", fps=30, seconds=4)
        summary, poses, predictions, _ = collect(self.make_engine(), clip)
        metrics = summary["metrics"]
        self.assertEqual(metrics["sampled_frames"], len(poses))
        self.assertEqual(metrics["posec3d_calls"], len(predictions))
        self.assertEqual(metrics["frames_decoded"], 120)
        self.assertTrue(
            all(v is None or isinstance(v, (int, float)) for v in metrics.values())
        )
        self.assertGreater(metrics["engine_wall_seconds"], 0)


class DistinctFailureTests(EngineTestCase):
    def test_no_person_is_distinct_and_emits_no_prediction(self) -> None:
        clip = write_clip(self.tmp / "clip.avi", fps=30, seconds=4)
        engine = self.make_engine(ScriptedExtractor(visible=lambda t: False))
        predictions: list = []
        with self.assertRaises(NoPersonError) as caught:
            engine.analyze_video(
                clip, on_pose=lambda r: None, on_prediction=predictions.append, on_progress=lambda v: None
            )
        self.assertEqual(caught.exception.code, "no_person")
        self.assertEqual(predictions, [])
        self.assertEqual(self.classifier.calls, 0)

    def test_short_clip_is_insufficient_coverage_not_zero_probability(self) -> None:
        clip = write_clip(self.tmp / "clip.avi", fps=30, seconds=1.5)
        with self.assertRaises(InsufficientCoverageError) as caught:
            collect(self.make_engine(), clip)
        self.assertEqual(caught.exception.code, "insufficient_temporal_coverage")
        self.assertEqual(self.classifier.calls, 0)

    def test_missing_and_corrupt_files_are_invalid_video(self) -> None:
        garbage = self.tmp / "garbage.mp4"
        garbage.write_bytes(b"this is not a video" * 100)
        for path in (self.tmp / "absent.mp4", garbage):
            with self.subTest(path=path.name):
                with self.assertRaises(InvalidVideoError) as caught:
                    collect(self.make_engine(), path)
                self.assertEqual(caught.exception.code, "invalid_video")

    def test_classifier_failure_is_model_error_without_fabricated_confidence(self) -> None:
        clip = write_clip(self.tmp / "clip.avi", fps=30, seconds=5)
        engine = self.make_engine(classifier=ScriptedClassifier(error=RuntimeError("boom")))
        predictions: list = []
        with self.assertRaises(ModelRuntimeError) as caught:
            engine.analyze_video(
                clip, on_pose=lambda r: None, on_prediction=predictions.append, on_progress=lambda v: None
            )
        self.assertEqual(caught.exception.code, "model_error")
        self.assertEqual(predictions, [])

    def test_invalid_probability_is_rejected_not_clipped(self) -> None:
        clip = write_clip(self.tmp / "clip.avi", fps=30, seconds=5)
        for value in (float("nan"), 1.5, -0.2):
            with self.subTest(value=value):
                engine = self.make_engine(classifier=ScriptedClassifier(result=value))
                with self.assertRaises(ModelRuntimeError):
                    collect(engine, clip)

    def test_pose_model_failures_are_model_errors(self) -> None:
        clip = write_clip(self.tmp / "clip.avi", fps=30, seconds=4)
        for extractor in (ScriptedExtractor(fail_at=1.0), ScriptedExtractor(bad_pose=True)):
            with self.subTest(extractor=vars(extractor).get("fail_at")):
                with self.assertRaises(ModelRuntimeError) as caught:
                    collect(self.make_engine(extractor), clip)
                self.assertEqual(caught.exception.code, "model_error")

    def test_error_codes_are_distinct(self) -> None:
        classes = [
            engine_module.ModelUnavailableError, engine_module.InvalidVideoError,
            engine_module.NoPersonError, engine_module.InsufficientCoverageError,
            engine_module.ModelRuntimeError, engine_module.AnalysisCancelled,
            engine_module.EngineClosedError,
        ]
        codes = [cls.code for cls in classes]
        self.assertEqual(len(set(codes)), len(codes))


class TrackGapTests(EngineTestCase):
    visible = staticmethod(lambda t: t < 3.0 or t >= 6.0)

    def test_window_never_spans_an_absence(self) -> None:
        clip = write_clip(self.tmp / "clip.avi", fps=30, seconds=7.5)
        summary, _, predictions, _ = collect(self.make_engine(ScriptedExtractor(self.visible)), clip)
        self.assertEqual(summary["metrics"]["track_resets"], 1)
        self.assertTrue(predictions)
        # After the person returns at 6 s only 1.5 s of track exists: no prediction.
        self.assertTrue(all(p["timestamp_seconds"] < 3.0 for p in predictions))

    def test_disabling_the_gap_rule_interpolates_across_the_absence(self) -> None:
        clip = write_clip(self.tmp / "clip.avi", fps=30, seconds=7.5)
        engine = self.make_engine(ScriptedExtractor(self.visible), max_pose_gap_seconds=None)
        _, _, predictions, _ = collect(engine, clip)
        self.assertTrue(any(p["window_start_seconds"] < 3.0 <= p["timestamp_seconds"] for p in predictions))


class CancellationTests(EngineTestCase):
    def test_cancel_event_stops_analysis_and_engine_stays_usable(self) -> None:
        clip = write_clip(self.tmp / "clip.avi", fps=30, seconds=6)
        engine = self.make_engine()
        cancel = threading.Event()
        poses: list = []

        def on_pose(record):
            poses.append(record)
            if len(poses) == 3:
                cancel.set()

        with self.assertRaises(AnalysisCancelled) as caught:
            engine.analyze_video(
                clip, on_pose=on_pose, on_prediction=lambda r: None,
                on_progress=lambda v: None, cancel_event=cancel,
            )
        self.assertEqual(caught.exception.code, "cancelled")
        self.assertEqual(len(poses), 3)
        _, _, predictions, _ = collect(engine, clip)  # lock released, no stale state
        self.assertTrue(predictions)

    def test_already_cancelled_job_does_not_start(self) -> None:
        clip = write_clip(self.tmp / "clip.avi", fps=30, seconds=3)
        cancel = threading.Event()
        cancel.set()
        extractor = ScriptedExtractor()
        with self.assertRaises(AnalysisCancelled):
            collect(self.make_engine(extractor), clip, cancel_event=cancel)
        self.assertEqual(extractor.sessions, 0)

    def test_callback_exception_propagates_and_releases_the_engine(self) -> None:
        clip = write_clip(self.tmp / "clip.avi", fps=30, seconds=4)
        engine = self.make_engine()

        class StopJob(Exception):
            pass

        def on_progress(value):
            if value and value > 0.2:
                raise StopJob

        with self.assertRaises(StopJob):
            engine.analyze_video(
                clip, on_pose=lambda r: None, on_prediction=lambda r: None, on_progress=on_progress
            )
        self.assertTrue(collect(engine, clip)[2])


class IndependenceTests(EngineTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.still = write_clip(self.tmp / "still.avi", fps=30, seconds=6, value=DARK)
        self.falling = write_clip(self.tmp / "falling.avi", fps=30, seconds=6, value=BRIGHT)

    def snapshot(self, engine, clip):
        _, poses, predictions, _ = collect(engine, clip)
        return poses, comparable(predictions)

    def test_clips_differ_so_the_isolation_checks_are_meaningful(self) -> None:
        engine = self.make_engine()
        self.assertNotEqual(self.snapshot(engine, self.still), self.snapshot(engine, self.falling))

    def test_interleaved_clips_match_their_standalone_results(self) -> None:
        alone_still = self.snapshot(self.make_engine(), self.still)
        alone_falling = self.snapshot(self.make_engine(), self.falling)
        engine = self.make_engine()
        order = [self.still, self.falling, self.falling, self.still]
        expected = [alone_still, alone_falling, alone_falling, alone_still]
        for clip, wanted in zip(order, expected):
            self.assertEqual(self.snapshot(engine, clip), wanted)

    def test_concurrent_callers_are_serialised_without_mixing(self) -> None:
        alone = {
            self.still: self.snapshot(self.make_engine(), self.still),
            self.falling: self.snapshot(self.make_engine(), self.falling),
        }
        engine = self.make_engine()
        results: dict[int, tuple] = {}
        clips = [self.still, self.falling] * 2

        def run(slot: int) -> None:
            results[slot] = self.snapshot(engine, clips[slot])

        threads = [threading.Thread(target=run, args=(slot,)) for slot in range(len(clips))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=120)
        self.assertEqual(len(results), len(clips))
        for slot, clip in enumerate(clips):
            self.assertEqual(results[slot], alone[clip])

    def test_each_clip_gets_a_fresh_pose_session(self) -> None:
        engine = self.make_engine()
        collect(engine, self.still)
        collect(engine, self.still)
        self.assertEqual(self.extractor.sessions, 2)


class LifecycleTests(EngineTestCase):
    def test_close_releases_models_and_rejects_new_work(self) -> None:
        clip = write_clip(self.tmp / "clip.avi", fps=30, seconds=4)
        engine = self.make_engine()
        self.assertTrue(engine.ready)
        engine.close()
        self.assertFalse(engine.ready)
        self.assertTrue(self.classifier.closed)
        with self.assertRaises(EngineClosedError) as caught:
            collect(engine, clip)
        self.assertEqual(caught.exception.code, "engine_closed")

    def test_describe_lists_settings_without_paths(self) -> None:
        info = self.make_engine().describe()
        self.assertEqual(info["sample_fps"], 6.0)
        self.assertEqual(info["clip_len"], 48)
        self.assertEqual(info["window_seconds"], 4.0)
        self.assertNotIn("model_path", info)


class ConfigAndLoadingTests(EngineTestCase):
    def test_defaults_follow_the_contract(self) -> None:
        config = EngineConfig.from_mapping({"model_path": "m.onnx", "device": "cpu"})
        self.assertEqual(config.sample_fps, 6.0)
        self.assertEqual(config.prediction_interval_seconds, 0.75)
        self.assertEqual(config.device, "cpu")

    def test_unknown_or_invalid_settings_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            EngineConfig.from_mapping({"model_path": "m.onnx", "sampel_fps": 3})
        with self.assertRaises(ValueError):
            EngineConfig.from_mapping({"device": "cpu"})
        with self.assertRaises(ValueError):
            EngineConfig(model_path=Path("m.onnx"), sample_fps=0)

    def test_non_cpu_device_is_not_ready(self) -> None:
        with self.assertRaises(ModelUnavailableError):
            load_engine({"model_path": ROOT / "models" / "posec3d_fall.onnx", "device": "cuda"})

    def test_missing_weights_report_model_unavailable(self) -> None:
        shutil.copy(ROOT / "models" / "posec3d_runtime.json", self.tmp / "posec3d_runtime.json")
        with self.assertRaises(ModelUnavailableError) as caught:
            load_engine({"model_path": self.tmp / "absent.onnx"})
        self.assertEqual(caught.exception.code, "model_unavailable")

    def test_missing_metadata_reports_model_unavailable(self) -> None:
        with self.assertRaises(ModelUnavailableError):
            load_engine({"model_path": self.tmp / "absent.onnx"})

    def test_swapped_class_order_in_metadata_is_refused(self) -> None:
        metadata = json.loads((ROOT / "models" / "posec3d_runtime.json").read_text(encoding="utf-8"))
        metadata["classes"] = ["Fall", "No Fall"]
        metadata["fall_class_index"] = 0
        (self.tmp / "posec3d_runtime.json").write_text(json.dumps(metadata), encoding="utf-8")
        with self.assertRaises(ModelUnavailableError) as caught:
            load_engine({"model_path": ROOT / "models" / "posec3d_fall.onnx",
                         "metadata_path": self.tmp / "posec3d_runtime.json"})
        self.assertIn("classes", str(caught.exception))

    def test_importing_the_engine_loads_no_inference_runtime(self) -> None:
        import subprocess
        import sys

        code = (
            "import sys, icare_app.engine, icare_app.engine_model;"
            "bad = [m for m in ('onnxruntime', 'rtmlib', 'psutil') if m in sys.modules];"
            "sys.exit(1 if bad else 0)"
        )
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode())


class ExtractorForkTests(unittest.TestCase):
    def test_fork_shares_models_but_not_tracking_state(self) -> None:
        # Built without loading rtmlib: only the state fork() must separate matters.
        base = object.__new__(RTMPoseExtractor)
        base.lock = threading.Lock()
        base.detector, base.pose_estimator = object(), object()
        base.detection_frequency = 1
        base.frame_index, base.primary_box, base.detected_people = 7, np.ones((1, 5)), 2
        clone = base.fork()
        self.assertEqual((clone.frame_index, clone.primary_box, clone.detected_people), (0, None, 0))
        self.assertEqual((base.frame_index, base.detected_people), (7, 2))
        self.assertIs(clone.detector, base.detector)
        self.assertIs(clone.lock, base.lock)


class PreprocessingTests(unittest.TestCase):
    def test_heatmaps_do_not_depend_on_where_or_how_large_the_person_is(self) -> None:
        # Justifies mapping poses back to source pixels: the bridge normalises scale.
        rng = np.random.default_rng(7)
        poses = np.concatenate(
            [rng.uniform(20, 100, (48, 17, 2)), rng.uniform(0.4, 1.0, (48, 17, 1))], axis=2
        ).astype(np.float32)
        moved = poses.copy()
        moved[..., :2] = moved[..., :2] * 3.5 + np.array([400.0, 90.0], np.float32)
        first, second = pose_sequence_to_heatmaps(poses), pose_sequence_to_heatmaps(moved)
        self.assertEqual(first.shape, (17, 48, 64, 64))
        np.testing.assert_allclose(first, second, atol=1e-3)

    def test_low_confidence_joints_leave_no_heatmap(self) -> None:
        poses = np.full((48, 17, 3), 0.9, dtype=np.float32)
        poses[..., 0] = np.linspace(10, 50, 17)
        poses[..., 1] = np.linspace(10, 90, 17)
        poses[:, 5, 2] = 0.0
        self.assertEqual(float(pose_sequence_to_heatmaps(poses)[5].max()), 0.0)


@unittest.skipUnless(HAS_ONNXRUNTIME, "onnxruntime is not installed")
class RealOnnxModelTests(EngineTestCase):
    """Real PoseC3D weights. Poses stay synthetic, so values are not evidence."""

    def load_classifier(self):
        from icare_app.engine_model import OnnxTemporalClassifier, load_metadata

        config = EngineConfig(model_path=ROOT / "models" / "posec3d_fall.onnx")
        return OnnxTemporalClassifier.load(config.model_path, load_metadata(config))

    def test_loads_verifies_and_versions_the_deployed_weights(self) -> None:
        classifier = self.load_classifier()
        self.assertRegex(classifier.model_version, r"^posec3d_fall\.onnx@[0-9a-f]{12}$")
        probability = classifier.predict(np.zeros((1, 17, 48, 64, 64), np.float32))
        self.assertTrue(0.0 < probability < 1.0)

    def test_wrong_input_shape_is_a_model_error(self) -> None:
        with self.assertRaises(ModelRuntimeError):
            self.load_classifier().predict(np.zeros((1, 17, 24, 64, 64), np.float32))

    def test_corrupt_weights_report_model_unavailable(self) -> None:
        bad = self.tmp / "posec3d_fall.onnx"
        bad.write_bytes(b"not an onnx file")
        shutil.copy(ROOT / "models" / "posec3d_runtime.json", self.tmp / "posec3d_runtime.json")
        with self.assertRaises(ModelUnavailableError):
            load_engine({"model_path": bad})

    def test_real_classifier_runs_a_whole_clip_through_the_engine(self) -> None:
        clip = write_clip(self.tmp / "clip.avi", fps=30, seconds=5, value=BRIGHT)
        engine = PoseC3DEngine(
            EngineConfig(model_path=ROOT / "models" / "posec3d_fall.onnx"),
            ScriptedExtractor(),
            self.load_classifier(),
        )
        summary, poses, predictions, _ = collect(engine, clip)
        self.assertTrue(predictions)
        self.assertEqual(predictions[-1]["timestamp_seconds"], poses[-1]["timestamp_seconds"])
        self.assertTrue(all(0.0 <= p["fall_probability"] <= 1.0 for p in predictions))
        self.assertGreater(summary["metrics"]["mean_pose_inference_ms"], 0)


@unittest.skipUnless(importlib.util.find_spec("fastapi"), "fastapi is not installed")
class ApiIntegrationTests(EngineTestCase):
    """The engine behind Person 2's job runner: schema validation, results, errors."""

    def mp4(self, name: str, seconds: float, value: int) -> bytes:
        from api.video import InvalidVideo, mp4_duration_seconds

        path = self.tmp / name
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (320, 240))
        if not writer.isOpened():
            raise unittest.SkipTest("OpenCV cannot write MP4 video in this environment")
        for _ in range(round(30 * seconds)):
            writer.write(np.full((240, 320, 3), value, dtype=np.uint8))
        writer.release()
        try:
            mp4_duration_seconds(path)
        except InvalidVideo:
            raise unittest.SkipTest("OpenCV wrote an MP4 the API validator rejects")
        return path.read_bytes()

    def run_job(self, engine, data: bytes) -> tuple[dict, dict | None]:
        import time

        from fastapi.testclient import TestClient

        from api.config import Settings
        from api.main import create_app

        settings = Settings(
            data_dir=self.tmp / "data", examples_manifest=self.tmp / "none.json",
            job_timeout_seconds=120,
        )
        with TestClient(create_app(settings, engine=engine)) as client:
            self.assertEqual(client.get("/api/v1/ready").status_code, 200)
            created = client.post(
                "/api/v1/jobs/upload", files={"file": ("clip.mp4", data, "video/mp4")}
            )
            self.assertEqual(created.status_code, 202, created.text)
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                job = client.get(f"/api/v1/jobs/{created.json()['job_id']}").json()
                if job["state"] in ("completed", "failed", "cancelled"):
                    result = client.get(job["result_url"]).json() if job["result_url"] else None
                    return job, result
                time.sleep(0.05)
        self.fail("job did not finish")

    def test_completed_job_carries_engine_records_through_the_api(self) -> None:
        engine = self.make_engine()
        job, result = self.run_job(engine, self.mp4("fall.mp4", 6, BRIGHT))
        self.assertEqual(job["state"], "completed", job)
        self.assertEqual(job["model_version"], "test-adapter-not-a-model")
        self.assertEqual((result["frame_width"], result["frame_height"]), (320, 240))
        self.assertTrue(result["predictions"] and result["poses"])
        self.assertEqual(
            result["predictions"][-1]["timestamp_seconds"], result["poses"][-1]["timestamp_seconds"]
        )
        self.assertEqual(result["metrics"]["posec3d_calls"], len(result["predictions"]))
        self.assertIn("track_resets", result["metrics"])

    def test_engine_error_codes_reach_the_job(self) -> None:
        engine = self.make_engine(ScriptedExtractor(visible=lambda t: False))
        job, result = self.run_job(engine, self.mp4("empty.mp4", 4, DARK))
        self.assertEqual((job["state"], job["error"]["code"]), ("failed", "no_person"))
        self.assertIsNone(result)

    def test_model_failure_fails_the_job_with_no_results(self) -> None:
        engine = self.make_engine(classifier=ScriptedClassifier(error=RuntimeError("boom")))
        job, result = self.run_job(engine, self.mp4("clip.mp4", 5, DARK))
        self.assertEqual((job["state"], job["error"]["code"]), ("failed", "model_error"))
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
