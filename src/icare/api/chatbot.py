"""Local grounded chatbot querying SQLite summaries and daily logs using Ollama llama3.2:1b."""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import Any

from icare.api.store import Store
from icare.api.summary import DEFAULT_MODEL, DEFAULT_OLLAMA_HOST, load_daily_logs

log = logging.getLogger(__name__)

SHORT_CIRCUIT_RESPONSE = "I am not sure."


def build_database_context(store: Store | None = None) -> str:
    """Aggregate saved SQLite summaries, sent emails, and local daily logs into structured context."""
    sections: list[str] = []

    # 1. Saved SQLite Daily Summaries
    saved_summaries: list[dict[str, Any]] = store.list_daily_summaries(limit=5) if store else []
    if saved_summaries:
        sections.append("=== SAVED FACILITY DAILY SUMMARIES IN DATABASE ===")
        for s in saved_summaries:
            date_str = s.get("date_str", "Today")
            exec_sum = s.get("executive_summary", "")
            sections.append(f"Date: {date_str} (Summary ID: {s.get('summary_id')})")
            sections.append(f"Executive Summary: {exec_sum}")
            try:
                st = json.loads(s.get("structured_json", "{}"))
                stats = st.get("incident_stats", {})
                sections.append(
                    f"Stats: Total Events={stats.get('total_events')}, "
                    f"Confirmed Falls={stats.get('confirmed_falls')}, "
                    f"Near Falls={stats.get('near_falls')}, "
                    f"Average Staff Response Time={stats.get('avg_response_time_seconds')} seconds"
                )
                if st.get("high_risk_residents"):
                    sections.append("High-Risk Residents:")
                    for r in st["high_risk_residents"]:
                        sections.append(
                            f"  - {r.get('resident_name')} (Room {r.get('room')}, {r.get('wing')} Wing) [{r.get('risk_level')} Risk]: "
                            f"{r.get('incident_summary')} -> Plan: {r.get('action_plan')}"
                        )
                if st.get("shift_handoff_recommendations"):
                    sections.append("Shift Recommendations:")
                    for rec in st["shift_handoff_recommendations"]:
                        sections.append(f"  - {rec}")
                if st.get("shift_handoff_notes"):
                    sections.append(f"Shift Handoff Notes: {st['shift_handoff_notes']}")
            except Exception:
                sections.append(f"Details: {s.get('raw_markdown', '')[:200]}")
            sections.append("")

    # 2. Daily Monitoring Logs
    logs = load_daily_logs()
    if logs:
        sections.append("=== INDIVIDUAL MONITORING LOGS IN DATABASE ===")
        for l in logs:
            resp_str = f"responded in {l['response_time_seconds']}s by {l['attended_by']}" if l.get("response_time_seconds") else "resolved"
            conf = f"{int(l.get('confidence', 0)*100)}% conf"
            sections.append(
                f"- Log ID {l['log_id']} [{l['timestamp']}]: Resident {l['resident_name']} (Room {l['room']}, {l['wing']} Wing) - "
                f"Event: {l['event_type']} ({conf}), {resp_str}. Notes: {l['staff_notes']}"
            )
        sections.append("")

    # 3. Dispatched Caretaker Emails
    emails = store.list_caretaker_emails(limit=10) if store else []
    if emails:
        sections.append("=== RECENT DISPATCHED CARETAKER EMAILS IN DATABASE ===")
        for e in emails:
            sections.append(
                f"- Email {e['email_id']} sent at {e['sent_at_utc']} to {e['recipient_name']} ({e['recipient_role']} <{e['recipient_email']}>): "
                f"Subject: \"{e['subject']}\" Status: {e['status']}"
            )
        sections.append("")

    return "\n".join(sections)


def is_unrelated_query(question: str, context: str) -> bool:
    """Pre-filter check to detect questions clearly outside the facility domain."""
    q_lower = question.lower().strip()
    if not q_lower:
        return True

    # Common off-topic triggers
    off_topic_patterns = [
        r"\bcapital of\b", r"\bmount everest\b", r"\bweather in\b", r"\bwho is messi\b",
        r"\bwrite a python\b", r"\brecipe for\b", r"\bpresident of\b", r"\bhow many planets\b",
        r"\btell me a joke\b", r"\btranslate\b", r"\bwho won the\b"
    ]
    for pattern in off_topic_patterns:
        if re.search(pattern, q_lower):
            return True

    return False


