"""Automated 10:00 PM daily summary generation, SQLite persistence, and caretaker mock email dispatch."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any
import uuid

from icare.api.store import Store, utc_now
from icare.api.summary import load_daily_logs, summarize_daily_logs

log = logging.getLogger(__name__)

# Standard facility caretakers receiving the nightly 10:00 PM report
DEFAULT_CARETAKERS = [
    {
        "name": "Nurse Elena Rostova",
        "email": "elena.rostova@icare-facility.org",
        "role": "Head Nurse & Night Supervisor"
    },
    {
        "name": "Caregiver Marcus Vance",
        "email": "marcus.vance@icare-facility.org",
        "role": "Senior Resident Caregiver"
    },
    {
        "name": "Duty Staff Alex Chen",
        "email": "alex.chen@icare-facility.org",
        "role": "East Wing Care Coordinator"
    },
    {
        "name": "Nurse David O'Connor",
        "email": "david.oconnor@icare-facility.org",
        "role": "West Wing Charge Nurse"
    },
    {
        "name": "Dr. Sarah Jenkins",
        "email": "s.jenkins@icare-facility.org",
        "role": "Medical Director & Geriatrician"
    },
]

# Track scheduler state in-memory
_SCHEDULER_STATE = {
    "last_run_at": None,
    "last_run_summary_id": None,
    "last_run_status": None,
    "last_run_email_count": 0,
    "target_hour": 22,  # 10:00 PM
}


def get_schedule_status(store: Store | None = None) -> dict[str, Any]:
    """Return status of the daily 10 PM scheduler and latest runs."""
    now = datetime.now()
    target_hour = _SCHEDULER_STATE["target_hour"]
    
    # Calculate next scheduled run at 10 PM
    if now.hour < target_hour:
        next_run_today = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
    else:
        # Tomorrow at 10 PM
        from datetime import timedelta
        next_run_today = (now + timedelta(days=1)).replace(hour=target_hour, minute=0, second=0, microsecond=0)

    latest_summary = store.get_latest_daily_summary() if store else None

    return {
        "scheduled_time": "22:00 (10:00 PM daily)",
        "target_hour": target_hour,
        "is_active": True,
        "next_scheduled_run": next_run_today.strftime("%Y-%m-%d 22:00:00"),
        "last_run_at": _SCHEDULER_STATE["last_run_at"],
        "last_run_status": _SCHEDULER_STATE["last_run_status"],
        "last_run_email_count": _SCHEDULER_STATE["last_run_email_count"],
        "latest_saved_summary": {
            "summary_id": latest_summary["summary_id"],
            "date_str": latest_summary["date_str"],
            "generated_at_utc": latest_summary["generated_at_utc"],
            "model": latest_summary["model"],
            "status": latest_summary["status"],
            "sent_email_count": latest_summary["sent_email_count"],
        } if latest_summary else None,
        "caretakers": DEFAULT_CARETAKERS,
    }


def format_caretaker_email_body(
    caretaker: dict[str, str],
    date_str: str,
    structured_summary: dict[str, Any],
    raw_markdown: str,
) -> tuple[str, str]:
    """Generate subject line and rich clinical email body for a caretaker."""
    stats = structured_summary.get("incident_stats", {})
    falls = stats.get("confirmed_falls", 0)
    total_events = stats.get("total_events", 0)
    avg_resp = stats.get("avg_response_time_seconds", 0)

    subject = f"[ICare Daily Report] 10:00 PM Fall Monitoring Summary - {date_str} ({falls} falls)"

    # Format high risk residents
    high_risk_lines = []
    for r in structured_summary.get("high_risk_residents", []):
        high_risk_lines.append(
            f"  * {r.get('resident_name')} (Room {r.get('room')}, {r.get('wing')} Wing) - [{r.get('risk_level')} Risk]\n"
            f"    - Event: {r.get('incident_summary')}\n"
            f"    - Action Required: {r.get('action_plan')}"
        )
    high_risk_text = "\n".join(high_risk_lines) if high_risk_lines else "  * No residents currently categorized as High Risk."

    # Format recommendations
    recs = [f"  * {rec}" for rec in structured_summary.get("shift_handoff_recommendations", [])]
    recs_text = "\n".join(recs) if recs else "  * Continue standard resident check cycles."

    body = f"""Dear {caretaker['name']} ({caretaker['role']}),

Here is the automated ICare Daily Monitoring Summary generated at 10:00 PM for {date_str}.

============================================================
1. EXECUTIVE SUMMARY
============================================================
{structured_summary.get('executive_summary', 'Daily summary completed.')}

============================================================
2. KEY INCIDENT METRICS
============================================================
* Total Events Monitored: {total_events}
* Confirmed Falls: {falls}
* Near Falls / Slip Alerts: {stats.get('near_falls', 0)}
* Average Staff Response Time: {avg_resp}s

============================================================
3. HIGH-RISK RESIDENTS & NURSING ACTION PLANS
============================================================
{high_risk_text}

============================================================
4. SHIFT HANDOFF RECOMMENDATIONS
============================================================
{recs_text}

