"""
Waylay — Always-Listening VAD Recorder (Upgrade 1)

Replaces wake word with pure Voice Activity Detection.
- Mic is ALWAYS open, listening continuously in a background thread
- webrtcvad detects when speech starts → records until silence
- Sends to STT → intent filter (llama3.2:3b) classifies COMMAND vs NOISE
- Only dispatches if COMMAND; silently discards NOISE
- No chime, no wake word — like a person always in the room

Flow:
  MIC → VAD detects speech → record → STT → intent filter
      → COMMAND → callback → NOISE → discard → back to listening
"""

import logging
import threading
import time
import json
import requests

try:
    import webrtcvad
except ImportError:
    import webrtcvad_wheels as webrtcvad

from config import (
    SAMPLE_RATE, FRAME_DURATION_MS, VAD_AGGRESSIVENESS,
    VAD_SILENCE_FRAMES, OLLAMA_HOST, INTENT_FILTER_MODEL,
)

logger = logging.getLogger("j.voice.recorder")

# ── Intent Filter ────────────────────────────────────────────────────────────

INTENT_SYSTEM_PROMPT = (
    "You are a speech filter. Respond with only 'COMMAND' or 'NOISE'. "
    "Return COMMAND if this sounds like someone talking to an AI assistant. "
    "Return NOISE if it's background conversation, TV, random noise, or unclear audio. "
    "Input:"
)


def _classify_intent(text: str) -> str:
    """
    Use llama3.2:3b to classify transcription as COMMAND or NOISE.
    Returns 'COMMAND' or 'NOISE'. Fast (<500ms) on local Ollama.
    """
    # Quick word-count pre-filter — less than 3 words → NOISE
    words = text.strip().split()
    if len(words) < 3:
        logger.debug("Intent filter: too short (%d words) → NOISE", len(words))
        return "NOISE"

    try:
        payload = {
            "model": INTENT_FILTER_MODEL,
            "messages": [
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 5},
        }
        resp = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json=payload,
            timeout=5,
        )
        resp.raise_for_status()
        result = resp.json()["message"]["content"].strip().upper()
        # Normalise — sometimes model returns "COMMAND." or "NOISE."
        if "COMMAND" in result:
            logger.debug("Intent filter: COMMAND → '%s'", text[:60])
            return "COMMAND"
        else:
            logger.debug("Intent filter: NOISE → '%s'", text[:60])
            return "NOISE"
    except Exception as e:
        # If intent filter fails, default to COMMAND so we don't miss things
        logger.warning("Intent filter error (%s) — defaulting to COMMAND", e)
        return "COMMAND"


# ── VAD Recorder ─────────────────────────────────────────────────────────────

