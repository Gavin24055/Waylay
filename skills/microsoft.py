"""
Waylay — Microsoft Graph API Skills
Outlook email + Microsoft Teams integration via Graph API.

━━━ AZURE SETUP (one-time, ~10 minutes) ━━━━━━━━━━━━━━━━━━━━━━━

1. Go to https://portal.azure.com → "App registrations" → "New registration"
   - Name: Waylay
   - Supported account types: "Accounts in any org directory and personal Microsoft accounts"
   - Redirect URI: Mobile and desktop → http://localhost:8080

2. After creation, copy the "Application (client) ID" → add to .env:
   MICROSOFT_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

3. For personal accounts set: MICROSOFT_TENANT_ID=common
   For work/school accounts set it to your org's tenant ID.

4. Go to "API permissions" → "Add a permission" → "Microsoft Graph" → "Delegated":
   Add all of these:
   - Mail.Read
   - Mail.Send
   - Chat.Read
   - Chat.ReadWrite
   - ChatMessage.Send
   - User.Read
   - offline_access  (required for refresh tokens)

5. Click "Grant admin consent" (if you have admin rights)
   OR just run the auth flow — it will ask for consent on first login.

6. No client secret needed for public/mobile apps (which we are).

7. Run the auth setup ONCE:
   python3 -c "from skills.microsoft import setup_microsoft_auth; setup_microsoft_auth()"

8. After that, all skills work automatically using the saved token.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import logging
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import requests

from config import MICROSOFT_CLIENT_ID, MICROSOFT_TENANT_ID, DATA_DIR
from skills.loader import skill

logger = logging.getLogger("j.skills.microsoft")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
TOKEN_PATH = DATA_DIR / "microsoft_token.json"
REDIRECT_URI = "http://localhost:8080"
SCOPES = "Mail.Read Mail.Send Chat.Read Chat.ReadWrite ChatMessage.Send User.Read offline_access"

AUTH_URL_BASE = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
TOKEN_URL_BASE = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"


# ── Token Management ─────────────────────────────────────────────

def _load_token() -> dict | None:
    """Load saved token from disk."""
    try:
        if TOKEN_PATH.exists():
            return json.loads(TOKEN_PATH.read_text())
    except Exception:
        pass
    return None


def _save_token(token: dict):
    """Save token to disk."""
    TOKEN_PATH.write_text(json.dumps(token, indent=2))
    logger.info("Microsoft token saved to %s", TOKEN_PATH)


def _refresh_token(token: dict) -> dict | None:
    """Use refresh_token to get a new access token."""
    if not token.get("refresh_token"):
        return None
    try:
        resp = requests.post(
            TOKEN_URL_BASE.format(tenant=MICROSOFT_TENANT_ID),
            data={
                "grant_type": "refresh_token",
                "client_id": MICROSOFT_CLIENT_ID,
                "refresh_token": token["refresh_token"],
                "scope": SCOPES,
            },
            timeout=15,
        )
        resp.raise_for_status()
        new_token = resp.json()
        if "refresh_token" not in new_token and "refresh_token" in token:
            new_token["refresh_token"] = token["refresh_token"]
        _save_token(new_token)
        return new_token
    except Exception as e:
        logger.error("Token refresh failed: %s", e)
        return None


def _get_access_token() -> str | None:
    """Get a valid access token, refreshing if needed."""
    import time
    token = _load_token()
    if not token:
        return None

    # Check if token is expired (with 60s buffer)
    expires_at = token.get("expires_at", 0)
    if time.time() < expires_at - 60:
        return token.get("access_token")

    # Refresh
    new_token = _refresh_token(token)
    if new_token:
        return new_token.get("access_token")
    return None


def _graph_get(endpoint: str, params: dict = None) -> dict | None:
    """Make an authenticated GET request to Graph API."""
    token = _get_access_token()
    if not token:
        logger.warning("No Microsoft token — run setup_microsoft_auth() first")
        return None

    try:
        resp = requests.get(
            f"{GRAPH_BASE}{endpoint}",
            headers={"Authorization": f"Bearer {token}"},
            params=params or {},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error("Graph API GET %s failed: %s", endpoint, e)
        return None


def _graph_post(endpoint: str, body: dict) -> dict | None:
    """Make an authenticated POST request to Graph API."""
    token = _get_access_token()
    if not token:
        return None
    try:
        resp = requests.post(
            f"{GRAPH_BASE}{endpoint}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json() if resp.content else {"ok": True}
    except Exception as e:
        logger.error("Graph API POST %s failed: %s", endpoint, e)
        return None


# ── OAuth2 Setup ─────────────────────────────────────────────────

def setup_microsoft_auth():
    """
    Run the OAuth2 browser-based auth flow.
    Opens browser, user logs in, token saved to data/microsoft_token.json.
    Call this ONCE from command line:
      python3 -c "from skills.microsoft import setup_microsoft_auth; setup_microsoft_auth()"
    """
    if not MICROSOFT_CLIENT_ID:
        print("\n❌ MICROSOFT_CLIENT_ID not set in .env")
        print("   Follow the Azure setup guide at the top of skills/microsoft.py\n")
        return

    auth_code_holder = {}
    server_done = threading.Event()

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            qs = parse_qs(urlparse(self.path).query)
            if "code" in qs:
                auth_code_holder["code"] = qs["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h2>Waylay: Auth complete! You can close this tab.</h2>")
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"<h2>Auth failed - no code returned.</h2>")
            server_done.set()

        def log_message(self, *args):
            pass  # Suppress server logs

    # Build auth URL
    params = {
        "client_id": MICROSOFT_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "response_mode": "query",
        "scope": SCOPES,
    }
    auth_url = AUTH_URL_BASE.format(tenant=MICROSOFT_TENANT_ID) + "?" + urlencode(params)

    print(f"\n🌐 Opening browser for Microsoft login...")
    print(f"   If browser doesn't open, go to:\n   {auth_url}\n")
    webbrowser.open(auth_url)

    # Start local server to catch redirect
    server = HTTPServer(("localhost", 8080), CallbackHandler)
    server_thread = threading.Thread(target=server.handle_request)
    server_thread.start()
    server_done.wait(timeout=120)

    if "code" not in auth_code_holder:
        print("❌ Auth timed out or failed.")
        return

    # Exchange code for token
    import time
    resp = requests.post(
        TOKEN_URL_BASE.format(tenant=MICROSOFT_TENANT_ID),
        data={
            "grant_type": "authorization_code",
            "client_id": MICROSOFT_CLIENT_ID,
            "code": auth_code_holder["code"],
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
        },
        timeout=15,
    )
    resp.raise_for_status()
    token = resp.json()
    token["expires_at"] = time.time() + token.get("expires_in", 3600)
    _save_token(token)

    print("✅ Microsoft auth complete! Token saved.")
    print("   You can now use: read_outlook_emails, get_teams_messages, etc.")


# ── Skills ───────────────────────────────────────────────────────

def _check_auth_configured() -> str | None:
    """Returns error message if auth is not set up, None if OK."""
    if not MICROSOFT_CLIENT_ID:
        return (
            "Microsoft not configured. Add MICROSOFT_CLIENT_ID to .env, "
            "then run: python3 -c \"from skills.microsoft import setup_microsoft_auth; setup_microsoft_auth()\""
        )
    if not _get_access_token():
        return (
            "Microsoft auth needed. Run: "
            "python3 -c \"from skills.microsoft import setup_microsoft_auth; setup_microsoft_auth()\""
        )
    return None


@skill
def read_outlook_emails(count: int = 5, unread_only: bool = True) -> str:
    """Read recent Outlook emails via Microsoft Graph API."""
    err = _check_auth_configured()
    if err:
        return err

    params = {
        "$top": count,
        "$orderby": "receivedDateTime desc",
        "$select": "from,subject,bodyPreview,isRead,receivedDateTime",
    }
    if unread_only:
        params["$filter"] = "isRead eq false"

    data = _graph_get("/me/messages", params)
    if not data:
        return "Could not fetch Outlook emails."

    messages = data.get("value", [])
    if not messages:
        return "No unread emails in Outlook." if unread_only else "No emails found."

    parts = [f"You have {len(messages)} {'unread ' if unread_only else ''}email(s) in Outlook:"]
    for m in messages:
        sender = m.get("from", {}).get("emailAddress", {}).get("name", "Unknown")
        subject = m.get("subject", "(no subject)")
        preview = m.get("bodyPreview", "")[:80]
        parts.append(f"• From {sender}: \"{subject}\" — {preview}")

    return "\n".join(parts)


@skill
def get_teams_messages(count: int = 5) -> str:
    """Get recent Microsoft Teams messages from all chats."""
    err = _check_auth_configured()
    if err:
        return err

    # Get list of chats
    chats_data = _graph_get("/me/chats", {"$top": 10, "$expand": "members"})
    if not chats_data:
        return "Could not fetch Teams chats."

    chats = chats_data.get("value", [])
    if not chats:
        return "No Teams chats found."

    results = []
    for chat in chats[:5]:
        chat_id = chat.get("id")
        if not chat_id:
            continue

        # Get recent messages from this chat
        msgs_data = _graph_get(
            f"/me/chats/{chat_id}/messages",
            {"$top": 3, "$orderby": "createdDateTime desc"}
        )
        if not msgs_data:
            continue

        for msg in msgs_data.get("value", []):
            # Skip system/event messages
            msg_type = msg.get("messageType", "")
            if msg_type != "message":
                continue

            sender = msg.get("from", {}).get("user", {}).get("displayName", "Someone")
            body = msg.get("body", {}).get("content", "")
            # Strip HTML tags simply
            import re
            body = re.sub(r"<[^>]+>", "", body).strip()[:100]

            if body:
                results.append(f"• {sender} in Teams: \"{body}\"")

    if not results:
        return "No recent Teams messages."

    return f"Recent Teams messages:\n" + "\n".join(results[:count])


@skill
def get_teams_messages_from(user: str) -> str:
    """Get recent Teams messages from a specific person by name."""
    err = _check_auth_configured()
    if err:
        return err

    chats_data = _graph_get("/me/chats", {"$top": 20, "$expand": "members"})
    if not chats_data:
        return "Could not fetch Teams chats."

    import re
    target = user.lower()
    results = []

    for chat in chats_data.get("value", []):
        # Check if this chat has the target user
        members = chat.get("members", [])
        has_user = any(
            target in m.get("displayName", "").lower()
            for m in members
        )
        if not has_user:
            continue

        chat_id = chat.get("id")
        msgs_data = _graph_get(
            f"/me/chats/{chat_id}/messages",
            {"$top": 5, "$orderby": "createdDateTime desc"}
        )
        if not msgs_data:
            continue

        for msg in msgs_data.get("value", []):
            if msg.get("messageType") != "message":
                continue
            sender = msg.get("from", {}).get("user", {}).get("displayName", "")
            if target not in sender.lower():
                continue
            body = msg.get("body", {}).get("content", "")
            body = re.sub(r"<[^>]+>", "", body).strip()[:120]
            if body:
                results.append(f"{sender}: \"{body}\"")

    if not results:
        return f"No recent Teams messages from {user}."
    return f"Messages from {user} on Teams:\n" + "\n".join(results[:5])


@skill
def send_teams_message(user: str, message: str) -> str:
    """
    Send a Teams message to a user by display name.
    ALWAYS returns a confirmation request — never sends silently.
    """
    err = _check_auth_configured()
    if err:
        return err

    # Find the chat with this user
    chats_data = _graph_get("/me/chats", {"$top": 20, "$expand": "members"})
    if not chats_data:
        return "Could not access Teams chats."

    target = user.lower()
    chat_id = None

    for chat in chats_data.get("value", []):
        members = chat.get("members", [])
        for m in members:
            if target in m.get("displayName", "").lower():
                chat_id = chat.get("id")
                break
        if chat_id:
            break

    if not chat_id:
        return f"Couldn't find a Teams chat with {user}. Make sure you've chatted with them before."

    # Send the message
    result = _graph_post(
        f"/me/chats/{chat_id}/messages",
        {"body": {"content": message}}
    )
    if result:
        logger.info("Teams message sent to %s", user)
        return f"Message sent to {user} on Teams: \"{message}\""
    return f"Failed to send Teams message to {user}."


@skill
def get_teams_notifications() -> str:
    """Get recent Teams activity notifications and mentions."""
    err = _check_auth_configured()
    if err:
        return err

    # Use /me/chats for unread counts as activity feed requires extra setup
    chats_data = _graph_get("/me/chats", {
        "$top": 10,
        "$orderby": "lastUpdatedDateTime desc"
    })
    if not chats_data:
        return "Could not fetch Teams notifications."

    chats = chats_data.get("value", [])
    if not chats:
        return "No recent Teams activity."

    results = []
    for chat in chats[:5]:
        topic = chat.get("topic") or "Direct message"
        updated = chat.get("lastUpdatedDateTime", "")[:10]
        results.append(f"• {topic} — updated {updated}")

    return "Recent Teams activity:\n" + "\n".join(results)
