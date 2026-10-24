"""Tests for daily logs loading and summary report generation with Ollama llama3.2:1b."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from icare.api.config import Settings
from icare.api.main import create_app
from icare.api.summary import (
    build_summary_prompt,
    format_logs_for_prompt,
    load_daily_logs,
    rule_based_fallback_summary,
    summarize_daily_logs,
)


class DailySummaryUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.csv_file = self.tmp / "test_logs.csv"
        self.csv_file.write_text(
            "log_id,timestamp,resident_id,resident_name,room,wing,event_type,confidence,status,response_time_seconds,attended_by,staff_notes\n"
            "LOG-1,2026-10-24 02:00:00,r1,Margaret Shah,101,East,Fall Detected,0.95,Attended,40,Nurse Elena,Assisted back to bed.\n"
            "LOG-2,2026-10-24 08:30:00,r2,Harold Brooks,102,East,Routine Check,0.50,Resolved,20,Caregiver Marcus,Normal check.\n",
            encoding="utf-8"
        )

    def test_load_daily_logs_reads_csv_records(self) -> None:
        logs = load_daily_logs(self.csv_file)
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0]["log_id"], "LOG-1")
        self.assertEqual(logs[0]["resident_name"], "Margaret Shah")
        self.assertEqual(logs[0]["confidence"], 0.95)
        self.assertEqual(logs[0]["response_time_seconds"], 40)
        self.assertEqual(logs[1]["event_type"], "Routine Check")

    def test_format_logs_for_prompt_creates_markdown_table(self) -> None:
        logs = load_daily_logs(self.csv_file)
        table = format_logs_for_prompt(logs)
        self.assertIn("Margaret Shah", table)
        self.assertIn("Fall Detected", table)
        self.assertIn("95%", table)

    def test_build_summary_prompt_contains_sections(self) -> None:
        logs = load_daily_logs(self.csv_file)
        prompt = build_summary_prompt(logs)
        self.assertIn("Executive Summary", prompt)
        self.assertIn("Clinical & Incident Analysis", prompt)
        self.assertIn("Shift Handoff Recommendations", prompt)

    def test_rule_based_fallback_summary(self) -> None:
        logs = load_daily_logs(self.csv_file)
        fallback = rule_based_fallback_summary(logs)
        self.assertIn("Total Monitoring Events", fallback)
        self.assertIn("Confirmed Falls", fallback)
        self.assertIn("Margaret Shah", fallback)

    @patch("urllib.request.urlopen")
    def test_summarize_daily_logs_success_with_mock_ollama(self, mock_urlopen) -> None:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "response": "### Daily Fall Monitoring Summary Report\nAll clear."
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        logs = load_daily_logs(self.csv_file)
        res = summarize_daily_logs(logs, model="llama3.2:1b")
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["ollama_connected"])
        self.assertIn("All clear", res["summary"])
        self.assertEqual(res["model"], "llama3.2:1b")

    def test_summarize_daily_logs_fallback_when_ollama_unreachable(self) -> None:
        logs = load_daily_logs(self.csv_file)
        # Using a dummy unreachable port to verify graceful fallback
        res = summarize_daily_logs(logs, ollama_host="http://127.0.0.1:59999", timeout_seconds=1.0)
        self.assertEqual(res["status"], "fallback")
        self.assertFalse(res["ollama_connected"])
        self.assertIn("Executive Summary", res["summary"])


class DailySummaryApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.settings = Settings(data_dir=self.tmp / "data")
        self.app = create_app(self.settings, engine=None)
        self.client = TestClient(self.app)

    def test_api_get_daily_logs(self) -> None:
        resp = self.client.get("/api/v1/reports/daily-logs")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total_logs", data)
        self.assertIn("logs", data)
        self.assertGreaterEqual(data["total_logs"], 1)

    @patch("icare.api.summary.urllib.request.urlopen")
    def test_api_get_daily_summary(self, mock_urlopen) -> None:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "response": "Executive Summary: 4 falls recorded today."
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        resp = self.client.get("/api/v1/reports/summarize")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["model"], "llama3.2:1b")
        self.assertIn("Executive Summary", data["summary"])


if __name__ == "__main__":
    unittest.main()
