from __future__ import annotations

import unittest

import numpy as np

from icare_app.inference import FallDetectionSession, ModelOutput


class FakeBackend:
    available = True
    name = "fake"

    def __init__(self, output: ModelOutput) -> None:
        self.output = output

    def reset(self) -> None:
        pass

    def process_frame(self, frame_rgb, timestamp_seconds):
        del frame_rgb, timestamp_seconds
        output, self.output = self.output, None
        return output


class InferenceLoggingTests(unittest.TestCase):
    def test_logs_latency_and_classifier_metadata(self) -> None:
        output = ModelOutput(
            timestamp_seconds=1.4,
            fall_probability=0.91,
            inference_ms=24.5,
            window_start_seconds=0.2,
            source_pose_count=12,
            urgency=0.82,
            reliability=0.88,
            process_cpu_percent=42.0,
            process_rss_mb=350.0,
        )
        session = FallDetectionSession(
            FakeBackend(output), ground_truth="fall", fall_onset_seconds=1.0
        )
        session._consume_output(output)
        session.mark_complete()
        snapshot = session.snapshot()
        self.assertEqual(snapshot["evaluation"]["posec3d_calls"], 1)
        self.assertAlmostEqual(
            snapshot["events"][0]["alert_latency_seconds"], 0.4
        )
        self.assertEqual(snapshot["inference_records"][0]["source_pose_count"], 12)
        self.assertFalse(snapshot["evaluation"]["missed_fall"])

    def test_counts_no_fall_detection_as_false_alarm(self) -> None:
        output = ModelOutput(2.0, 0.75)
        session = FallDetectionSession(FakeBackend(output), ground_truth="no_fall")
        session._consume_output(output)
        session.mark_complete()
        self.assertEqual(session.snapshot()["evaluation"]["false_alarm_count"], 1)


if __name__ == "__main__":
    unittest.main()
