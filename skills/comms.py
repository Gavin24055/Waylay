"""
J — Communications Skills
Gmail API read/send, Google Calendar events.
Requires OAuth2 credentials.json setup.
"""

import os
import logging
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from config import GOOGLE_CREDENTIALS_PATH, DATA_DIR
from skills.loader import skill

logger = logging.getLogger("j.skills.comms")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
]
TOKEN_PATH = DATA_DIR / "google_token.pickle"


def _get_google_creds():
    """Get or refresh Google OAuth2 credentials."""
    creds = None

    if TOKEN_PATH.exists():
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        try:
            creds.refresh(Request())
            with open(TOKEN_PATH, "wb") as f:
                pickle.dump(creds, f)
            return creds
        except Exception as e:
            logger.warning("Token refresh failed: %s", e)

    if not Path(GOOGLE_CREDENTIALS_PATH).exists():
        logger.warning("Google credentials.json not found at %s", GOOGLE_CREDENTIALS_PATH)
        return None

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CREDENTIALS_PATH, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)
        return creds
    except Exception as e:
        logger.error("Google OAuth failed: %s", e)
        return None


def _get_gmail_service():
    from googleapiclient.discovery import build
    creds = _get_google_creds()
    if not creds:
        return None
    return build("gmail", "v1", credentials=creds)


def _get_calendar_service():
    from googleapiclient.discovery import build
    creds = _get_google_creds()
    if not creds:
        return None
    return build("calendar", "v3", credentials=creds)


@skill
def read_emails(count: int = 5, unread_only: bool = True) -> str:
    """Read recent emails from Gmail."""
    service = _get_gmail_service()
    if not service:
        return "Gmail not configured. Run OAuth setup first (need credentials.json)."

    try:
        query = "is:unread" if unread_only else ""
        results = service.users().messages().list(
            userId="me", q=query, maxResults=count
        ).execute()

        messages = results.get("messages", [])
        if not messages:
            return "No unread emails." if unread_only else "No emails found."

        output = []
        for msg_ref in messages:
            msg = service.users().messages().get(
                userId="me", id=msg_ref["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            output.append(
                f"• From: {headers.get('From', 'Unknown')}\n"
                f"  Subject: {headers.get('Subject', '(no subject)')}\n"
                f"  Date: {headers.get('Date', '')}"
            )
        return "\n\n".join(output)
    except Exception as e:
        logger.error("Email read failed: %s", e)
        return f"Email read failed: {e}"


@skill
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email via Gmail. ALWAYS confirm with user first."""
    service = _get_gmail_service()
    if not service:
        return "Gmail not configured. Run OAuth setup first."

    try:
        import base64
        from email.mime.text import MIMEText

        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()

        logger.info("Email sent to %s: %s", to, subject)
        return f"Email sent to {to}"
    except Exception as e:
        logger.error("Email send failed: %s", e)
        return f"Email send failed: {e}"


@skill
def search_emails(query: str) -> str:
    """Search emails by query string."""
    service = _get_gmail_service()
    if not service:
        return "Gmail not configured."

    try:
        results = service.users().messages().list(
            userId="me", q=query, maxResults=5
        ).execute()

        messages = results.get("messages", [])
        if not messages:
            return "No emails match that search."

        output = []
        for msg_ref in messages:
            msg = service.users().messages().get(
                userId="me", id=msg_ref["id"], format="metadata",
                metadataHeaders=["From", "Subject"],
            ).execute()
            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            output.append(f"• {headers.get('From', '?')} — {headers.get('Subject', '(no subject)')}")
        return "\n".join(output)
    except Exception as e:
        return f"Search failed: {e}"


@skill
def get_calendar_events(days_ahead: int = 1) -> str:
    """Get upcoming Google Calendar events."""
    service = _get_calendar_service()
    if not service:
        return "Calendar not configured. Run OAuth setup first."

    try:
        now = datetime.utcnow()
        time_min = now.isoformat() + "Z"
        time_max = (now + timedelta(days=days_ahead)).isoformat() + "Z"

        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = events_result.get("items", [])
        if not events:
            return "No events scheduled." if days_ahead <= 1 else f"No events in the next {days_ahead} days."

        output = []
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            summary = event.get("summary", "(no title)")
            output.append(f"• {start}: {summary}")
        return "\n".join(output)
    except Exception as e:
        logger.error("Calendar read failed: %s", e)
        return f"Calendar read failed: {e}"


@skill
def create_reminder(title: str, time: str = None, notes: str = None) -> str:
    """Create a reminder (stored locally in tasks table)."""
    # Use structured memory to store as a task
    try:
        from memory.structured import StructuredMemory
        db = StructuredMemory()
        db.add_task(project_id=None, title=f"[Reminder] {title}", priority="high")
        logger.info("Reminder created: %s", title)
        return f"Reminder set: {title}"
    except Exception as e:
        return f"Failed to create reminder: {e}"
