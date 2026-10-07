from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import icare_app.reports as reports


class ReportTests(unittest.TestCase):
    def test_writes_incident_json_and_inference_csv(self) -> None:
        directory = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(directory.cleanup)
        original_root = reports.REPORT_ROOT
        reports.REPORT_ROOT = Path(directory.name)
        self.addCleanup(setattr, reports, "REPORT_ROOT", original_root)
        snapshot = {
            "events": [
                {
                    "event_id": 1,
                    "detected_at_seconds": 2.0,
                    "confidence": 0.9,
                    "source": "test",
                    "created_at_utc": "2026-01-01T00:00:00+00:00",
                    "fall_onset_seconds": 1.5,
                    "alert_latency_seconds": 0.5,
                }
            ],
            "inference_records": [
                {
                    "timestamp_seconds": 2.0,
                    "fall_probability": 0.9,
                    "inference_ms": 20.0,
                    "window_start_seconds": 0.0,
                    "source_pose_count": 10,
                    "urgency": 0.8,
                    "reliability": 0.9,
                    "process_cpu_percent": 30.0,
                    "process_rss_mb": 250.0,
                }
            ],
        }
        json_path, event_csv_path = reports.write_report(snapshot, "evaluation")
        document = json.loads(Path(json_path).read_text(encoding="utf-8"))
        inference_path = Path(document["inference_log_csv"])
        self.assertTrue(Path(event_csv_path).exists())
        self.assertTrue(inference_path.exists())
        with inference_path.open(newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
        self.assertEqual(rows[0]["urgency"], "0.8")


if __name__ == "__main__":
    unittest.main()