class VoiceRecorder:
    """
    Always-on VAD recorder.
    Runs a background thread that continuously monitors the mic.
    When speech is detected → records it → classifies it → calls on_utterance.
    """

    def __init__(self, on_utterance=None):
        """
        on_utterance(pcm_bytes: bytes) → called when a COMMAND utterance is ready.
        If None, use self.record() in synchronous mode instead.
        """
        self.vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
        self.sample_rate = SAMPLE_RATE
        self.frame_duration_ms = FRAME_DURATION_MS
        self.frame_size = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)  # samples/frame
        self.silence_limit = VAD_SILENCE_FRAMES
        self.on_utterance = on_utterance

        self._running = False
        self._paused = False
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially
        self._thread = None

        logger.info(
            "VoiceRecorder (always-on VAD) init — rate=%d, frame=%dms, silence=%d frames, filter=%s",
            SAMPLE_RATE, FRAME_DURATION_MS, VAD_SILENCE_FRAMES, INTENT_FILTER_MODEL,
        )

    # ── Public API ──────────────────────────────────────────────────────────

    def start(self, stt=None):
        """Start the background always-listening thread."""
        if self._running:
            return
        self._stt = stt  # SpeechToText instance — injected for always-on mode
        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop_wrapper,
            daemon=True,
            name="vad-listener",
        )
        self._thread.start()
        logger.info("Always-listening VAD started")

    def stop(self):
        """Stop the background listener."""
        self._running = False
        self._pause_event.set()
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("VAD listener stopped")

    def pause(self):
        """Pause mic capture (e.g., while TTS is speaking)."""
        self._paused = True
        self._pause_event.clear()
        logger.debug("VAD listener paused")

    def resume(self):
        """Resume mic capture after TTS finishes."""
        self._paused = False
        self._pause_event.set()
        logger.debug("VAD listener resumed")

    def record(self) -> bytes:
        """
        SYNCHRONOUS mode — used by _do_single_interaction() after VAD triggers.
        Opens mic, records until silence, returns raw PCM.
        """
        import pyaudio

        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.frame_size,
        )
        logger.info("Recording (sync VAD)...")
        frames = []
        silence_count = 0
        has_speech = False

        try:
            while True:
                audio_data = stream.read(self.frame_size, exception_on_overflow=False)
                is_speech = self.vad.is_speech(audio_data, self.sample_rate)

                if is_speech:
                    has_speech = True
                    silence_count = 0
                    frames.append(audio_data)
                elif has_speech:
                    frames.append(audio_data)
                    silence_count += 1
                    if silence_count >= self.silence_limit:
                        break
                else:
                    # Pre-speech — keep a small rolling buffer so we don't clip onset
                    frames.append(audio_data)
                    if len(frames) > 10:
                        frames.pop(0)

                # Safety: max 30s
                if len(frames) > (30 * 1000 // self.frame_duration_ms):
                    logger.warning("Max recording length (30s) reached")
                    break

        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()

        return b"".join(frames)

    # ── Background Loop ─────────────────────────────────────────────────────

    def _listen_loop_wrapper(self):
        """Auto-restart the listen loop on any error."""
        while self._running:
            try:
                self._listen_loop()
            except Exception as e:
                if self._running:
                    logger.error("VAD listener crashed: %s — restarting in 2s", e)
                    time.sleep(2)
                else:
                    break

    def _listen_loop(self):
        """
        Core always-on loop:
        1. Open mic stream
        2. Detect speech onset with VAD
        3. Record until silence
        4. STT → intent filter → dispatch if COMMAND
        """
        import pyaudio

        pa = pyaudio.PyAudio()
        stream = None
        try:
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.frame_size,
            )
            logger.debug("VAD mic stream open — listening always on")

            while self._running:
                # ── Pause handling ──────────────────────────────────────────
                if self._paused:
                    if stream.is_active():
                        stream.stop_stream()
                    self._pause_event.wait()          # Block until resumed
                    if not self._running:
                        break
                    if not stream.is_active():
                        stream.start_stream()
                    self.vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)  # Reset VAD state
                    continue

                # ── Read one frame ──────────────────────────────────────────
                audio_data = stream.read(self.frame_size, exception_on_overflow=False)
                is_speech = self.vad.is_speech(audio_data, self.sample_rate)

                if not is_speech:
                    continue  # Silence — keep looping

                # ── Speech detected → capture full utterance ────────────────
                logger.debug("VAD: speech onset detected")
                utterance = self._capture_utterance(stream, audio_data)

                if not utterance:
                    continue

                # ── Pause mic while we process (avoid feedback) ─────────────
                self.pause()
                threading.Thread(
                    target=self._process_utterance,
                    args=(utterance,),
                    daemon=True,
                    name="vad-process",
                ).start()

        finally:
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            pa.terminate()

    def _capture_utterance(self, stream, first_frame: bytes) -> bytes:
        """
        Capture audio frames until silence detected.
        Returns PCM bytes, or None if too short.
        """
        frames = [first_frame]
        silence_count = 0
        max_frames = 30 * 1000 // self.frame_duration_ms  # 30s safety cap

        while self._running and not self._paused:
            audio_data = stream.read(self.frame_size, exception_on_overflow=False)
            frames.append(audio_data)
            is_speech = self.vad.is_speech(audio_data, self.sample_rate)

            if is_speech:
                silence_count = 0
            else:
                silence_count += 1
                if silence_count >= self.silence_limit:
                    logger.debug("VAD: utterance end (%d frames)", len(frames))
                    break

            if len(frames) >= max_frames:
                logger.warning("VAD: utterance safety cap hit (30s)")
                break

        pcm = b"".join(frames)
        # Discard very short clips (< 0.3s = likely noise burst)
        if len(pcm) < (self.sample_rate * 2 * 0.3):
            logger.debug("VAD: utterance too short — discarding")
            return None
        return pcm

    def _process_utterance(self, pcm: bytes):
        """
        STT → intent filter → dispatch.
        Runs in a background thread so the mic loop restarts ASAP.
        """
        try:
            if not self._stt:
                logger.warning("No STT injected — cannot process utterance")
                self.resume()
                return

            # Step 1: Transcribe
            text = self._stt.transcribe(pcm)
            if not text or not text.strip():
                logger.debug("Empty transcription — discarding silently")
                self.resume()
                return

            logger.info("Transcribed: '%s'", text)

            # Step 2: Intent filter
            intent = _classify_intent(text)
            if intent != "COMMAND":
                logger.info("Intent: NOISE — discarding '%s'", text[:60])
                self.resume()
                return

            # Step 3: Dispatch via callback
            logger.info("Intent: COMMAND → dispatching '%s'", text[:80])
            if self.on_utterance:
                self.on_utterance(text)
            else:
                logger.warning("No on_utterance callback set")

        except Exception as e:
            logger.error("Utterance processing error: %s", e, exc_info=True)
        finally:
            # Always resume listening after processing
            self.resume()
