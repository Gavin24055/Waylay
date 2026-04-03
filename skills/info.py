"""
Waylay — Information Skills
Web search, page fetch, weather, time, system stats.
"""

import logging
from datetime import datetime
import pytz
import psutil
import requests
from config import OPENWEATHER_API_KEY, USER_LOCATION, TIMEZONE
from skills.loader import skill

logger = logging.getLogger("j.skills.info")


@skill
def web_search(query: str) -> str:
    """Search the web using DuckDuckGo and return top results summary."""
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                results.append(r)
        if not results:
            return "No results found."

        output = []
        for r in results:
            title = r.get("title", "")
            body = r.get("body", r.get("snippet", ""))[:150]
            href = r.get("href", r.get("url", ""))
            output.append(f"• {title}\n  {body}\n  {href}")
        return "\n\n".join(output)
    except Exception as e:
        logger.error("Web search failed: %s", e)
        # Try plain requests fallback
        try:
            import urllib.parse
            fallback_url = f"https://duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            return f"Search unavailable — try: {fallback_url}"
        except Exception:
            return f"Search failed: {e}"


@skill
def web_fetch(url: str) -> str:
    """Fetch and return the text content of a URL."""
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "J-AI/1.0"})
        resp.raise_for_status()
        # Return first 3000 chars of text content
        from html.parser import HTMLParser

        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text = []
                self._skip = False

            def handle_starttag(self, tag, attrs):
                if tag in ("script", "style", "noscript"):
                    self._skip = True

            def handle_endtag(self, tag):
                if tag in ("script", "style", "noscript"):
                    self._skip = False

            def handle_data(self, data):
                if not self._skip:
                    stripped = data.strip()
                    if stripped:
                        self.text.append(stripped)

        extractor = TextExtractor()
        extractor.feed(resp.text)
        text = " ".join(extractor.text)
        return text[:3000]
    except Exception as e:
        logger.error("Web fetch failed: %s", e)
        return f"Fetch failed: {e}"


@skill
def get_weather(city: str = None) -> str:
    """Get current weather for a city (default: Bengaluru)."""
    city = city or USER_LOCATION
    if not OPENWEATHER_API_KEY:
        return "Weather API key not configured. Add OPENWEATHER_API_KEY to .env"

    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        resp = requests.get(url, params={
            "q": city,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        desc = data["weather"][0]["description"].capitalize()
        temp = data["main"]["temp"]
        feels = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        wind = data["wind"]["speed"]

        return (
            f"{city}: {desc}, {temp:.0f}°C (feels like {feels:.0f}°C), "
            f"humidity {humidity}%, wind {wind:.1f} m/s"
        )
    except Exception as e:
        logger.error("Weather fetch failed: %s", e)
        return f"Weather unavailable: {e}"


@skill
def get_time() -> str:
    """Get the current time in IST."""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    return now.strftime("%A, %B %d, %Y — %I:%M %p IST")


@skill
def get_system_stats() -> str:
    """Get current system resource usage."""
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    battery = psutil.sensors_battery()

    parts = [
        f"CPU: {cpu:.1f}%",
        f"RAM: {ram.percent:.1f}% ({ram.used / (1024**3):.1f}/{ram.total / (1024**3):.1f} GB)",
        f"Disk: {disk.percent:.1f}% ({disk.used / (1024**3):.0f}/{disk.total / (1024**3):.0f} GB)",
    ]

    if battery:
        status = "charging" if battery.power_plugged else "on battery"
        parts.append(f"Battery: {battery.percent}% ({status})")
    else:
        parts.append("Battery: N/A (desktop)")

    return " | ".join(parts)
