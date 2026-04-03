"""
J — Context Builder
Builds the full system prompt with live runtime data injected.
"""

import logging
from datetime import datetime
import pytz
import psutil
from config import SYSTEM_PROMPT_PATH, TIMEZONE, USER_LOCATION

logger = logging.getLogger("j.brain.context")


class ContextBuilder:
    """Builds the system prompt with live data and memory context."""

    def __init__(self, episodic_memory=None, structured_memory=None):
        self.episodic = episodic_memory
        self.structured = structured_memory
        self._prompt_template = None

    @property
    def prompt_template(self) -> str:
        if self._prompt_template is None:
            try:
                self._prompt_template = SYSTEM_PROMPT_PATH.read_text()
                logger.info("Loaded system prompt from %s", SYSTEM_PROMPT_PATH)
            except FileNotFoundError:
                logger.warning("system_prompt.txt not found, using minimal prompt")
                self._prompt_template = "You are J, a personal AI assistant for Gavin."
        return self._prompt_template

    def _get_active_window(self) -> str:
        """Get the currently focused window title."""
        try:
            import subprocess
            # macOS
            result = subprocess.run(
                ["osascript", "-e", 'tell application "System Events" to get name of first application process whose frontmost is true'],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

        try:
            # Windows fallback
            import pyautogui
            win = pyautogui.getActiveWindow()
            if win:
                return win.title
        except Exception:
            pass
        return "Unknown"

    def _get_battery(self) -> str:
        battery = psutil.sensors_battery()
        if battery:
            return f"{battery.percent}"
        return "N/A (desktop)"

    def _get_calendar_today(self) -> str:
        """Placeholder — requires OAuth setup. Returns empty until configured."""
        return "Calendar not configured yet"

    def _get_unread_count(self) -> str:
        """Placeholder — requires OAuth setup. Returns 0 until configured."""
        return "0"

    def _get_memory_context(self, user_input: str) -> str:
        """Get top 3 semantically relevant memories."""
        if not self.episodic:
            return "No memories yet"
        try:
            memories = self.episodic.recall(user_input, n_results=3)
            if not memories:
                return "No relevant memories found"
            parts = []
            for m in memories:
                parts.append(f"- {m['content']}")
            return "\n".join(parts)
        except Exception as e:
            logger.debug("Memory recall failed: %s", e)
            return "Memory recall unavailable"

    def build_prompt(self, user_input: str, conversation_history: list[dict] = None) -> str:
        """Build the complete system prompt with live data injected."""
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)

        prompt = self.prompt_template
        replacements = {
            "[LIVE: DATETIME_IST]": now.strftime("%Y-%m-%d %H:%M:%S IST"),
            "[LIVE: DAY_OF_WEEK]": now.strftime("%A"),
            "[LIVE: ACTIVE_WINDOW]": self._get_active_window(),
            "[LIVE: BATTERY_PCT]": self._get_battery(),
            "[LIVE: CPU_PCT]": f"{psutil.cpu_percent(interval=0.1):.0f}",
            "[LIVE: RAM_PCT]": f"{psutil.virtual_memory().percent:.0f}",
            "[LIVE: CALENDAR_TODAY]": self._get_calendar_today(),
            "[LIVE: UNREAD_COUNT]": self._get_unread_count(),
            "[LIVE: MEMORY_CONTEXT]": self._get_memory_context(user_input),
        }
        for placeholder, value in replacements.items():
            prompt = prompt.replace(placeholder, value)

        return prompt

    def build_messages(self, user_input: str, conversation_history: list[dict] = None) -> tuple[str, list[dict]]:
        """Return (system_prompt, messages) ready for LLM."""
        system_prompt = self.build_prompt(user_input, conversation_history)
        messages = []
        if conversation_history:
            for msg in conversation_history[-10:]:  # Last 10 messages for context
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_input})
        return system_prompt, messages
