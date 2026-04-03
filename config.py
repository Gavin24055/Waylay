"""
Waylay — Configuration Module
Loads environment variables and defines all paths/constants.

Updated for Upgrades 1-5:
  - Removed OPENWAKEWORD_MODEL (wake word eliminated)
  - Added INTENT_FILTER_MODEL (llama3.2:3b for COMMAND/NOISE classification)
  - Added VOICE_NAME / VOICE_RATE / VOICE_PITCH for edge-tts
  - Removed WAKE_CHIME_ENABLED (no chime in always-on mode)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = DATA_DIR / "chroma"
DB_PATH = DATA_DIR / "j.db"
AUDIT_LOG = DATA_DIR / "j_audit.log"
SCHEMA_PATH = BASE_DIR / "memory" / "schema.sql"
SYSTEM_PROMPT_PATH = BASE_DIR / "system_prompt.txt"

# Ensure data directories exist
DATA_DIR.mkdir(exist_ok=True)
CHROMA_DIR.mkdir(exist_ok=True)

# ── Load .env ────────────────────────────────────────────────────────────────
load_dotenv(BASE_DIR / ".env")

# ── API Keys ─────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
GOOGLE_CREDENTIALS_PATH = os.getenv(
    "GOOGLE_CREDENTIALS_PATH", str(BASE_DIR / "credentials.json")
)
MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID", "")
MICROSOFT_TENANT_ID = os.getenv("MICROSOFT_TENANT_ID", "common")

# ── LLM Config ───────────────────────────────────────────────────────────────
# Ollama is PRIMARY (local, unlimited, private). Groq is fallback only.
OLLAMA_PRIMARY = True
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Intent filter — tiny model, classifies COMMAND vs NOISE (<500ms)
INTENT_FILTER_MODEL = os.getenv("INTENT_FILTER_MODEL", "llama3.2:3b")

# ── Voice Config — Upgrade 1 (VAD always-on) ─────────────────────────────────
VAD_AGGRESSIVENESS = 2         # 0-3, higher = more aggressive silence detection
VAD_SILENCE_FRAMES = 30        # ~0.9s of silence to stop recording
SAMPLE_RATE = 16000
FRAME_DURATION_MS = 30         # 30ms frames for webrtcvad
CONVERSATION_TIMEOUT = 15      # seconds of silence before exiting conversation mode
# Wake chime is retained for optional use (e.g., error tones), but disabled by default
WAKE_CHIME_ENABLED = False     # No chime in always-on mode
WAKE_CHIME_FREQUENCY = 880     # Hz (used by error / status tones)
WAKE_CHIME_DURATION = 0.15     # seconds

# ── Voice Config — Upgrade 2 (edge-tts) ──────────────────────────────────────
# Primary: en-US-AriaNeural — warm, natural, casual AI assistant voice
# Alternatives (uncomment to switch):
#   en-US-JennyNeural    — casual, friendly
#   en-GB-SoniaNeural    — British female, more formal
#   en-US-AnaNeural      — young, energetic
VOICE_NAME = os.getenv("VOICE_NAME", "en-US-AriaNeural")
VOICE_RATE = os.getenv("VOICE_RATE", "+5%")    # Slightly faster = more natural
VOICE_PITCH = os.getenv("VOICE_PITCH", "-5Hz") # Slightly lower = warmer

# Piper fallback — local offline TTS
PIPER_MODEL_PATH = os.getenv(
    "PIPER_MODEL_PATH", str(BASE_DIR / "models" / "en_US-lessac-medium.onnx")
)

# ── User Config ───────────────────────────────────────────────────────────────
USER_NAME = os.getenv("USER_NAME", "Gavin")
USER_LOCATION = os.getenv("USER_LOCATION", "Bengaluru")
PHONE_SERIAL = os.getenv("PHONE_SERIAL", "")
TIMEZONE = "Asia/Kolkata"

# ── Proactive Thresholds ──────────────────────────────────────────────────────
BATTERY_LOW_PCT = 20
CPU_HIGH_PCT = 88
CPU_HIGH_DURATION_S = 180         # 3 minutes
WATER_REMINDER_HOUR = 14          # 2:30 PM check
APP_FOCUS_LIMIT_MIN = 120         # 2 hours in one app
EMAIL_POLL_INTERVAL_S = 300       # 5 minutes

# ── Groq Rate Limiting (fallback only) ───────────────────────────────────────
GROQ_DAILY_LIMIT = 14400          # free tier: 14,400 req/day
GROQ_RPM_LIMIT = 30               # 30 req/min

# ── Safe Shell Commands ───────────────────────────────────────────────────────
SAFE_SHELL_COMMANDS = {
    "ls", "pwd", "whoami", "date", "cal", "uptime", "df",
    "free", "top", "htop", "ps", "cat", "head", "tail",
    "wc", "grep", "find", "which", "echo", "ping",
    "ifconfig", "ip", "hostname", "uname", "lsblk",
    "nvidia-smi", "ollama", "git", "dir", "ipconfig",  # dir/ipconfig for Windows
}
