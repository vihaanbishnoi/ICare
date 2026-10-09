"""Unit tests for Person 4 evaluation benchmark harness, IncidentTracker integration, and robustness protocols."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from evaluation.benchmark_harness import (
    BenchmarkConfig,
    BenchmarkHarness,
    ClipAnnotation,
    EvaluationRecord,
    MetricResults,
    calculate_percentile,
)
from evaluation.robustness_eval import (
    HARD_NEGATIVE_ACTIVITIES,
    RobustnessEvaluator,
    apply_frame_cropping,
    apply_keypoint_dropout,
    apply_keypoint_noise,
)
from evaluation.run_benchmarks import load_annotations_from_catalog, run_benchmark_suite


class TestFixtureEngineAdapter:
    """TEST ADAPTER for unit tests only.

    Scripted test outputs for unit test execution. Does not claim inference evidence.
    """

    def __init__(self, probabilities: list[float] | None = None) -> None:
        self.probabilities = probabilities if probabilities is not None else [0.1, 0.6, 0.7, 0.2, 0.2, 0.2]

    def analyze_video(self, video_path, *, on_pose, on_prediction, on_progress, cancel_event):
        for idx, prob in enumerate(self.probabilities):
            t = 1.0 + 0.75 * idx
            on_pose({
                "timestamp_seconds": t,
                "bbox_xyxy": [10.0, 10.0, 100.0, 100.0],
                "keypoints": [[20.0, 20.0, 0.9] for _ in range(17)],
            })
            on_prediction({
                "timestamp_seconds": t,
                "fall_probability": prob,
                "window_start_seconds": max(0.0, t - 4.0),
                "source_pose_count": 24,
                "inference_ms": 25.0,
                "urgency": 0.8 if prob >= 0.5 else 0.1,
                "reliability": 0.9,
            })
        on_progress(1.0)
        return {
            "duration_seconds": 6.0,
            "frame_width": 416,
            "frame_height": 416,
            "metrics": {
                "source_fps": 30.0,
                "sampled_frames": 36,
                "processed_frames_per_second": 12.0,
                "process_cpu_percent_mean": 15.0,
                "process_rss_mb_peak": 120.0,
                "mean_pose_inference_ms": 25.0,
            },
        }


class BenchmarkHarnessTests(unittest.TestCase):
    def test_calculate_percentile(self) -> None:
        data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        self.assertEqual(calculate_percentile(data, 50.0), 5.5)
        self.assertAlmostEqual(calculate_percentile(data, 95.0), 9.55, places=2)
        self.assertIsNone(calculate_percentile([], 50.0))
        self.assertEqual(calculate_percentile([4.2], 90.0), 4.2)

    def test_compute_metrics_classification(self) -> None:
        annotations = [
            ClipAnnotation(clip_id="c1", filename=Path("c1.mp4"), true_label="Fall", fall_onset_seconds=2.0, duration_seconds=10.0),
            ClipAnnotation(clip_id="c2", filename=Path("c2.mp4"), true_label="Fall", fall_onset_seconds=1.5, duration_seconds=10.0),
            ClipAnnotation(clip_id="c3", filename=Path("c3.mp4"), true_label="No Fall", fall_onset_seconds=None, duration_seconds=10.0),
            ClipAnnotation(clip_id="c4", filename=Path("c4.mp4"), true_label="No Fall", fall_onset_seconds=None, duration_seconds=10.0),
        ]

        records = [
            EvaluationRecord(
                clip_id="c1", true_label="Fall", predicted_label="Fall",
                max_fall_probability=0.9, incidents_detected=1, first_incident_timestamp_seconds=2.5,
                alert_latency_seconds=0.5, processing_time_seconds=1.0, total_frames_processed=10,
                temporal_model_calls=5, fps=10.0, mean_pose_inference_ms=25.0, cpu_percent_mean=12.0, ram_mb_peak=100.0
            ),
            EvaluationRecord(
                clip_id="c2", true_label="Fall", predicted_label="No Fall",
                max_fall_probability=0.2, incidents_detected=0, first_incident_timestamp_seconds=None,
                alert_latency_seconds=None, processing_time_seconds=1.0, total_frames_processed=10,
                temporal_model_calls=5, fps=10.0, mean_pose_inference_ms=25.0, cpu_percent_mean=14.0, ram_mb_peak=102.0
            ),
            EvaluationRecord(
                clip_id="c3", true_label="No Fall", predicted_label="Fall",
                max_fall_probability=0.8, incidents_detected=1, first_incident_timestamp_seconds=3.0,
                alert_latency_seconds=None, processing_time_seconds=1.0, total_frames_processed=10,
                temporal_model_calls=5, fps=10.0, mean_pose_inference_ms=25.0, cpu_percent_mean=10.0, ram_mb_peak=98.0
            ),
            EvaluationRecord(
                clip_id="c4", true_label="No Fall", predicted_label="No Fall",
                max_fall_probability=0.1, incidents_detected=0, first_incident_timestamp_seconds=None,
                alert_latency_seconds=None, processing_time_seconds=1.0, total_frames_processed=10,
                temporal_model_calls=5, fps=10.0, mean_pose_inference_ms=25.0, cpu_percent_mean=11.0, ram_mb_peak=99.0
            ),
        ]

        metrics = BenchmarkHarness.compute_metrics(records, annotations)
        self.assertEqual(metrics.tp, 1)
        self.assertEqual(metrics.fn, 1)
        self.assertEqual(metrics.fp, 1)
        self.assertEqual(metrics.tn, 1)
        self.assertAlmostEqual(metrics.precision, 0.5)
        self.assertAlmostEqual(metrics.recall, 0.5)
        self.assertAlmostEqual(metrics.f1_score, 0.5)
        self.assertAlmostEqual(metrics.balanced_accuracy, 0.5)
        self.assertAlmostEqual(metrics.overall_accuracy, 0.5)
        self.assertAlmostEqual(metrics.alert_latency_median_seconds, 0.5)
        self.assertAlmostEqual(metrics.avg_fps, 10.0)
        self.assertEqual(metrics.cpu_percent_mean, 11.75)

    def test_unmeasured_fields_stay_none(self) -> None:
        annotations = [
            ClipAnnotation(clip_id="c1", filename=Path("c1.mp4"), true_label="No Fall", duration_seconds=None)
        ]
        records = [
            EvaluationRecord(
                clip_id="c1", true_label="No Fall", predicted_label="No Fall",
                max_fall_probability=0.1, incidents_detected=0, first_incident_timestamp_seconds=None,
                alert_latency_seconds=None, processing_time_seconds=1.0, total_frames_processed=10,
                temporal_model_calls=5, fps=None, mean_pose_inference_ms=None, cpu_percent_mean=None, ram_mb_peak=None
            )
        ]
        metrics = BenchmarkHarness.compute_metrics(records, annotations)
        self.assertIsNone(metrics.cpu_percent_mean)
        self.assertIsNone(metrics.ram_mb_peak_mean)
        self.assertIsNone(metrics.total_observed_hours)
        self.assertIsNone(metrics.false_alarms_per_hour)

    def test_run_engine_clip_with_adapter(self) -> None:
        harness = BenchmarkHarness()
        adapter = TestFixtureEngineAdapter(probabilities=[0.1, 0.6, 0.7, 0.2, 0.2, 0.2])
        annot = ClipAnnotation(clip_id="fall_test", filename=Path("test.mp4"), true_label="Fall", fall_onset_seconds=1.0)
        rec = harness.run_engine_clip(adapter, annot)
        self.assertEqual(rec.incidents_detected, 1)
        self.assertEqual(rec.predicted_label.lower(), "fall")
        self.assertAlmostEqual(rec.alert_latency_seconds, 0.75)  # first incident at t=1.75, onset=1.0


class RobustnessEvaluationTests(unittest.TestCase):
    def test_keypoint_dropout(self) -> None:
        keypoints = [[10.0, 20.0, 0.9], [30.0, 40.0, 0.8]]
        dropped = apply_keypoint_dropout(keypoints, dropout_prob=1.0, seed=42)
        self.assertEqual(dropped, [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])

        kept = apply_keypoint_dropout(keypoints, dropout_prob=0.0)
        self.assertEqual(kept, keypoints)

    def test_keypoint_noise(self) -> None:
        keypoints = [[10.0, 20.0, 0.9], [30.0, 40.0, 0.8]]
        noisy = apply_keypoint_noise(keypoints, noise_std=1.0, seed=42)
        self.assertNotEqual(noisy[0][:2], keypoints[0][:2])

    def test_frame_cropping(self) -> None:
        keypoints = [[10.0, 10.0, 0.9], [200.0, 200.0, 0.9]]
        cropped = apply_frame_cropping(keypoints, crop_ratio=0.2, img_width=416.0, img_height=416.0)
        self.assertEqual(cropped[0], [0.0, 0.0, 0.0])
        self.assertEqual(cropped[1], [200.0, 200.0, 0.9])

    def test_hard_negative_activities_defined(self) -> None:
        self.assertTrue(len(HARD_NEGATIVE_ACTIVITIES) >= 5)
        for act in HARD_NEGATIVE_ACTIVITIES:
            self.assertEqual(act["expected_outcome"], "No Fall")


class BenchmarkRunnerTests(unittest.TestCase):
    def test_run_benchmark_suite_pending_media(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            catalog = tmppath / "catalog.json"
            output = tmppath / "report.json"

            catalog_content = {
                "version": "1.0",
                "status": "pending_approved_media",
                "examples": [
                    {
                        "example_id": "test_pending",
                        "file": "non_existent.mp4",
                        "expected_outcome": "Fall",
                        "provenance_status": "pending"
                    }
                ]
            }
            catalog.write_text(json.dumps(catalog_content), encoding="utf-8")

            report = run_benchmark_suite(catalog, output)
            self.assertTrue(output.exists())
            self.assertEqual(report["evaluated_clips"], 0)
            self.assertIsNone(report["baseline_metrics"])
            self.assertEqual(report["media_provenance_status"], "pending_approved_media")


if __name__ == "__main__":
    unittest.main()
