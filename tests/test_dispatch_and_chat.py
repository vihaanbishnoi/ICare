"""Tests for 10 PM daily schedule, SQLite persistence, mock email dispatch, and grounded chatbot."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from icare.api.chatbot import ask_facility_chatbot, is_unrelated_query, SHORT_CIRCUIT_RESPONSE
from icare.api.config import Settings
from icare.api.dispatch import (
    DEFAULT_CARETAKERS,
    format_caretaker_email_body,
    get_schedule_status,
    run_daily_10pm_routine,
    send_mock_emails_to_caretakers,
)
from icare.api.main import create_app
from icare.api.store import Store


class DispatchAndStoreUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.store = Store(self.tmp / "test.sqlite3")

    def tearDown(self) -> None:
        self.store.close()

    def test_save_and_retrieve_daily_summary(self) -> None:
        summary_id = "sum_test_01"
        self.store.save_daily_summary(
            summary_id=summary_id,
            date_str="2026-10-24",
            model="llama3.2:1b",
            status="success",
            executive_summary="All units monitored safely.",
            structured_json=json.dumps({"incident_stats": {"total_events": 5, "confirmed_falls": 1}}),
            raw_markdown="# Report",
            log_count=5,
            sent_email_count=5,
        )
        retrieved = self.store.get_daily_summary(summary_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["summary_id"], summary_id)
        self.assertEqual(retrieved["date_str"], "2026-10-24")
        self.assertEqual(retrieved["sent_email_count"], 5)

        latest = self.store.get_latest_daily_summary()
        self.assertEqual(latest["summary_id"], summary_id)

    def test_save_and_list_caretaker_emails(self) -> None:
        email_id = self.store.save_caretaker_email(
            email_id="em_001",
            summary_id="sum_test_01",
            recipient_name="Nurse Elena",
            recipient_email="elena@facility.org",
            recipient_role="Head Nurse",
            subject="Daily Summary",
            body_text="Summary text",
            status="delivered",
        )
        self.assertEqual(email_id, "em_001")
        emails = self.store.list_caretaker_emails()
        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0]["recipient_name"], "Nurse Elena")
        self.assertEqual(emails[0]["status"], "delivered")

    def test_format_caretaker_email_body(self) -> None:
        c = DEFAULT_CARETAKERS[0]
        structured = {
            "executive_summary": "1 fall reported.",
            "incident_stats": {"total_events": 10, "confirmed_falls": 1, "near_falls": 1, "avg_response_time_seconds": 35},
            "high_risk_residents": [{"resident_name": "Eugene Patel", "room": "204", "wing": "West", "risk_level": "High", "incident_summary": "Fall", "action_plan": "Bed pad"}],
            "shift_handoff_recommendations": ["Check room 204"],
            "shift_handoff_notes": "Pay attention to 204.",
        }
        subject, body = format_caretaker_email_body(c, "2026-10-24", structured, "")
        self.assertIn("[ICare Daily Report]", subject)
        self.assertIn("1 falls", subject)
        self.assertIn(c["name"], body)
        self.assertIn("Eugene Patel", body)
        self.assertIn("10:00 PM", body)

    def test_send_mock_emails_to_caretakers(self) -> None:
        structured = {
            "executive_summary": "Summary",
            "incident_stats": {"total_events": 2, "confirmed_falls": 0, "near_falls": 0, "avg_response_time_seconds": 20},
        }
        sent = send_mock_emails_to_caretakers(
            store=self.store,
            summary_id="sum_test_02",
            date_str="2026-10-24",
            structured_summary=structured,
            raw_markdown="Markdown",
        )
        self.assertEqual(len(sent), len(DEFAULT_CARETAKERS))
        db_emails = self.store.list_caretaker_emails("sum_test_02")
        self.assertEqual(len(db_emails), len(DEFAULT_CARETAKERS))


class ChatbotUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.store = Store(self.tmp / "test.sqlite3")

    def tearDown(self) -> None:
        self.store.close()

    def test_is_unrelated_query_detects_off_topic(self) -> None:
        self.assertTrue(is_unrelated_query("What is the capital of France?", ""))
        self.assertTrue(is_unrelated_query("Who is Messi?", ""))
        self.assertTrue(is_unrelated_query("What is the weather in Tokyo?", ""))
        self.assertFalse(is_unrelated_query("Who had a fall today?", ""))
        self.assertFalse(is_unrelated_query("What is the status of room 204?", ""))

    @patch("urllib.request.urlopen")
    def test_ask_chatbot_grounded_answer(self, mock_urlopen) -> None:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "response": "Eugene Patel in Room 204 had 2 falls today."
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = ask_facility_chatbot(self.store, "Who had a fall in room 204?")
        self.assertEqual(res["reply"], "Eugene Patel in Room 204 had 2 falls today.")
        self.assertTrue(res["grounded"])

    @patch("urllib.request.urlopen")
    def test_ask_chatbot_short_circuits_unrelated(self, mock_urlopen) -> None:
        # Off-topic should short-circuit immediately without calling LLM
        res = ask_facility_chatbot(self.store, "What is the capital of France?")
        self.assertEqual(res["reply"], SHORT_CIRCUIT_RESPONSE)
        mock_urlopen.assert_not_called()

    @patch("urllib.request.urlopen")
    def test_ask_chatbot_normalizes_model_uncertainty(self, mock_urlopen) -> None:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "response": "I am not sure based on the provided records."
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = ask_facility_chatbot(self.store, "What color was the resident's shoes?")
        self.assertEqual(res["reply"], SHORT_CIRCUIT_RESPONSE)


class DispatchAndChatApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.settings = Settings(data_dir=self.tmp / "data")
        self.app = create_app(self.settings, engine=None)
        self._client_ctx = TestClient(self.app)
        self.client = self._client_ctx.__enter__()

    def tearDown(self) -> None:
        self._client_ctx.__exit__(None, None, None)


    def test_api_schedule_status(self) -> None:
        resp = self.client.get("/api/v1/reports/schedule-status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("scheduled_time", data)
        self.assertEqual(data["target_hour"], 22)
        self.assertTrue(data["is_active"])
        self.assertIn("caretakers", data)

    @patch("icare.api.dispatch.summarize_daily_logs")
    def test_api_trigger_10pm_dispatch(self, mock_summarize) -> None:
        mock_summarize.return_value = {
            "status": "success",
            "model": "llama3.2:1b",
            "summary": "Report",
            "structured_summary": {
                "executive_summary": "Daily check finished.",
                "incident_stats": {"total_events": 1, "confirmed_falls": 0, "near_falls": 0, "avg_response_time_seconds": 15},
                "high_risk_residents": [],
                "key_observations": [],
                "shift_handoff_recommendations": [],
                "shift_handoff_notes": "None"
            },
            "log_count": 1,
            "generated_at_utc": "2026-10-24T22:00:00Z",
            "ollama_connected": True,
        }
        resp = self.client.post("/api/v1/reports/trigger-10pm-dispatch")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertGreaterEqual(data["emails_dispatched"], 1)

        # Check emails endpoint returns the newly sent emails
        emails_resp = self.client.get("/api/v1/reports/caretaker-emails")
        self.assertEqual(emails_resp.status_code, 200)
        emails_data = emails_resp.json()
        self.assertGreaterEqual(emails_data["total_emails"], 1)

    def test_api_chat_short_circuit(self) -> None:
        resp = self.client.post("/api/v1/chat", json={
            "message": "What is the capital of France?",
            "history": []
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["reply"], SHORT_CIRCUIT_RESPONSE)


if __name__ == "__main__":
    unittest.main()
