"""Unit tests for Person 4 evaluation benchmark harness and robustness evaluation."""
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
    RobustnessEvaluator,
    apply_frame_cropping,
    apply_keypoint_dropout,
    apply_keypoint_noise,
)
from evaluation.run_benchmarks import load_annotations_from_manifest, run_benchmark_suite


class BenchmarkHarnessTests(unittest.TestCase):
    def test_calculate_percentile(self) -> None:
        data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        self.assertEqual(calculate_percentile(data, 50.0), 5.5)
        self.assertAlmostEqual(calculate_percentile(data, 95.0), 9.55, places=2)
        self.assertIsNone(calculate_percentile([], 50.0))
        self.assertEqual(calculate_percentile([4.2], 90.0), 4.2)

    def test_compute_metrics_classification(self) -> None:
        annotations = [
            ClipAnnotation(clip_id="c1", filename=Path("c1.mp4"), true_label="Fall", fall_onset_sec=2.0, duration_sec=10.0),
            ClipAnnotation(clip_id="c2", filename=Path("c2.mp4"), true_label="Fall", fall_onset_sec=1.5, duration_sec=10.0),
            ClipAnnotation(clip_id="c3", filename=Path("c3.mp4"), true_label="No Fall", fall_onset_sec=None, duration_sec=10.0),
            ClipAnnotation(clip_id="c4", filename=Path("c4.mp4"), true_label="No Fall", fall_onset_sec=None, duration_sec=10.0),
        ]

        records = [
            EvaluationRecord(
                clip_id="c1", true_label="Fall", predicted_label="Fall",
                max_fall_probability=0.9, fall_detected=True, first_alert_time_sec=2.5,
                alert_latency_sec=0.5, processing_time_sec=1.0, total_frames_processed=10,
                temporal_model_calls=5, fps=10.0, cpu_percent=12.0, ram_mb=100.0
            ),
            EvaluationRecord(
                clip_id="c2", true_label="Fall", predicted_label="No Fall",
                max_fall_probability=0.2, fall_detected=False, first_alert_time_sec=None,
                alert_latency_sec=None, processing_time_sec=1.0, total_frames_processed=10,
                temporal_model_calls=5, fps=10.0, cpu_percent=14.0, ram_mb=102.0
            ),
            EvaluationRecord(
                clip_id="c3", true_label="No Fall", predicted_label="Fall",
                max_fall_probability=0.8, fall_detected=True, first_alert_time_sec=3.0,
                alert_latency_sec=None, processing_time_sec=1.0, total_frames_processed=10,
                temporal_model_calls=5, fps=10.0, cpu_percent=10.0, ram_mb=98.0
            ),
            EvaluationRecord(
                clip_id="c4", true_label="No Fall", predicted_label="No Fall",
                max_fall_probability=0.1, fall_detected=False, first_alert_time_sec=None,
                alert_latency_sec=None, processing_time_sec=1.0, total_frames_processed=10,
                temporal_model_calls=5, fps=10.0, cpu_percent=11.0, ram_mb=99.0
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
        self.assertAlmostEqual(metrics.alert_latency_median_sec, 0.5)
        self.assertAlmostEqual(metrics.avg_fps, 10.0)
        self.assertEqual(metrics.cpu_percent_mean, 11.75)


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
        # 20% crop on 416x416 means border < 83.2 or > 332.8 is cropped
        cropped = apply_frame_cropping(keypoints, crop_ratio=0.2, img_width=416.0, img_height=416.0)
        self.assertEqual(cropped[0], [0.0, 0.0, 0.0])
        self.assertEqual(cropped[1], [200.0, 200.0, 0.9])


class BenchmarkRunnerTests(unittest.TestCase):
    def test_run_benchmark_suite(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            manifest = tmppath / "manifest.json"
            output = tmppath / "report.json"

            manifest_content = {
                "version": "1.0",
                "clips": [
                    {
                        "id": "test_fall",
                        "filename": "test_fall.mp4",
                        "label": "Fall",
                        "fall_onset_sec": 1.0,
                        "duration_sec": 4.0
                    }
                ]
            }
            manifest.write_text(json.dumps(manifest_content), encoding="utf-8")

            report = run_benchmark_suite(manifest, output)
            self.assertTrue(output.exists())
            self.assertEqual(report["total_clips_evaluated"], 1)
            self.assertEqual(report["baseline_metrics"]["tp"], 1)


if __name__ == "__main__":
    unittest.main()
