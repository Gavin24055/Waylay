"""
Waylay — Text-to-Speech (Upgrade 2)

Primary:  edge-tts  (Microsoft Edge neural voices — near-human, free, no API key)
Fallback: Piper TTS (local, offline, works without internet)

Voice: en-US-AriaNeural — warm, natural, casual AI assistant voice.
Includes interrupt detection: background thread monitors audio while playing;
if user speaks above threshold, playback stops immediately.
"""

import asyncio
import logging
import tempfile
import threading
import time
import wave
from pathlib import Path

import numpy as np

from config import (
    PIPER_MODEL_PATH,
    WAKE_CHIME_FREQUENCY,
    WAKE_CHIME_DURATION,
    VOICE_NAME,
    VOICE_RATE,
    VOICE_PITCH,
    SAMPLE_RATE,
)

logger = logging.getLogger("j.voice.tts")

# ── Interrupt state (module-level so it can be read from threads) ─────────────
_playing = False
_interrupt_requested = False
_interrupt_lock = threading.Lock()


class TextToSpeech:
    """
    TTS engine with edge-tts primary, Piper fallback, and interrupt detection.
    """

    def __init__(self):
        import pygame
        pygame.mixer.init(frequency=44100, size=-16, channels=1)
        self._piper = None
        self.model_path = PIPER_MODEL_PATH
        self._edge_tts_available = self._check_edge_tts()
        logger.info(
            "TTS engine init — primary: %s, fallback: Piper (%s)",
            f"edge-tts ({VOICE_NAME})" if self._edge_tts_available else "edge-tts UNAVAILABLE",
            Path(self.model_path).name,
        )

    def _check_edge_tts(self) -> bool:
        """Check if edge-tts is installed."""
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            logger.warning("edge-tts not installed — pip install edge-tts")
            return False

    # ── Main speak API ────────────────────────────────────────────────────────

    def speak(self, text: str):
        """
        Synthesise text and play audio.
        Tries edge-tts first; falls back to Piper on failure.
        Interrupt detection runs in a background thread while playing.
        """
        if not text or not text.strip():
            return

        if self._edge_tts_available:
            try:
                self._speak_edge(text)
                return
            except Exception as e:
                logger.warning("edge-tts failed (%s) — falling back to Piper", e)

        # Piper fallback
        self._speak_piper(text)

    def speak_streaming(self, sentence_iter):
        """
        Streaming TTS — speak sentences as they arrive from the LLM.
        sentence_iter: iterable yielding str sentences.
        """
        for sentence in sentence_iter:
            if not sentence.strip():
                continue
            logger.info("Streaming TTS: %s", sentence[:80])
            self.speak(sentence)
            if _interrupt_requested:
                logger.info("Interrupt during streaming — stopping TTS chain")
                break

    # ── edge-tts (Primary) ────────────────────────────────────────────────────

    def _speak_edge(self, text: str):
        """Generate audio via edge-tts and play with pygame."""
        import pygame
        import edge_tts

        global _playing, _interrupt_requested

        tmp_path = "/tmp/waylay_tts.mp3"

        async def _generate():
            communicate = edge_tts.Communicate(
                text,
                voice=VOICE_NAME,
                rate=VOICE_RATE,
                pitch=VOICE_PITCH,
            )
            await communicate.save(tmp_path)

        # Generate audio (async → sync)
        asyncio.run(_generate())

        # Play with interrupt monitoring
        with _interrupt_lock:
            _playing = True
            _interrupt_requested = False

        # Start interrupt listener thread
        interrupt_thread = threading.Thread(
            target=_listen_for_interrupt,
            daemon=True,
            name="tts-interrupt",
        )
        interrupt_thread.start()

        try:
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                if _interrupt_requested:
                    pygame.mixer.music.stop()
                    logger.info("TTS interrupted by user speech")
                    break
                time.sleep(0.05)

        finally:
            with _interrupt_lock:
                _playing = False

            # Clean up temp file
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass

        logger.info("Spoke (edge-tts): %s", text[:80])

    # ── Piper Fallback ────────────────────────────────────────────────────────

    @property
    def _piper_voice(self):
        """Lazy-load Piper to avoid startup cost if edge-tts works."""
        if self._piper is None:
            from piper import PiperVoice
            self._piper = PiperVoice.load(self.model_path)
            logger.info("Piper voice model loaded (fallback)")
        return self._piper

    def _speak_piper(self, text: str):
        """Synthesise via Piper and play with pygame."""
        import pygame

        global _playing, _interrupt_requested

        tmp_path = None
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp_path = tmp.name
            with wave.open(tmp, "wb") as wf:
                self._piper_voice.synthesize_wav(text, wf)

            with _interrupt_lock:
                _playing = True
                _interrupt_requested = False

            interrupt_thread = threading.Thread(
                target=_listen_for_interrupt,
                daemon=True,
                name="tts-interrupt",
            )
            interrupt_thread.start()

            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                if _interrupt_requested:
                    pygame.mixer.music.stop()
                    logger.info("TTS (Piper) interrupted by user speech")
                    break
                time.sleep(0.05)

        except Exception as e:
            logger.error("Piper TTS error: %s", e)
        finally:
            with _interrupt_lock:
                _playing = False
            if tmp_path:
                try:
                    Path(tmp_path).unlink()
                except Exception:
                    pass

        logger.info("Spoke (Piper fallback): %s", text[:80])

    # ── Chimes / Feedback Tones ───────────────────────────────────────────────

    def play_chime(self, frequency: int = None, duration: float = None):
        """Play a short chime tone (Siri-style). No audio file needed."""
        import pygame

        freq = frequency or WAKE_CHIME_FREQUENCY
        dur = duration or WAKE_CHIME_DURATION

        try:
            sample_rate = 22050
            n_samples = int(sample_rate * dur)
            t = np.linspace(0, dur, n_samples, endpoint=False)
            tone = np.sin(2 * np.pi * freq * t) * 0.3
            fade = np.linspace(1, 0, n_samples)
            samples = (tone * fade * 32767).astype(np.int16)
            sound = pygame.mixer.Sound(buffer=samples.tobytes())
            sound.play()
            pygame.time.wait(int(dur * 1000) + 80)
            logger.debug("Chime played (%dHz, %.2fs)", freq, dur)
        except Exception as e:
            logger.warning("Chime failed: %s", e)

    def play_error_tone(self):
        """Play a low double-beep for 'didn't catch that'."""
        import pygame
        self.play_chime(frequency=330, duration=0.1)
        pygame.time.wait(80)
        self.play_chime(frequency=280, duration=0.1)

    def stop(self):
        """Stop any currently playing audio."""
        global _interrupt_requested
        import pygame
        _interrupt_requested = True
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass


# ── Interrupt Listener (module-level, shared by all TTS sessions) ─────────────

def _listen_for_interrupt():
    """
    Background thread: monitors mic audio while TTS is playing.
    If speech energy exceeds threshold → sets _interrupt_requested.
    """
    global _interrupt_requested, _playing

    INTERRUPT_THRESHOLD = 600   # RMS amplitude (out of 32767). Tune to room.
    try:
        import pyaudio

        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=1024,
        )

        while _playing:
            try:
                data = stream.read(1024, exception_on_overflow=False)
                audio = np.frombuffer(data, dtype=np.int16)
                rms = np.sqrt(np.mean(audio.astype(np.float32) ** 2))
                if rms > INTERRUPT_THRESHOLD:
                    logger.info("Interrupt detected — RMS=%.0f > threshold=%d", rms, INTERRUPT_THRESHOLD)
                    _interrupt_requested = True
                    break
            except Exception:
                break

        stream.stop_stream()
        stream.close()
        pa.terminate()

    except Exception as e:
        logger.warning("Interrupt listener error: %s", e)