============================================================
5. OVERNIGHT SHIFT PRIORITY NOTES
============================================================
{structured_summary.get('shift_handoff_notes', 'Standard shift handover protocols apply.')}

------------------------------------------------------------
Automated Notification from ICare Fall Monitoring System
Data stored in local SQLite facility database.
Recipient: {caretaker['email']}
"""
    return subject, body


def send_mock_emails_to_caretakers(
    store: Store,
    summary_id: str,
    date_str: str,
    structured_summary: dict[str, Any],
    raw_markdown: str,
    caretakers: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Generate and record mock emails dispatched to caretakers in SQLite."""
    recipients = caretakers or DEFAULT_CARETAKERS
    sent_emails: list[dict[str, Any]] = []

    for c in recipients:
        email_id = f"email_{uuid.uuid4().hex[:12]}"
        subject, body = format_caretaker_email_body(c, date_str, structured_summary, raw_markdown)
        now_str = utc_now()
        
        store.save_caretaker_email(
            email_id=email_id,
            summary_id=summary_id,
            recipient_name=c["name"],
            recipient_email=c["email"],
            recipient_role=c["role"],
            subject=subject,
            body_text=body,
            sent_at_utc=now_str,
            status="delivered",
        )
        sent_emails.append({
            "email_id": email_id,
            "summary_id": summary_id,
            "recipient_name": c["name"],
            "recipient_email": c["email"],
            "recipient_role": c["role"],
            "subject": subject,
            "body_preview": body[:160] + "...",
            "sent_at_utc": now_str,
            "status": "delivered",
        })

    store.update_summary_email_count(summary_id, len(sent_emails))
    return sent_emails


def run_daily_10pm_routine(
    store: Store,
    force: bool = False,
    model: str = "llama3.2:1b",
    date_str: str | None = None,
) -> dict[str, Any]:
    """Execute the full 10:00 PM routine: summarise logs, save to SQLite, dispatch mock emails."""
    today_str = date_str or datetime.now().strftime("%Y-%m-%d")
    now_utc = utc_now()
    summary_id = f"sum_{today_str.replace('-', '')}_{datetime.now().strftime('%H%M%S')}"

    log.info("Starting Daily 10:00 PM Routine for %s (Summary ID: %s)...", today_str, summary_id)
    
    # 1. Generate summary from local dummy logs
    logs = load_daily_logs()
    summary_res = summarize_daily_logs(logs=logs, model=model)

    structured = summary_res.get("structured_summary") or {}
    exec_summary = structured.get("executive_summary") or summary_res.get("summary", "")
    raw_markdown = summary_res.get("summary", "")

    # 2. Save into SQLite daily_summaries table
    store.save_daily_summary(
        summary_id=summary_id,
        date_str=today_str,
        model=model,
        status=summary_res.get("status", "success"),
        executive_summary=exec_summary,
        structured_json=json.dumps(structured),
        raw_markdown=raw_markdown,
        log_count=len(logs),
        sent_email_count=0,
        generated_at_utc=now_utc,
    )

    # 3. Dispatch mock emails to caretakers and record in SQLite
    emails = send_mock_emails_to_caretakers(
        store=store,
        summary_id=summary_id,
        date_str=today_str,
        structured_summary=structured,
        raw_markdown=raw_markdown,
    )

    # 4. Update memory state
    _SCHEDULER_STATE["last_run_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _SCHEDULER_STATE["last_run_summary_id"] = summary_id
    _SCHEDULER_STATE["last_run_status"] = summary_res.get("status", "success")
    _SCHEDULER_STATE["last_run_email_count"] = len(emails)

    log.info("Daily 10:00 PM Routine complete: saved summary %s and sent %d emails", summary_id, len(emails))

    return {
        "status": "success",
        "summary_id": summary_id,
        "date_str": today_str,
        "generated_at_utc": now_utc,
        "model": model,
        "summary": summary_res,
        "emails_dispatched": len(emails),
        "emails": emails,
    }


async def start_10pm_daily_scheduler(store: Store, target_hour: int = 22) -> None:
    """Async background worker that triggers the daily routine when local time reaches target_hour (22:00)."""
    _SCHEDULER_STATE["target_hour"] = target_hour
    last_triggered_date: str | None = None

    log.info("10:00 PM Daily Summary & Email Scheduler started (target hour: %02d:00)", target_hour)

    while True:
        try:
            await asyncio.sleep(20)  # Check every 20 seconds
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")

            # Check if current time is within the 10:00 PM hour and haven't run today
            if now.hour == target_hour and last_triggered_date != today_str:
                log.info("Current time is %02d:%02d: Triggering automated 10:00 PM routine...", now.hour, now.minute)
                last_triggered_date = today_str
                await asyncio.to_thread(run_daily_10pm_routine, store=store, force=False, date_str=today_str)
        except asyncio.CancelledError:
            log.info("10:00 PM Daily Scheduler cancelled.")
            break
        except Exception:
            log.exception("Unexpected error in daily 10:00 PM scheduler loop")
