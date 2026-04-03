#!/usr/bin/env python3
"""
Waylay — Personal AI Life OS
Main entry point and orchestrator.

Owner: Gavin Payankan | v2.0

Upgrades in this version:
  1. Always-listening VAD (no wake word)
  2. edge-tts female voice (en-US-AriaNeural)
  3. Streaming LLM → sentence-by-sentence TTS (low latency)
  4. Auto-start via LaunchAgent (see waylay_start.sh / plist)
  5. Interrupt detection while speaking

Usage:
    python3 main.py                     # Normal voice mode (always-on)
    python3 main.py --test              # Test with default "what time is it"
    python3 main.py --test "your text"  # Test with custom text
"""

import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"  # Silence HuggingFace tokenizer warnings

import logging
import queue
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

# ── Bootstrap ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    AUDIT_LOG, DATA_DIR, CONVERSATION_TIMEOUT,
    INTENT_FILTER_MODEL, OLLAMA_HOST, PIPER_MODEL_PATH,
    CHROMA_DIR, DB_PATH, GROQ_API_KEY,
    GOOGLE_CREDENTIALS_PATH, MICROSOFT_CLIENT_ID,
    VOICE_NAME,
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(AUDIT_LOG),
    ],
)
logger = logging.getLogger("j.main")


# ── Mic Permission Check ──────────────────────────────────────────────────────

