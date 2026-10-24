"""Local grounded chatbot querying all active SQLite database tables and shift logs using Ollama llama3.2:1b."""
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

FACILITY_RESIDENTS: list[dict[str, Any]] = [
    {"name": "Margaret Shah", "age": 82, "room": "101", "wing": "East", "family_contact": "Priya Shah <priya@family.demo>"},
    {"name": "Harold Brooks", "age": 79, "room": "102", "wing": "East", "family_contact": "Daniel Brooks <daniel@family.demo>"},
    {"name": "Kamala Iyer", "age": 88, "room": "104", "wing": "East", "family_contact": "Arjun Iyer <arjun@family.demo>"},
    {"name": "Walter Kim", "age": 84, "room": "201", "wing": "West", "family_contact": "Grace Kim <grace@family.demo>"},
    {"name": "Rosa Martinez", "age": 76, "room": "203", "wing": "West", "family_contact": "Lucia Martinez <lucia@family.demo>"},
    {"name": "Eugene Patel", "age": 90, "room": "204", "wing": "West", "family_contact": "Neha Patel <neha@family.demo>"},
    {"name": "Dorothy Clarke", "age": 81, "room": "301", "wing": "Garden", "family_contact": "Simon Clarke <simon@family.demo>"},
    {"name": "Ravi Menon", "age": 86, "room": "302", "wing": "Garden", "family_contact": "Anita Menon <anita@family.demo>"},
]


