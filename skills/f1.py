"""
J — F1 Skills
Schedule, standings, and news via the free OpenF1 API + web search.
"""

import logging
from datetime import datetime, timezone, timedelta
import requests
from skills.loader import skill

logger = logging.getLogger("j.skills.f1")

OPENF1_BASE = "https://api.openf1.org/v1"
ERGAST_BASE = "https://ergast.com/api/f1"


@skill
def f1_schedule() -> str:
    """Get the F1 race schedule (upcoming sessions)."""
    try:
        now = datetime.now(timezone.utc)
        year = now.year

        # Try OpenF1 sessions endpoint
        resp = requests.get(f"{OPENF1_BASE}/sessions", params={
            "year": year,
            "date_start>": now.strftime("%Y-%m-%dT%H:%M:%S"),
        }, timeout=10)

        if resp.status_code == 200:
            sessions = resp.json()
            if sessions:
                # Group by meeting/GP
                lines = ["Upcoming F1 sessions:"]
                seen_meetings = set()
                for s in sessions[:10]:
                    meeting = s.get("meeting_name", "Unknown GP")
                    session_name = s.get("session_name", "")
                    start = s.get("date_start", "")

                    if meeting not in seen_meetings:
                        lines.append(f"\n  🏎️ {meeting}")
                        seen_meetings.add(meeting)

                    # Parse and format time to IST
                    if start:
                        try:
                            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                            ist = dt + timedelta(hours=5, minutes=30)
                            time_str = ist.strftime("%a %b %d, %I:%M %p IST")
                        except Exception:
                            time_str = start
                    else:
                        time_str = "TBD"

                    lines.append(f"    {session_name}: {time_str}")
                return "\n".join(lines)

        # Fallback: Ergast API
        resp = requests.get(f"{ERGAST_BASE}/current.json", timeout=10)
        if resp.status_code == 200:
            races = resp.json()["MRData"]["RaceTable"]["Races"]
            upcoming = [r for r in races if r["date"] >= now.strftime("%Y-%m-%d")]
            if upcoming:
                lines = ["Upcoming F1 races:"]
                for r in upcoming[:5]:
                    lines.append(f"  🏁 Round {r['round']}: {r['raceName']} — {r['date']}")
                    lines.append(f"     Circuit: {r['Circuit']['circuitName']}")
                return "\n".join(lines)

        return "Couldn't fetch F1 schedule right now."

    except Exception as e:
        logger.error("F1 schedule fetch failed: %s", e)
        return f"F1 schedule unavailable: {e}"


@skill
def f1_standings(type: str = "drivers") -> str:
    """Get current F1 standings (drivers or constructors)."""
    try:
        if type.lower() in ("drivers", "driver", "wdc"):
            resp = requests.get(f"{ERGAST_BASE}/current/driverStandings.json", timeout=10)
            if resp.status_code == 200:
                data = resp.json()["MRData"]["StandingsTable"]["StandingsLists"]
                if data:
                    standings = data[0]["DriverStandings"]
                    lines = [f"🏆 WDC Standings {data[0]['season']}:"]
                    for s in standings[:10]:
                        driver = s["Driver"]
                        name = f"{driver['givenName']} {driver['familyName']}"
                        team = s["Constructors"][0]["name"] if s["Constructors"] else ""
                        lines.append(f"  P{s['position']}: {name} ({team}) — {s['points']} pts")
                    return "\n".join(lines)

        elif type.lower() in ("constructors", "constructor", "wcc", "teams"):
            resp = requests.get(f"{ERGAST_BASE}/current/constructorStandings.json", timeout=10)
            if resp.status_code == 200:
                data = resp.json()["MRData"]["StandingsTable"]["StandingsLists"]
                if data:
                    standings = data[0]["ConstructorStandings"]
                    lines = [f"🏆 WCC Standings {data[0]['season']}:"]
                    for s in standings:
                        lines.append(f"  P{s['position']}: {s['Constructor']['name']} — {s['points']} pts")
                    return "\n".join(lines)

        return "Standings aren't available right now."

    except Exception as e:
        logger.error("F1 standings fetch failed: %s", e)
        return f"Standings unavailable: {e}"


@skill
def f1_news() -> str:
    """Get latest F1 news via web search."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.news("Formula 1 latest news", max_results=5))

        if not results:
            return "No F1 news found right now."

        lines = ["Latest F1 news:"]
        for r in results:
            lines.append(f"  📰 {r['title']}")
            lines.append(f"     {r.get('body', '')[:120]}")
            lines.append(f"     {r.get('url', '')}")
        return "\n".join(lines)
    except Exception as e:
        logger.error("F1 news fetch failed: %s", e)
        return f"F1 news unavailable: {e}"
