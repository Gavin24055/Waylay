"""
J — Health Skills
Sleep, mood, water, exercise logging and summaries.
"""

import logging
from skills.loader import skill

logger = logging.getLogger("j.skills.health")


def _get_db():
    from memory.structured import StructuredMemory
    return StructuredMemory()


@skill
def log_sleep(hours: float, quality: str = None, notes: str = None) -> str:
    """Log sleep hours and quality."""
    db = _get_db()
    db.log_sleep(hours, quality, notes)
    logger.info("Logged sleep: %.1f hours, quality=%s", hours, quality)

    verdict = ""
    if hours < 6:
        verdict = " That's pretty low, bro."
    elif hours >= 8:
        verdict = " Nice, solid rest."

    return f"Logged {hours:.1f} hours of sleep ({quality or 'unrated'}).{verdict}"


@skill
def log_mood(mood: str, notes: str = None) -> str:
    """Log current mood."""
    sentiment_map = {
        "great": 1.0, "good": 0.7, "okay": 0.4, "ok": 0.4,
        "meh": 0.2, "bad": -0.3, "terrible": -0.7, "awful": -1.0,
        "stressed": -0.4, "anxious": -0.5, "happy": 0.8, "excited": 0.9,
        "sad": -0.6, "angry": -0.7, "tired": -0.2, "energetic": 0.8,
    }
    score = sentiment_map.get(mood.lower(), 0.0)
    db = _get_db()
    db.log_mood(mood, score, notes)
    logger.info("Logged mood: %s (score=%.1f)", mood, score)
    return f"Mood logged: {mood}"


@skill
def log_water(glasses: int = 1) -> str:
    """Log water intake (glasses)."""
    db = _get_db()
    db.log_water(glasses)
    total = db.get_water_today()
    logger.info("Logged water: +%d glass(es), total today=%d", glasses, total)

    msg = f"Logged {glasses} glass(es). Total today: {total}"
    if total >= 8:
        msg += " — solid hydration 💧"
    return msg


@skill
def log_exercise(exercise_type: str, duration_min: int, notes: str = None) -> str:
    """Log exercise activity."""
    db = _get_db()
    db.log_exercise(exercise_type, duration_min, notes)
    logger.info("Logged exercise: %s for %d min", exercise_type, duration_min)
    return f"Logged {duration_min} min of {exercise_type}. Keep it up 💪"


@skill
def health_summary(days: int = 7) -> str:
    """Get health summary for the past N days."""
    db = _get_db()
    summary = db.health_summary(days)

    parts = [f"Health summary (last {days} days):"]
    parts.append(f"  Sleep: avg {summary['avg_sleep_hours']:.1f} hrs/night")
    parts.append(f"  Water: avg {summary['avg_water_glasses']:.1f} glasses/day")
    parts.append(f"  Exercise: {summary['exercise_sessions']} sessions, {summary['exercise_total_min']} min total")

    if summary["avg_sleep_hours"] < 7:
        parts.append("  ⚠️ Sleep is below 7 hours — consider winding down earlier")
    if summary["avg_water_glasses"] < 6:
        parts.append("  ⚠️ Water intake could be better")

    return "\n".join(parts)
