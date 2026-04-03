"""
J — Speech-to-Text
Uses SpeechRecognition with Google's free API as primary,
with Groq Whisper API as fallback.
faster-whisper / ctranslate2 segfaults on Intel macOS — not used.
"""

import logging
import tempfile
import wave
import numpy as np
from config import SAMPLE_RATE

logger = logging.getLogger("j.voice.stt")


class SpeechToText:
    """Transcribes audio using SpeechRecognition (Google free API).
    No local model needed — fast and reliable."""

    def __init__(self):
        import speech_recognition as sr
        self.recognizer = sr.Recognizer()
        logger.info("STT ready (SpeechRecognition — Google free API)")

    def transcribe(self, pcm_audio: bytes) -> str:
        """
        Transcribe raw PCM16 mono 16kHz audio bytes to text.
        Returns the transcribed string.
        """
        import speech_recognition as sr

        if len(pcm_audio) < 3200:  # less than 0.1s
            logger.debug("Audio too short, skipping transcription")
            return ""

        # Write PCM to temp WAV for SpeechRecognition
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp.name
        try:
            with wave.open(tmp, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(pcm_audio)

            # Load audio file for recognition
            with sr.AudioFile(tmp_path) as source:
                audio_data = self.recognizer.record(source)

            # Try Google's free speech recognition
            try:
                text = self.recognizer.recognize_google(audio_data, language="en-IN")
                logger.info("Transcribed (Google): %s", text)
                return text.strip()
            except sr.UnknownValueError:
                logger.info("Google STT: could not understand audio")
                return ""
            except sr.RequestError as e:
                logger.warning("Google STT request failed: %s — trying Groq Whisper", e)
                return self._fallback_groq(tmp_path)

        except Exception as e:
            logger.error("STT error: %s", e)
            return ""
        finally:
            try:
                import os
                os.unlink(tmp_path)
            except Exception:
                pass

    def _fallback_groq(self, wav_path: str) -> str:
        """Fallback: use Groq's free Whisper API for transcription."""
        try:
            from groq import Groq
            from config import GROQ_API_KEY
            if not GROQ_API_KEY:
                return ""

            client = Groq(api_key=GROQ_API_KEY)
            with open(wav_path, "rb") as f:
                transcription = client.audio.transcriptions.create(
                    file=("audio.wav", f),
                    model="whisper-large-v3-turbo",
                    language="en",
                )
            text = transcription.text.strip()
            logger.info("Transcribed (Groq Whisper): %s", text)
            return text
        except Exception as e:
            logger.error("Groq Whisper fallback failed: %s", e)
            return ""
