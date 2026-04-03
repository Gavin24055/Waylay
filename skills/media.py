"""
J — Media Control Skills
Play/pause, volume, music playback.
"""

import logging
import subprocess
import os
from skills.loader import skill

logger = logging.getLogger("j.skills.media")


@skill
def media_playpause() -> str:
    """Toggle play/pause for media."""
    try:
        # macOS: simulate media key
        subprocess.run([
            "osascript", "-e",
            'tell application "System Events" to key code 49',  # space
        ], timeout=3)
        return "Toggled play/pause"
    except Exception:
        try:
            import pyautogui
            pyautogui.press("playpause")
            return "Toggled play/pause"
        except Exception as e:
            return f"Media control failed: {e}"


@skill
def media_volume(level: int) -> str:
    """Set system volume (0-100)."""
    level = max(0, min(100, level))
    try:
        # macOS
        vol_7 = round(level * 7 / 100)  # macOS volume is 0-7
        subprocess.run([
            "osascript", "-e",
            f'set volume output volume {level}',
        ], timeout=3)
        logger.info("Volume set to %d%%", level)
        return f"Volume set to {level}%"
    except Exception:
        try:
            # Windows fallback with nircmd or similar
            return f"Volume control not available on this platform"
        except Exception as e:
            return f"Volume control failed: {e}"


@skill
def play_music(query: str) -> str:
    """Open a music search in the default browser (Spotify Web or YouTube)."""
    import webbrowser
    try:
        # Try Spotify web search
        url = f"https://open.spotify.com/search/{query}"
        webbrowser.open(url)
        logger.info("Opened Spotify search: %s", query)
        return f"Opened Spotify search for '{query}'"
    except Exception:
        try:
            url = f"https://www.youtube.com/results?search_query={query}"
            webbrowser.open(url)
            return f"Opened YouTube search for '{query}'"
        except Exception as e:
            return f"Couldn't open music: {e}"
