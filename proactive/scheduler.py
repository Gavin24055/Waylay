"""
J — Proactive Scheduler
APScheduler jobs: morning briefing, weekly wrap, water reminders, onboarding.
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("j.proactive.scheduler")


class ProactiveScheduler:
    """Manages all scheduled proactive actions for J."""

    def __init__(self, tts=None, llm_chain=None, context_builder=None,
                 structured_memory=None, episodic_memory=None):
        self.scheduler = BackgroundScheduler(daemon=True)
        self.tts = tts
        self.llm = llm_chain
        self.context = context_builder
        self.db = structured_memory
        self.episodic = episodic_memory

    def start(self):
        """Register and start all scheduled jobs."""

        # ── Morning Briefing: 8:15 AM, Mon-Fri ──────────────────
        self.scheduler.add_job(
            self._morning_briefing,
            CronTrigger(hour=8, minute=15, day_of_week="mon-fri"),
            id="morning_briefing",
            name="Morning Briefing",
            replace_existing=True,
        )

        # ── Sunday Weekly Wrap: 9:00 PM ─────────────────────────
        self.scheduler.add_job(
            self._weekly_wrap,
            CronTrigger(hour=21, minute=0, day_of_week="sun"),
            id="weekly_wrap",
            name="Sunday Weekly Wrap",
            replace_existing=True,
        )

        # ── Water Reminder: Every 2 hours from 10AM to 8PM ─────
        self.scheduler.add_job(
            self._water_reminder,
            CronTrigger(hour="10,12,14,16,18,20", minute=30),
            id="water_reminder",
            name="Water Reminder",
            replace_existing=True,
        )

        # ── Onboarding Question: 9:00 PM daily ─────────────────
        self.scheduler.add_job(
            self._onboarding_question,
            CronTrigger(hour=21, minute=0, day_of_week="mon-sat"),
            id="onboarding_question",
            name="Onboarding Question",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info("Proactive scheduler started with %d jobs", len(self.scheduler.get_jobs()))

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Proactive scheduler stopped")

    def _speak(self, text: str):
        """Speak text via TTS if available."""
        if self.tts:
            try:
                self.tts.speak(text)
            except Exception as e:
                logger.error("TTS failed in scheduled job: %s", e)
        logger.info("[Proactive] %s", text)

    def _morning_briefing(self):
        """Generate and speak the morning briefing."""
        try:
            from proactive.briefing import generate_morning_briefing
            briefing_text = generate_morning_briefing(self.db)
            self._speak(briefing_text)
        except Exception as e:
            logger.error("Morning briefing failed: %s", e)

    def _weekly_wrap(self):
        """Offer a weekly wrap-up on Sunday evenings."""
        self._speak("Hey Luttu, it's Sunday evening. Want me to run through a quick weekly wrap? Your tasks, health, spending — the works.")

    def _water_reminder(self):
        """Nudge about water intake if low."""
        try:
            if self.db:
                glasses = self.db.get_water_today()
                from datetime import datetime
                hour = datetime.now().hour
                expected = max(1, (hour - 8) // 2)  # rough expectation
                if glasses < expected:
                    self._speak(f"Hey, you've only had {glasses} glasses of water today. Grab one.")
        except Exception as e:
            logger.debug("Water reminder check failed: %s", e)

    def _onboarding_question(self):
        """Ask the next onboarding question naturally."""
        try:
            from proactive.onboarding import get_onboarding_prompt
            question = get_onboarding_prompt(self.db)
            if question:
                self._speak(question)
        except Exception as e:
            logger.debug("Onboarding question failed: %s", e)
