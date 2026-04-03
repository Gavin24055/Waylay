"""
J — Morning Briefing Generator
Generates the morning briefing text for weekdays at 8:15 AM.
"""

import logging
from datetime import datetime, timedelta, timezone
import pytz
import requests
from config import OPENWEATHER_API_KEY, USER_LOCATION, USER_NAME, TIMEZONE

logger = logging.getLogger("j.proactive.briefing")


def generate_morning_briefing(structured_memory=None) -> str:
    """
    Build and return the morning briefing text.
    Format:
    "Morning Luttu. [Weather]. [Calendar]. [Emails]. [F1]. [Tasks]."
    """
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    parts = [f"Morning {USER_NAME}."]

    # ── Weather ──────────────────────────────────────────────────
    weather = _get_weather_summary()
    if weather:
        parts.append(weather)

    # ── Calendar ─────────────────────────────────────────────────
    calendar = _get_calendar_summary()
    if calendar:
        parts.append(calendar)

    # ── Emails ───────────────────────────────────────────────────
    email_summary = _get_email_summary()
    if email_summary:
        parts.append(email_summary)

    # ── F1 (if race weekend) ─────────────────────────────────────
    f1 = _get_f1_today()
    if f1:
        parts.append(f1)

    # ── Tasks ────────────────────────────────────────────────────
    if structured_memory:
        tasks = structured_memory.get_tasks_today()
        high_priority = [t for t in tasks if t["priority"] in ("critical", "high")]
        if high_priority:
            task_names = ", ".join(t["title"] for t in high_priority[:3])
            parts.append(f"Quick reminder — {task_names}.")

    parts.append("Have a good one.")
    return " ".join(parts)


def _get_weather_summary() -> str:
    """Get a brief weather summary."""
    if not OPENWEATHER_API_KEY:
        return ""
    try:
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": USER_LOCATION, "appid": OPENWEATHER_API_KEY, "units": "metric"},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            desc = data["weather"][0]["description"]
            temp = data["main"]["temp"]
            return f"It's {desc} in {USER_LOCATION}, {temp:.0f} degrees."
    except Exception:
        pass
    return ""


def _get_calendar_summary() -> str:
    """Get today's calendar events count and list."""
    try:
        from skills.comms import get_calendar_events
        events = get_calendar_events(days_ahead=1)
        if events and "not configured" not in events.lower() and "no events" not in events.lower():
            count = events.count("•")
            return f"You've got {count} thing{'s' if count != 1 else ''} on your calendar today."
    except Exception:
        pass
    return ""


def _get_email_summary() -> str:
    """Get unread email count and top sender."""
    try:
        from skills.comms import read_emails
        emails = read_emails(count=3, unread_only=True)
        if emails and "not configured" not in emails.lower() and "no unread" not in emails.lower():
            count = emails.count("•")
            # Extract first sender
            lines = emails.split("\n")
            first_from = ""
            first_subject = ""
            for line in lines:
                if "From:" in line:
                    first_from = line.split("From:")[-1].strip()
                    break
            for line in lines:
                if "Subject:" in line:
                    first_subject = line.split("Subject:")[-1].strip()
                    break

            msg = f"{count} unread email{'s' if count != 1 else ''}"
            if first_from:
                msg += f", top one is from {first_from}"
                if first_subject:
                    msg += f" about {first_subject}"
            return msg + "."
    except Exception:
        pass
    return ""


def _get_f1_today() -> str:
    """Check if there's an F1 session today."""
    try:
        now = datetime.now(timezone.utc)
        resp = requests.get(
            "https://api.openf1.org/v1/sessions",
            params={
                "year": now.year,
                "date_start>": now.strftime("%Y-%m-%dT00:00:00"),
                "date_start<": (now + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00"),
            },
            timeout=5,
        )
        if resp.status_code == 200:
            sessions = resp.json()
            if sessions:
                names = [s.get("session_name", "") for s in sessions]
                session_list = ", ".join(names)
                return f"F1 today — {session_list}."
    except Exception:
        pass
    return ""