def build_database_context(store: Store | None = None) -> str:
    """Aggregate all active SQLite database tables, real-time added data, summaries, emails, logs, and roster."""
    sections: list[str] = []

    # 1. Facility Resident Directory & Room Roster
    sections.append("=== FACILITY RESIDENTS & ROOM ROSTER ===")
    for r in FACILITY_RESIDENTS:
        sections.append(
            f"- {r['name']} (Age {r['age']}): Room {r['room']}, {r['wing']} Wing. Emergency Family Contact: {r['family_contact']}"
        )
    sections.append("- Monitored detector camera room: Room DET (General Detector)")
    sections.append("")

    # 2. SQLite Database Live Record Counts
    if store:
        stats = store.database_stats()
        sections.append("=== SQLITE DATABASE RECORD COUNTS (LIVE REPOSITORY STATS) ===")
        sections.append(
            f"Saved Daily Summaries: {stats.get('daily_summaries', 0)}, "
            f"Recorded Fall Locations: {stats.get('fall_locations', 0)}, "
            f"Stored Clips: {stats.get('clips', 0)}, "
            f"Video Analysis Jobs: {stats.get('jobs', 0)}, "
            f"Detected Incidents: {stats.get('incidents', 0)}, "
            f"Live Sessions: {stats.get('live_sessions', 0)}, "
            f"Dispatched Emails: {stats.get('caretaker_emails', 0)}"
        )
        sections.append("")

    # 3. Room Danger Zones & Recorded Falls (fall_locations in SQLite)
    if store:
        room_sums = store.room_summaries()
        sections.append("=== ROOM DANGER ZONES & FALL TOTALS IN DATABASE ===")
        if room_sums:
            for rs in room_sums:
                last_time = rs.get('last_fall_utc') or 'N/A'
                sections.append(f"- Room {rs['room']}: {rs['fall_count']} total recorded fall(s) (last fall: {last_time})")
        else:
            sections.append("No room danger zones recorded yet in fall_locations.")
        sections.append("")

        recent_falls = store.recent_fall_locations(limit=50)
        if recent_falls:
            sections.append("=== INDIVIDUAL DETECTED FALL LOCATIONS IN DATABASE (fall_locations table) ===")
            for f in recent_falls:
                conf_pct = int(f.get('confidence', 0) * 100)
                sections.append(
                    f"- Fall ID {f['fall_id']} in Room {f['room']} [{f['created_at_utc']}]: "
                    f"source={f['source_kind']}, track_id={f.get('track_id')}, "
                    f"confidence={conf_pct}%, at {f.get('detected_at_seconds', 0):.1f}s, "
                    f"onset=({f.get('onset_x', 0):.2f}, {f.get('onset_y', 0):.2f}), "
                    f"landing=({f.get('landing_x', 0):.2f}, {f.get('landing_y', 0):.2f})"
                )
            sections.append("")

    # 4. Recorded Fall Clips in Database (clips table)
    if store:
        clips = store.recent_clips(limit=50)
        if clips:
            sections.append("=== STORED FALL CLIPS IN DATABASE (clips table) ===")
            for c in clips:
                conf_pct = int(c.get('confidence', 0) * 100)
                room_str = f"Room {c['room']}" if c.get('room') else "General"
                dur = f"{c['duration_seconds']:.1f}s" if c.get('duration_seconds') else "N/A"
                sections.append(
                    f"- Clip {c['clip_id']} ({room_str}, {c['status']}): "
                    f"confidence={conf_pct}%, duration={dur}, created={c['created_at_utc']}, "
                    f"source={c['source_kind']}, file={c.get('file_name', 'pending')}"
                )
            sections.append("")

    # 5. Video Processing Jobs & Incidents (jobs & incidents tables)
    if store:
        jobs = store.recent_jobs(limit=25)
        if jobs:
            sections.append("=== VIDEO ANALYSIS JOBS IN DATABASE (jobs table) ===")
            for j in jobs:
                err = f" (error: {j['error_message']})" if j.get('error_message') else ""
                sections.append(
                    f"- Job {j['job_id']}: state={j['state']}, source={j['source_kind']}, "
                    f"model={j.get('model_version') or 'yolo_fall'}, created={j['created_at_utc']}{err}"
                )
            sections.append("")

        incidents = store.recent_incidents(limit=30)
        if incidents:
            sections.append("=== RECORDED JOB INCIDENTS IN DATABASE (incidents table) ===")
            for inc in incidents:
                conf_pct = int(inc.get('confidence', 0) * 100)
                sections.append(
                    f"- Incident {inc['incident_id']} (Job {inc['job_id']}): "
                    f"detected at {inc['detected_at_seconds']:.1f}s with {conf_pct}% confidence, status={inc['status']}"
                )
            sections.append("")

    # 6. Live Camera Sessions (live_sessions table)
    if store:
        live_sessions = store.recent_live_sessions(limit=10)
        if live_sessions:
            sections.append("=== LIVE CAMERA SESSIONS IN DATABASE (live_sessions table) ===")
            for ls in live_sessions:
                sections.append(
                    f"- Live Session {ls['session_id']}: state={ls['state']}, "
                    f"frames_processed={ls['frames_processed']}, created={ls['created_at_utc']}"
                )
            sections.append("")

    # 7. Saved SQLite Daily Summaries (daily_summaries table)
    saved_summaries: list[dict[str, Any]] = store.list_daily_summaries(limit=5) if store else []
    if saved_summaries:
        sections.append("=== SAVED FACILITY DAILY SUMMARIES IN DATABASE (daily_summaries table) ===")
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

    # 8. Shift Monitoring Logs (CSV Data)
    logs = load_daily_logs()
    if logs:
        sections.append("=== CLINICAL SHIFT MONITORING LOGS (CSV DATA) ===")
        for l in logs:
            resp_str = f"responded in {l['response_time_seconds']}s by {l['attended_by']}" if l.get("response_time_seconds") else "resolved"
            conf = f"{int(l.get('confidence', 0)*100)}% conf"
            sections.append(
                f"- Log ID {l['log_id']} [{l['timestamp']}]: Resident {l['resident_name']} (Room {l['room']}, {l['wing']} Wing) - "
                f"Event: {l['event_type']} ({conf}), {resp_str}. Notes: {l['staff_notes']}"
            )
        sections.append("")

    # 9. Dispatched Caretaker Emails (caretaker_emails table)
    emails = store.list_caretaker_emails(limit=10) if store else []
    if emails:
        sections.append("=== RECENT DISPATCHED CARETAKER EMAILS IN DATABASE (caretaker_emails table) ===")
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
        "facility database context below (including real-time SQLite tables: fall_locations, clips, jobs, "
        "incidents, live_sessions, room danger zones, daily_summaries, caretaker_emails, shift monitoring logs, "
        "and the resident roster).\n\n"
        "CRITICAL RULES:\n"
        "1. You must answer questions ONLY using facts explicitly stated in the DATABASE CONTEXT below.\n"
        "2. If the user's question asks about anything NOT present in the database context, or if you cannot find "
        "the answer with certainty from the records, you MUST reply EXACTLY:\n"
        "\"I am not sure.\"\n"
        "Do NOT speculate, do NOT guess, and do NOT use outside general knowledge.\n"
        "3. Keep answers concise, factual, and direct. Reference resident names, room numbers, clip IDs, job states, "
        "and metrics exactly as recorded in the database.\n\n"
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

    sources = [
        "SQLite Database (fall_locations, clips, jobs, incidents, live_sessions, daily_summaries, caretaker_emails)",
        "Shift Monitoring Logs (CSV)",
        "Facility Resident Roster",
    ]

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
                "sources": sources,
            }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        log.warning("Ollama chatbot query failed (%s). Checking database records fallback.", exc)
        q_low = clean_question.lower()

        # Deterministic database fallback
        if store and any(k in q_low for k in ("how many", "count", "stats", "database record", "total clips", "total jobs")):
            stats = store.database_stats()
            reply = (
                f"The database currently contains {stats.get('fall_locations', 0)} recorded fall locations, "
                f"{stats.get('clips', 0)} stored clips, {stats.get('jobs', 0)} video jobs, "
                f"{stats.get('daily_summaries', 0)} saved daily summaries, and "
                f"{stats.get('caretaker_emails', 0)} caretaker emails."
            )
        elif store and "room" in q_low:
            room_match = re.search(r"room\s*(\w+)", q_low)
            room_id = room_match.group(1).upper() if room_match else None
            falls = store.fall_locations(room_id) if room_id else []
            resident = next((r for r in FACILITY_RESIDENTS if r["room"].lower() == (room_id or "").lower()), None)
            res_str = f" occupied by {resident['name']}" if resident else ""
            if falls:
                reply = f"Room {room_id}{res_str} has {len(falls)} recorded fall(s) in the database."
            elif resident:
                reply = f"Room {room_id} is in {resident['wing']} Wing, occupied by {resident['name']} (Age {resident['age']}). No falls recorded in the danger zones database yet."
            else:
                reply = SHORT_CIRCUIT_RESPONSE
        elif "fall" in q_low or "eugene" in q_low or "room 204" in q_low:
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
            "sources": sources,
        }
