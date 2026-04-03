"""
J — System Tray (disabled)
pystray causes SIGILL on this macOS hardware.
Replaced with console-only status output.
"""

import logging

logger = logging.getLogger("j.ui.tray")


class TrayIcon:
    """Console-mode fallback — pystray disabled due to macOS SIGILL crash."""

    def __init__(self, on_quit=None, on_status=None, on_briefing=None):
        self.on_quit = on_quit
        self.on_status = on_status
        self.on_briefing = on_briefing

    def start(self):
        logger.info("Tray disabled (macOS SIGILL) — running in console mode")

    def stop(self):
        pass
