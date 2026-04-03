"""
J — Background Monitors
Threads that watch CPU, battery, email, and app focus time.
"""

import logging
import threading
import time
import psutil
from config import (
    BATTERY_LOW_PCT, CPU_HIGH_PCT, CPU_HIGH_DURATION_S,
    EMAIL_POLL_INTERVAL_S, APP_FOCUS_LIMIT_MIN,
)

logger = logging.getLogger("j.proactive.monitors")


class BackgroundMonitors:
    """Background monitoring threads for CPU, battery, email, app focus."""

    def __init__(self, tts=None):
        self.tts = tts
        self._running = False
        self._threads = []
        self._battery_warned = False
        self._cpu_high_start = None
        self._last_app = None
        self._app_start_time = None

    def start(self):
        self._running = True

        monitors = [
            ("cpu_battery_monitor", self._cpu_battery_loop),
            ("app_focus_monitor", self._app_focus_loop),
        ]

        for name, target in monitors:
            t = threading.Thread(target=target, daemon=True, name=name)
            t.start()
            self._threads.append(t)
            logger.info("Started monitor: %s", name)

    def stop(self):
        self._running = False
        for t in self._threads:
            t.join(timeout=2)
        logger.info("All monitors stopped")

    def _speak(self, text: str):
        if self.tts:
            try:
                self.tts.speak(text)
            except Exception:
                pass
        logger.info("[Monitor] %s", text)

    def _cpu_battery_loop(self):
        """Monitor CPU and battery every 30 seconds."""
        while self._running:
            try:
                # Battery check
                battery = psutil.sensors_battery()
                if battery and not battery.power_plugged:
                    if battery.percent <= BATTERY_LOW_PCT and not self._battery_warned:
                        self._speak(f"Battery's at {battery.percent}% — might want to plug in.")
                        self._battery_warned = True
                    elif battery.percent > BATTERY_LOW_PCT + 10:
                        self._battery_warned = False

                # CPU check
                cpu = psutil.cpu_percent(interval=1)
                if cpu > CPU_HIGH_PCT:
                    if self._cpu_high_start is None:
                        self._cpu_high_start = time.time()
                    elif time.time() - self._cpu_high_start > CPU_HIGH_DURATION_S:
                        self._speak(f"CPU has been above {CPU_HIGH_PCT}% for over 3 minutes. Something's working hard.")
                        self._cpu_high_start = None  # Reset to avoid spamming
                else:
                    self._cpu_high_start = None

            except Exception as e:
                logger.debug("Monitor error: %s", e)

            time.sleep(30)

    def _app_focus_loop(self):
        """Monitor if user has been in one app too long."""
        while self._running:
            try:
                import subprocess
                result = subprocess.run(
                    ["osascript", "-e",
                     'tell application "System Events" to get name of first application process whose frontmost is true'],
                    capture_output=True, text=True, timeout=3,
                )
                current_app = result.stdout.strip() if result.returncode == 0 else None

                if current_app:
                    if current_app != self._last_app:
                        self._last_app = current_app
                        self._app_start_time = time.time()
                    elif self._app_start_time:
                        elapsed_min = (time.time() - self._app_start_time) / 60
                        if elapsed_min >= APP_FOCUS_LIMIT_MIN:
                            self._speak(f"You've been in {current_app} for over {int(elapsed_min)} minutes. Take a quick break?")
                            self._app_start_time = time.time()  # Reset timer

            except Exception:
                pass

            time.sleep(60)