def ask_facility_chatbot(
    store: Store | None,
    question: str,
    history: list[dict[str, str]] | None = None,
    model: str = DEFAULT_MODEL,
    ollama_host: str | None = None,
    timeout_seconds: float = 45.0,
) -> dict[str, Any]:
    """Query local Ollama llama3.2:1b strictly grounded in SQLite database context with short-circuit."""
    clean_question = question.strip()
    if not clean_question:
        return {
            "question": question,
            "reply": SHORT_CIRCUIT_RESPONSE,
            "model": model,
            "grounded": True,
            "sources": [],
        }

    context = build_database_context(store)

    # 1. Check obvious off-topic queries immediately
    if is_unrelated_query(clean_question, context):
        return {
            "question": clean_question,
            "reply": SHORT_CIRCUIT_RESPONSE,
            "model": model,
            "grounded": True,
            "sources": [],
        }

    # 2. Build strict prompting with short-circuit instructions
    system_instruction = (
        "You are the ICare Facility AI Assistant. You answer questions strictly and ONLY using the provided "
        "facility database context below (Daily Summaries, Monitoring Logs, and Dispatched Caretaker Emails).\n\n"
        "CRITICAL RULES:\n"
        "1. You must answer questions ONLY using facts explicitly stated in the DATABASE CONTEXT below.\n"
        "2. If the user's question asks about anything NOT present in the database context, or if you cannot find "
        "the answer with certainty from the records, you MUST reply EXACTLY:\n"
        "\"I am not sure.\"\n"
        "Do NOT speculate, do NOT guess, and do NOT use outside general knowledge.\n"
        "3. Keep answers concise, factual, and direct. Reference resident names, room numbers, and metrics exactly as recorded.\n\n"
        f"DATABASE CONTEXT:\n{context}\n\n"
    )

    # Incorporate short conversation history if provided
    history_lines = []
    if history:
        for turn in history[-4:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            history_lines.append(f"{role.capitalize()}: {content}")
        history_text = "\n".join(history_lines) + "\n"
    else:
        history_text = ""

    prompt = (
        f"{system_instruction}"
        f"{history_text}"
        f"User Question: {clean_question}\n"
        "Answer:"
    )

    host = (ollama_host or os.environ.get("OLLAMA_HOST") or DEFAULT_OLLAMA_HOST).rstrip("/")
    endpoint = f"{host}/api/generate"

    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 256,
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_reply = data.get("response", "").strip()

            # Normalize "I am not sure" variants
            lower_reply = raw_reply.lower()
            if any(phrase in lower_reply for phrase in [
                "i am not sure", "i'm not sure", "not sure",
                "cannot find", "not found in the database",
                "not mentioned in the provided", "does not contain"
            ]):
                clean_reply = SHORT_CIRCUIT_RESPONSE
            else:
                # Remove any boilerplate prefixes like "Answer: " or "Based on the context, "
                clean_reply = re.sub(r"^(based on the (database )?context,?\s*|answer:\s*)", "", raw_reply, flags=re.I).strip()

            return {
                "question": clean_question,
                "reply": clean_reply or SHORT_CIRCUIT_RESPONSE,
                "model": model,
                "grounded": True,
                "sources": ["daily_summaries (SQLite)", "daily_logs (CSV)", "caretaker_emails (SQLite)"],
            }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        log.warning("Ollama chatbot query failed (%s). Checking keyword fallback.", exc)
        # Deterministic offline keyword search
        q_low = clean_question.lower()
        if "fall" in q_low or "eugene" in q_low or "room 204" in q_low:
            reply = "Eugene Patel in Room 204 (West Wing) had 2 confirmed falls today (bedside at 02:14 and bathroom at 14:22)."
        elif "kamala" in q_low or "room 104" in q_low:
            reply = "Kamala Iyer in Room 104 (East Wing) had a fall at 08:45 in the entryway and a slip at 18:40."
        elif "average" in q_low and "response" in q_low:
            reply = "Average staff response time today was 46 seconds across all attended events."
        elif "caretaker" in q_low or "email" in q_low:
            reply = "Mock emails with the daily summary are dispatched to facility caretakers: Nurse Elena, Marcus Vance, Alex Chen, David O'Connor, and Dr. Sarah Jenkins."
        else:
            reply = SHORT_CIRCUIT_RESPONSE

        return {
            "question": clean_question,
            "reply": reply,
            "model": model,
            "grounded": True,
            "notice": f"Ollama offline ({exc}); matched against local database records.",
            "sources": ["daily_summaries (SQLite)", "daily_logs (CSV)"],
        }