def _check_mic_permission():
    """Check macOS microphone permission before starting voice pipeline."""
    try:
        result = subprocess.run(
            [sys.executable, "-c",
             "import pyaudio; p = pyaudio.PyAudio(); p.terminate()"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            logger.error("Microphone permission check failed: %s", result.stderr[:200])
            print("\n" + "=" * 60)
            print("  ⚠️  Microphone permission denied!")
            print("  Go to: System Preferences → Privacy & Security → Microphone")
            print("  Enable access for Terminal (or your IDE)")
            print("=" * 60 + "\n")
            sys.exit(1)
        logger.info("Microphone permission: OK")
    except subprocess.TimeoutExpired:
        logger.warning("Mic permission check timed out — proceeding anyway")
    except Exception as e:
        logger.warning("Mic permission check error: %s — proceeding anyway", e)


# ── Health Check ──────────────────────────────────────────────────────────────

def run_health_check():
    """Run a startup health check and print a status table."""
    import requests as _req

    rows = []

    # Ollama primary LLM
    try:
        r = _req.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            note = ", ".join(models[:3]) if models else "running (no models pulled)"
            rows.append(("Ollama (primary LLM)", "✅", note))
        else:
            rows.append(("Ollama (primary LLM)", "❌", "run: ollama serve"))
    except Exception:
        rows.append(("Ollama (primary LLM)", "❌", "run: ollama serve"))

    # Intent filter model (llama3.2:3b)
    try:
        r2 = _req.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        if r2.status_code == 200:
            models_list = [m["name"] for m in r2.json().get("models", [])]
            if any(INTENT_FILTER_MODEL in m for m in models_list):
                rows.append(("Intent filter model", "✅", INTENT_FILTER_MODEL))
            else:
                rows.append(("Intent filter model", "⚠️ ", f"run: ollama pull {INTENT_FILTER_MODEL}"))
        else:
            rows.append(("Intent filter model", "❌", f"ollama not running"))
    except Exception:
        rows.append(("Intent filter model", "❌", "ollama not running"))

    # Groq fallback
    if GROQ_API_KEY:
        rows.append(("Groq (fallback LLM)", "✅", "API key set"))
    else:
        rows.append(("Groq (fallback LLM)", "⚠️ ", "GROQ_API_KEY not set"))

    # edge-tts (primary voice)
    try:
        import edge_tts  # noqa: F401
        rows.append(("edge-tts (voice)", "✅", VOICE_NAME))
    except ImportError:
        rows.append(("edge-tts (voice)", "❌", "pip install edge-tts"))

    # Piper TTS (fallback)
    if Path(PIPER_MODEL_PATH).exists():
        rows.append(("Piper TTS (fallback)", "✅", Path(PIPER_MODEL_PATH).name))
    else:
        rows.append(("Piper TTS (fallback)", "⚠️ ", f"model not found: {PIPER_MODEL_PATH}"))

    # Microphone
    try:
        import pyaudio
        pa = pyaudio.PyAudio()
        count = pa.get_device_count()
        pa.terminate()
        if count > 0:
            rows.append(("Microphone", "✅", f"{count} audio device(s) found"))
        else:
            rows.append(("Microphone", "❌", "no audio devices"))
    except Exception as e:
        rows.append(("Microphone", "❌", str(e)[:50]))

    # Google OAuth
    cred_path = Path(GOOGLE_CREDENTIALS_PATH)
    token_path = DATA_DIR / "token.json"
    if cred_path.exists() and token_path.exists():
        rows.append(("Google OAuth (Gmail)", "✅", "credentials + token found"))
    elif cred_path.exists():
        rows.append(("Google OAuth (Gmail)", "⚠️ ", "credentials ok, token.json missing"))
    else:
        rows.append(("Google OAuth (Gmail)", "❌", "credentials.json missing"))

    # Microsoft Graph (Teams)
    ms_token = DATA_DIR / "microsoft_token.json"
    if MICROSOFT_CLIENT_ID and ms_token.exists():
        rows.append(("Microsoft Graph (Teams)", "✅", "authenticated"))
    elif MICROSOFT_CLIENT_ID:
        rows.append(("Microsoft Graph (Teams)", "⚠️ ", "run setup_microsoft_auth()"))
    else:
        rows.append(("Microsoft Graph (Teams)", "❌", "MICROSOFT_CLIENT_ID not set"))

    # Phone ADB
    try:
        r3 = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=3)
        connected = [l for l in r3.stdout.splitlines() if "\tdevice" in l]
        if connected:
            rows.append(("Phone ADB", "✅", connected[0].split()[0]))
        else:
            rows.append(("Phone ADB", "⚠️ ", "no device connected"))
    except Exception:
        rows.append(("Phone ADB", "⚠️ ", "adb not installed"))

    # SQLite DB
    if DB_PATH.exists():
        rows.append(("SQLite DB", "✅", DB_PATH.name))
    else:
        rows.append(("SQLite DB", "⚠️ ", "will be created on first run"))

    # ChromaDB memory
    if CHROMA_DIR.exists():
        rows.append(("ChromaDB memory", "✅", str(CHROMA_DIR.name) + "/"))
    else:
        rows.append(("ChromaDB memory", "⚠️ ", "will be created on first use"))

    # Print table
    w_comp = max(len(r[0]) for r in rows)
    w_note = max(len(r[2]) for r in rows)
    divider = "+" + "-" * (w_comp + 2) + "+--------+" + "-" * (w_note + 2) + "+"

    print()
    print(divider)
    print(f"| {'Component':<{w_comp}} | Status | {'Note':<{w_note}} |")
    print(divider.replace("-", "="))
    for comp, status, note in rows:
        print(f"| {comp:<{w_comp}} | {status:<6} | {note:<{w_note}} |")
    print(divider)
    print()


# ── Main Orchestrator ─────────────────────────────────────────────────────────

class Waylay:
    """The main Waylay orchestrator — ties all subsystems together."""

    def __init__(self, skip_voice: bool = False):
        logger.info("═" * 60)
        logger.info("  Waylay — Personal AI Life Operating System v2.0")
        logger.info("  Starting up...")
        logger.info("═" * 60)

        self.session_id = str(uuid.uuid4())[:8]
        self._shutdown = threading.Event()
        self._interaction_lock = threading.Lock()

        # ── Init Memory ────────────────────────────────────────────────────
        logger.info("Initialising memory systems...")
        from memory.structured import StructuredMemory
        from memory.episodic import EpisodicMemory
        self.structured = StructuredMemory()
        self.episodic = EpisodicMemory()

        # ── Init Brain ─────────────────────────────────────────────────────
        logger.info("Initialising brain...")
        from brain.llm import LLMChain
        from brain.context import ContextBuilder
        from brain.dispatcher import Dispatcher
        self.llm = LLMChain()
        self.context = ContextBuilder(
            episodic_memory=self.episodic,
            structured_memory=self.structured,
        )

        # ── Init Voice ─────────────────────────────────────────────────────
        logger.info("Initialising voice pipeline...")
        from voice.tts import TextToSpeech
        from voice.stt import SpeechToText
        self.tts = TextToSpeech()
        self.stt = SpeechToText()

        if not skip_voice:
            from voice.recorder import VoiceRecorder
            # Always-on VAD recorder — calls _on_utterance when COMMAND detected
            self.recorder = VoiceRecorder(on_utterance=self._on_utterance)
        else:
            self.recorder = None

        # ── Init Skills ────────────────────────────────────────────────────
        logger.info("Discovering skills...")
        from skills.loader import get_registry
        self.skills_registry = get_registry()
        self.dispatcher = Dispatcher(self.skills_registry, self.tts)
        logger.info("Loaded %d skills", len(self.skills_registry))

        # ── Init Proactive Systems ─────────────────────────────────────────
        logger.info("Initialising proactive systems...")
        from proactive.scheduler import ProactiveScheduler
        from proactive.monitors import BackgroundMonitors
        self.scheduler = ProactiveScheduler(
            tts=self.tts,
            llm_chain=self.llm,
            context_builder=self.context,
            structured_memory=self.structured,
            episodic_memory=self.episodic,
        )
        self.monitors = BackgroundMonitors(tts=self.tts)

        # ── Init Tray ──────────────────────────────────────────────────────
        from ui.tray import TrayIcon
        self.tray = TrayIcon(
            on_quit=self.shutdown,
            on_status=self._tray_status,
            on_briefing=self._tray_briefing,
        )

        # Conversation history for multi-turn context
        self._conversation_history = []

    # ── Always-On VAD Callback ─────────────────────────────────────────────────

    def _on_utterance(self, text: str):
        """
        Called by VoiceRecorder when a COMMAND utterance is transcribed + classified.
        Runs in the recorder's background thread — dispatch to a new thread.
        The recorder auto-resumes listening after this returns.
        """
        threading.Thread(
            target=self._handle_command,
            args=(text,),
            daemon=True,
            name="cmd-handler",
        ).start()

    def _handle_command(self, text: str):
        """
        Process a validated command text → streaming LLM → sentence TTS.
        Runs in a background thread; acquires _interaction_lock so only
        one command is processed at a time.
        """
        with self._interaction_lock:
            try:
                # Stop any ongoing TTS first
                self.tts.stop()

                logger.info("Handling command: %s", text)
                self._process_and_speak_streaming(text)

            except Exception as e:
                logger.error("Command handler error: %s", e, exc_info=True)
                try:
                    self.tts.play_error_tone()
                except Exception:
                    pass

    def _process_and_speak_streaming(self, text: str):
        """
        Upgrade 3 — Streaming LLM + TTS pipeline:
        1. Save user utterance to memory
        2. Build context messages
        3. Stream LLM response sentence by sentence
        4. Speak each sentence immediately as it arrives
        5. Accumulate full response for skill dispatch

        This reduces TTFS (time-to-first-sound) from 5-8s to ~1.5s.
        """
        # Save to memory
        self.structured.save_conversation("user", text, self.session_id)
        self._conversation_history.append({"role": "user", "content": text})

        # Build context
        system_prompt, messages = self.context.build_messages(
            text, self._conversation_history
        )

        # Determine mode: if this looks like it needs a skill (tool call),
        # we need the full JSON response → non-streaming chat.
        # Otherwise, stream for natural conversation.
        #
        # Heuristic: if dispatcher has a matching skill for the text,
        # use non-streaming to get clean JSON. Otherwise stream.
        #
        # For now: always attempt streaming FIRST for the spoken response,
        # then call dispatcher with the full accumulated text.

        full_response_parts = []
        sentence_queue = queue.Queue()
        done_event = threading.Event()

        def _stream_to_queue():
            """Generate sentences in background and push to queue."""
            try:
                for sentence in self.llm.chat_stream(messages, system_prompt):
                    full_response_parts.append(sentence)
                    sentence_queue.put(sentence)
            except Exception as e:
                logger.error("Streaming LLM error: %s", e)
            finally:
                done_event.set()
                sentence_queue.put(None)  # Sentinel

        # Start streaming in background
        stream_thread = threading.Thread(
            target=_stream_to_queue,
            daemon=True,
            name="llm-stream",
        )
        stream_thread.start()

        # Speak sentences as they arrive
        spoken_sentences = []
        from voice.tts import _interrupt_requested

        while True:
            try:
                sentence = sentence_queue.get(timeout=30)
            except queue.Empty:
                logger.warning("Sentence queue timeout — stopping")
                break

            if sentence is None:
                break  # Stream complete

            if not sentence.strip():
                continue

            # Check interrupt flag — user spoke while we were talking
            import voice.tts as _tts_mod
            if _tts_mod._interrupt_requested:
                logger.info("User interrupted — stopping TTS chain early")
                break

            spoken_sentences.append(sentence)
            logger.info("Speaking sentence: %s", sentence[:80])
            self.tts.speak(sentence)  # This blocks until sentence is spoken
            self.recorder.resume()    # Keep listener live between sentences

        # Wait for full response to be generated (for dispatch)
        done_event.wait(timeout=60)
        full_response = " ".join(full_response_parts)

        # If the full response looks like JSON (tool call), dispatch it
        if full_response.strip().startswith("{"):
            logger.info("Detected JSON tool call — dispatching to skills")
            speak_text = self.dispatcher.dispatch(full_response)
            # Speak any additional text the dispatcher returns
            if speak_text and speak_text not in " ".join(spoken_sentences):
                self.tts.speak(speak_text)
            final_response = speak_text
        else:
            final_response = " ".join(spoken_sentences) or full_response

        # Save assistant response to memory
        self.structured.save_conversation("assistant", final_response, self.session_id)
        self._conversation_history.append(
            {"role": "assistant", "content": final_response}
        )

        # Episodic memory
        self.episodic.save(
            content=f"User: {text}\nJ: {final_response}",
            tags=["conversation"],
        )

        # Keep conversation history manageable
        if len(self._conversation_history) > 20:
            self._conversation_history = self._conversation_history[-20:]

        logger.info("Command complete — back to listening")

    # ── Synchronous process_text (test mode + tray) ────────────────────────────

    def process_text(self, text: str) -> str:
        """
        Process a text input through the full brain pipeline.
        Non-streaming — used by --test mode and tray menu.
        Returns the text Waylay would speak.
        """
        logger.info("Processing input: %s", text)

        self.structured.save_conversation("user", text, self.session_id)
        self._conversation_history.append({"role": "user", "content": text})

        system_prompt, messages = self.context.build_messages(
            text, self._conversation_history
        )
        response = self.llm.chat(messages, system_prompt, force_json=True)
        logger.info("LLM response: %s", response[:200])

        speak_text = self.dispatcher.dispatch(response)

        self.structured.save_conversation("assistant", speak_text, self.session_id)
        self._conversation_history.append({"role": "assistant", "content": speak_text})

        self.episodic.save(
            content=f"User: {text}\nJ: {speak_text}",
            tags=["conversation"],
        )

        if len(self._conversation_history) > 20:
            self._conversation_history = self._conversation_history[-20:]

        return speak_text

    # ── Tray Callbacks ─────────────────────────────────────────────────────────

    def _tray_status(self):
        from skills.info import get_system_stats
        stats = get_system_stats()
        self.tts.speak(stats)

    def _tray_briefing(self):
        from proactive.briefing import generate_morning_briefing
        briefing = generate_morning_briefing(self.structured)
        self.tts.speak(briefing)

    # ── Run / Shutdown ─────────────────────────────────────────────────────────

    def run(self):
        """Start all systems and run until shutdown (always-on)."""
        logger.info("Starting all systems...")

        # Start recorder (always-on VAD — injects STT reference)
        if self.recorder:
            self.recorder.start(stt=self.stt)

        self.scheduler.start()
        self.monitors.start()
        self.tray.start()

        # Startup greeting
        self.tts.speak("Waylay is online. What's up, Gavin?")

        logger.info("═" * 60)
        logger.info("  Waylay is running — always listening (no wake word needed).")
        logger.info("  Just speak naturally. Say 'stop' to interrupt a response.")
        logger.info("  Press Ctrl+C to shutdown.")
        logger.info("═" * 60)

        signal.signal(signal.SIGINT, lambda *_: self.shutdown())
        signal.signal(signal.SIGTERM, lambda *_: self.shutdown())

        while not self._shutdown.is_set():
            self._shutdown.wait(timeout=0.5)

    def shutdown(self):
        """Gracefully shut down all systems."""
        if self._shutdown.is_set():
            return

        logger.info("Shutting down Waylay...")

        try:
            self.tts.speak("Shutting down. Catch you later, Gavin.")
        except Exception:
            pass

        if self.recorder:
            self.recorder.stop()
        self.scheduler.stop()
        self.monitors.stop()
        self.tray.stop()

        logger.info("Waylay shutdown complete.")
        self._shutdown.set()


# ── Entry Point ────────────────────────────────────────────────────────────────

def main():
    # ── Test mode ────────────────────────────────────────────────────────────
    if "--test" in sys.argv:
        idx = sys.argv.index("--test")
        test_input = " ".join(sys.argv[idx + 1:]) or "what time is it"
        print(f"\n  Waylay — Test Mode: \"{test_input}\"\n")

        w = Waylay(skip_voice=True)
        result = w.process_text(test_input)
        print(f"\n  Result: {result}\n")
        sys.exit(0)

    # ── Normal always-on voice mode ───────────────────────────────────────────
    _check_mic_permission()
    run_health_check()
    w = Waylay()
    w.run()


if __name__ == "__main__":
    main()
