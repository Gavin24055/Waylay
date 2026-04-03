"""
Waylay — LLM Chain (Upgrade 3: Streaming)

Chain order: Ollama (primary, local, unlimited) → Groq (cloud fallback).

New in this version:
- chat_stream() method: streams Ollama tokens and yields complete sentences.
  First sentence arrives in ~1s instead of waiting for the full response.
- Sentence splitting on '. ', '? ', '! ', '\n' — streams naturally.
- Groq non-streaming fallback when Ollama is down.
"""

import json
import time
import logging
from datetime import date, datetime
import requests
from config import (
    GROQ_API_KEY, OLLAMA_HOST,
    GROQ_MODEL, OLLAMA_MODEL,
    GROQ_DAILY_LIMIT, GROQ_RPM_LIMIT, AUDIT_LOG,
)

logger = logging.getLogger("j.brain.llm")

# Sentence boundary punctuation for streaming splits
_SENTENCE_ENDS = [". ", "? ", "! ", "\n", ".\n", "?\n", "!\n"]


def check_ollama_running() -> bool:
    """Ping Ollama health endpoint. Returns True if running."""
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


class LLMChain:
    """
    LLM failover chain: Ollama (primary) → Groq (fallback).
    Ollama is preferred — local, unlimited, private, works offline.
    Groq is used only when Ollama is unavailable.
    """

    def __init__(self):
        self._groq_client = None
        self._groq_calls_today = 0
        self._groq_date = date.today()
        self._groq_minute_calls = []

        if check_ollama_running():
            logger.info("LLMChain initialised — Ollama ✅ primary | Groq fallback")
        else:
            logger.warning(
                "Ollama is NOT running. Start it with: ollama serve\n"
                "  Then pull a model: ollama pull qwen2.5:7b\n"
                "  Falling back to Groq for now."
            )
            logger.info("LLMChain initialised — Ollama ❌ offline | Groq primary")

    @property
    def groq_client(self):
        if self._groq_client is None and GROQ_API_KEY:
            from groq import Groq
            self._groq_client = Groq(api_key=GROQ_API_KEY)
        return self._groq_client

    def _check_groq_limits(self) -> bool:
        today = date.today()
        if self._groq_date != today:
            self._groq_calls_today = 0
            self._groq_date = today

        if self._groq_calls_today >= GROQ_DAILY_LIMIT:
            return False

        now = time.time()
        self._groq_minute_calls = [t for t in self._groq_minute_calls if now - t < 60]
        if len(self._groq_minute_calls) >= GROQ_RPM_LIMIT:
            return False

        return True

    def _audit_log(self, provider: str, success: bool, error: str = None):
        entry = f"[{datetime.now().isoformat()}] provider={provider} success={success}"
        if error:
            entry += f" error={error}"
        try:
            with open(AUDIT_LOG, "a") as f:
                f.write(entry + "\n")
        except Exception:
            pass
        if success:
            logger.info("LLM response via %s", provider)
        else:
            logger.warning("LLM %s failed: %s", provider, error or "unknown")

    def _build_messages(
        self, messages: list[dict], system_prompt: str = None
    ) -> list[dict]:
        """Prepend system prompt to messages list."""
        full = []
        if system_prompt:
            full.append({"role": "system", "content": system_prompt})
        full.extend(messages)
        return full

    # ── Non-streaming (original) ──────────────────────────────────────────────

    def _try_ollama(self, full_messages: list[dict], force_json: bool) -> str | None:
        """Try local Ollama — primary LLM, unlimited and private."""
        try:
            payload = {
                "model": OLLAMA_MODEL,
                "messages": full_messages,
                "stream": False,
                "options": {"temperature": 0.7},
            }
            if force_json:
                payload["format"] = "json"

            resp = requests.post(
                f"{OLLAMA_HOST}/api/chat",
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            result = resp.json()["message"]["content"]
            self._audit_log("ollama", True)
            return result
        except Exception as e:
            self._audit_log("ollama", False, str(e))
            return None

    def _try_groq(self, full_messages: list[dict], force_json: bool) -> str | None:
        """Try Groq cloud API — fallback when Ollama is unavailable."""
        if not GROQ_API_KEY or not self.groq_client or not self._check_groq_limits():
            return None

        try:
            response_format = {"type": "json_object"} if force_json else None
            resp = self.groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=full_messages,
                temperature=0.7,
                max_tokens=1024,
                response_format=response_format,
            )
            self._groq_calls_today += 1
            self._groq_minute_calls.append(time.time())
            result = resp.choices[0].message.content
            tokens = resp.usage.total_tokens if resp.usage else 0
            self._audit_log("groq", True)
            logger.info("Groq tokens used: %d (daily count: %d)", tokens, self._groq_calls_today)
            return result
        except Exception as e:
            self._audit_log("groq", False, str(e))
            time.sleep(1)
            return None

    def chat(
        self,
        messages: list[dict],
        system_prompt: str = None,
        force_json: bool = False,
    ) -> str:
        """
        Send messages through the LLM chain: Ollama → Groq.
        Non-streaming — returns complete response as a string.
        Used for tool-dispatch where we need the full JSON response.
        """
        full_messages = self._build_messages(messages, system_prompt)

        result = self._try_ollama(full_messages, force_json)
        if result:
            return result

        result = self._try_groq(full_messages, force_json)
        if result:
            return result

        logger.error("All LLM providers failed")
        self._audit_log("all", False, "all providers exhausted")
        return "I'm having trouble connecting right now. Make sure Ollama is running: ollama serve"

    # ── Streaming (Upgrade 3) ─────────────────────────────────────────────────

    def chat_stream(
        self,
        messages: list[dict],
        system_prompt: str = None,
    ):
        """
        Stream LLM response, yielding COMPLETE SENTENCES as they arrive.

        This cuts perceived latency from 5-8s to ~1-2s because the caller
        can start TTS on the first sentence while the LLM generates the rest.

        Yields: str — one complete sentence at a time
        Falls back to Groq (non-streaming) if Ollama is unavailable.
        """
        full_messages = self._build_messages(messages, system_prompt)

        # Try Ollama streaming first
        try:
            yielded = yield from self._ollama_stream(full_messages)
            if yielded:
                return
        except Exception as e:
            logger.warning("Ollama streaming failed: %s — falling back to Groq", e)

        # Fall back to Groq (non-streaming — Groq streaming is complex with rate-limits)
        result = self._try_groq(full_messages, force_json=False)
        if result:
            # Yield Groq response sentence-by-sentence too
            yield from _split_into_sentences(result)
        else:
            yield "I'm having trouble connecting right now. Make sure Ollama is running."

    def _ollama_stream(self, full_messages: list[dict]):
        """
        Generator: POST to Ollama /api/chat with stream=True.
        Accumulates tokens into a buffer, yields on sentence boundaries.
        Returns True if any content was yielded, False otherwise.
        """
        payload = {
            "model": OLLAMA_MODEL,
            "messages": full_messages,
            "stream": True,
            "options": {"temperature": 0.7},
        }

        resp = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json=payload,
            stream=True,
            timeout=60,
        )
        resp.raise_for_status()

        buffer = ""
        yielded_anything = False
        t0 = time.time()

        for line in resp.iter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue

            token = chunk.get("message", {}).get("content", "")
            buffer += token

            # Yield complete sentences greedily
            while True:
                found = False
                for punct in _SENTENCE_ENDS:
                    idx = buffer.find(punct)
                    if idx != -1:
                        sentence = buffer[: idx + len(punct)].strip()
                        buffer = buffer[idx + len(punct):]
                        if sentence:
                            if not yielded_anything:
                                logger.info(
                                    "First sentence ready in %.2fs: %s",
                                    time.time() - t0, sentence[:60],
                                )
                            yield sentence
                            yielded_anything = True
                        found = True
                        break
                if not found:
                    break

            # Stream done?
            if chunk.get("done", False):
                break

        # Yield any remaining buffer content
        if buffer.strip():
            yield buffer.strip()
            yielded_anything = True

        self._audit_log("ollama-stream", True)
        return yielded_anything


# ── Helpers ───────────────────────────────────────────────────────────────────

def _split_into_sentences(text: str) -> list[str]:
    """Split a complete response into a list of sentences for non-streaming fallback."""
    import re
    # Split on sentence-ending punctuation followed by whitespace
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip()]
