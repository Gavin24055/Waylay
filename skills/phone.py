"""
J — Phone Skills (ADB via phone-mcp)
Answer/reject calls, SMS, notifications, screenshot, battery.
"""

import logging
import subprocess
from config import PHONE_SERIAL
from skills.loader import skill

logger = logging.getLogger("j.skills.phone")


def _adb(*args) -> str:
    """Run an ADB command and return the output."""
    cmd = ["adb"]
    if PHONE_SERIAL:
        cmd.extend(["-s", PHONE_SERIAL])
    cmd.extend(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.stdout.strip()
    except FileNotFoundError:
        return "ADB not found. Install Android platform-tools."
    except subprocess.TimeoutExpired:
        return "ADB command timed out"
    except Exception as e:
        return f"ADB error: {e}"


@skill
def phone_answer_call() -> str:
    """Answer an incoming phone call."""
    result = _adb("shell", "input", "keyevent", "KEYCODE_CALL")
    logger.info("Answered phone call")
    return "Answered the call" if "error" not in result.lower() else result


@skill
def phone_reject_call() -> str:
    """Reject an incoming phone call."""
    result = _adb("shell", "input", "keyevent", "KEYCODE_ENDCALL")
    logger.info("Rejected phone call")
    return "Rejected the call" if "error" not in result.lower() else result


@skill
def phone_send_sms(contact: str, message: str) -> str:
    """Send an SMS. ALWAYS confirm with user before sending."""
    result = _adb(
        "shell", "am", "start",
        "-a", "android.intent.action.SENDTO",
        "-d", f"sms:{contact}",
        "--es", "sms_body", message,
        "--ez", "exit_on_sent", "true",
    )
    logger.info("SMS composed to %s: %s", contact, message[:50])
    return f"SMS to {contact} composed (review on phone and tap send)"


@skill
def phone_get_notifications() -> str:
    """Get current phone notifications via dumpsys."""
    output = _adb("shell", "dumpsys", "notification", "--noredact")
    if "error" in output.lower() or "not found" in output.lower():
        return output

    # Parse notification snippets
    lines = output.split("\n")
    notifications = []
    for line in lines:
        if "android.title=" in line or "android.text=" in line:
            text = line.strip().split("=", 1)[-1].strip()
            if text and len(text) > 2:
                notifications.append(f"• {text}")

    if not notifications:
        return "No notifications on phone"
    return "\n".join(notifications[:15])


@skill
def phone_screenshot() -> str:
    """Take a screenshot of the phone screen."""
    from config import DATA_DIR
    from datetime import datetime

    remote = "/sdcard/j_screenshot.png"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    local = DATA_DIR / f"phone_screenshot_{ts}.png"

    _adb("shell", "screencap", "-p", remote)
    _adb("pull", remote, str(local))
    _adb("shell", "rm", remote)

    logger.info("Phone screenshot: %s", local)
    return str(local)


@skill
def phone_launch_app(package: str) -> str:
    """Launch an app on the phone by package name."""
    result = _adb("shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")
    logger.info("Launched phone app: %s", package)
    return f"Launched {package}" if "error" not in result.lower() else result


@skill
def phone_battery() -> str:
    """Get phone battery level."""
    output = _adb("shell", "dumpsys", "battery")
    lines = output.split("\n")
    info = {}
    for line in lines:
        if "level:" in line:
            info["level"] = line.split(":")[-1].strip()
        elif "status:" in line:
            status_code = line.split(":")[-1].strip()
            statuses = {"1": "unknown", "2": "charging", "3": "discharging", "4": "not charging", "5": "full"}
            info["status"] = statuses.get(status_code, status_code)
        elif "temperature:" in line:
            temp = line.split(":")[-1].strip()
            info["temp"] = f"{int(temp) / 10:.1f}°C"

    if info:
        return f"Phone battery: {info.get('level', '?')}% ({info.get('status', '?')}), temp: {info.get('temp', '?')}"
    return output
