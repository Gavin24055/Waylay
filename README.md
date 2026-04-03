# Waylay — Personal AI Life Operating System

> Voice-activated, always-on AI life OS. No wake word. Just talk.
> Built for one person. Free tier only.

```
═══════════════════════════════════════════════════════════════════
 WAYLAY — PERSONAL AI LIFE OPERATING SYSTEM
 Owner: Gavin Payankan | Version: 2.0 | Built: 2026
 Location: Bengaluru, India
═══════════════════════════════════════════════════════════════════
```

## What's New in v2.0

| Upgrade | What changed |
|---------|-------------|
| **1. Always-Listening VAD** | No wake word. Mic is always on. webrtcvad detects speech, llama3.2:3b filters COMMAND vs NOISE. |
| **2. Female Neural Voice** | edge-tts with `en-US-AriaNeural` — near-human, warm, casual. Piper kept as offline fallback. |
| **3. Streaming LLM → TTS** | First sentence spoken in ~1.5s instead of 5-8s. Ollama streams tokens → splits on sentence boundaries → speaks immediately. |
| **4. Auto-Start** | macOS LaunchAgent + Windows Task Scheduler. No terminal needed. |
| **5. Interrupt Detection** | Say anything while Waylay is speaking → audio stops immediately. |

## Voice Pipeline

```
MIC → VAD detects speech → record until silence
    → Google STT → llama3.2:3b (COMMAND or NOISE?)
    → COMMAND → Ollama qwen2.5:7b streaming
    → sentence 1 → edge-tts → speakers
    → sentence 2 → edge-tts → speakers  (overlap with LLM gen)
    → back to listening
```

## Architecture

```
  ┌─────────────────────────────────────────────────────────┐
  │                      main.py                            │
  │          (orchestrator — ties everything)                │
  ├────────────┬────────────┬────────────┬─────────────────┤
  │   voice/   │   brain/   │  skills/   │   proactive/    │
  │            │            │            │                 │
  │ recorder   │ llm.py     │ loader.py  │ scheduler.py    │
  │ (VAD+VAD)  │ (streaming)│ pc.py      │ monitors.py     │
  │ stt.py     │ context.py │ info.py    │ briefing.py     │
  │ tts.py     │ dispatcher │ comms.py   │                 │
  │ (edge-tts) │            │ phone.py   │   ui/           │
  │            │            │ health.py  │   tray.py       │
  │            │            │ finance.py │                 │
  │            │            │ ...60 more │   memory/       │
  ├────────────┴────────────┴────────────┴─────────────────┤
  │  LLM Chain: Ollama qwen2.5:7b (primary, local)         │
  │             Intent filter: llama3.2:3b (COMMAND/NOISE) │
  │             Groq llama-3.3-70b (cloud fallback)        │
  │  Memory: ChromaDB (vector) + SQLite (structured)       │
  └─────────────────────────────────────────────────────────┘
```

---

## Setup — macOS

### 1. Prerequisites

```bash
brew install portaudio tesseract
```

### 2. Clone & Virtual Environment

```bash
git clone https://github.com/Gavin24055/Waylay.git jarvis
cd jarvis
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Pull Ollama Models

```bash
ollama serve &          # Start Ollama in background
ollama pull qwen2.5:7b  # Main LLM (~4.7 GB)
ollama pull llama3.2:3b # Intent filter (~2 GB)
```

### 4. Download Piper Voice Model (Offline Fallback)

```bash
mkdir -p models
curl -L -o models/en_US-lessac-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
curl -L -o models/en_US-lessac-medium.onnx.json \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
```

### 5. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 6. Run

```bash
source venv/bin/activate
python main.py
```

Waylay will say **"Waylay is online. What's up, Gavin?"** — just talk.

### 7. Auto-Start on Login (macOS)

```bash
# Make start script executable
chmod +x waylay_start.sh

# Register LaunchAgent (starts Waylay on login automatically)
cp com.waylay.assistant.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.waylay.assistant.plist
```

---

## Setup — Windows

See **[WINDOWS_SETUP.md](./WINDOWS_SETUP.md)** for the full step-by-step guide.

Quick version:
```cmd
git clone https://github.com/Gavin24055/Waylay.git jarvis
cd jarvis
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
ollama pull qwen2.5:7b
ollama pull llama3.2:3b
copy .env.example .env
python main.py --test "hello"
python main.py
```

---

## Test Mode (No Mic)

```bash
# macOS/Linux
python main.py --test "what time is it"
python main.py --test "take a screenshot"

# Windows
python main.py --test "what time is it"
```

---

## Adding a Skill

1. Create `skills/yourskill.py`
2. Use the `@skill` decorator
3. Add tool name to `system_prompt.txt` under `AVAILABLE TOOLS`
4. Restart — auto-discovered

```python
from skills.loader import skill

@skill
def recipe_search(query: str) -> str:
    """Search for a recipe."""
    return f"Found recipe for {query}"
```

---

## Changing the Voice

Edit `.env`:
```env
VOICE_NAME=en-US-JennyNeural   # or any edge-tts voice
VOICE_RATE=+10%                # faster
VOICE_PITCH=+0Hz               # default pitch
```

Available voices: run `edge-tts --list-voices` to see all options.

---

## Project Structure

```
jarvis/
├── main.py                  # Orchestrator (v2.0 — streaming + VAD)
├── config.py                # Config & env loading
├── system_prompt.txt        # Waylay's personality & knowledge
├── .env                     # API keys (gitignored)
├── .env.example             # Template
├── requirements.txt         # Python dependencies
├── waylay_start.sh          # macOS auto-start script
├── waylay_start.bat         # Windows auto-start script
├── com.waylay.assistant.plist  # macOS LaunchAgent
├── WINDOWS_SETUP.md         # Full Windows migration guide
├── voice/
│   ├── recorder.py          # Always-on VAD + intent filter
│   ├── tts.py               # edge-tts primary + Piper fallback + interrupt
│   └── stt.py               # Google STT + Groq Whisper fallback
├── brain/
│   ├── llm.py               # Streaming Ollama → Groq chain
│   ├── context.py           # Context builder
│   └── dispatcher.py        # Skill dispatcher
├── memory/
│   ├── structured.py        # SQLite
│   └── episodic.py          # ChromaDB vector memory
├── skills/                  # 60+ skill implementations
├── proactive/               # Scheduled jobs & monitors
├── ui/                      # System tray
└── data/                    # Runtime data (gitignored)
```

---

## License

Personal project. Not for redistribution.
