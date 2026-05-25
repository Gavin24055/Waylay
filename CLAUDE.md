# Waylay AI Context

This file provides context to AI coding assistants (like Antigravity or Claude) about the Waylay project when developing on Windows or macOS.

## Current State (v2.0)
- **Architecture**: Voice-activated, always-on AI life OS.
- **Microphone**: Pure Voice Activity Detection (webrtcvad) — no wake word.
- **Intent Filter**: `llama3.2:3b` filters transcribed text to determine if it's a `COMMAND` or `NOISE`.
- **Primary LLM**: Local Ollama `qwen2.5:7b` (streaming).
- **Fallback LLM**: Groq `llama-3.3-70b-versatile`.
- **Text-to-Speech**: `edge-tts` (en-US-AriaNeural) with streaming support for low latency, falls back to local `piper-tts`.
- **Auto-Start**: macOS LaunchAgent or Windows Task Scheduler.

## Important Files
- `main.py`: The orchestrator, ties memory, brain, voice, skills, and proactive systems together.
- `voice/recorder.py`: VAD microphone listener.
- `voice/tts.py`: edge-tts and Piper fallback.
- `brain/llm.py`: Ollama and Groq chat execution (includes streaming).
- `config.py`: Environment variables, API keys, and model paths.
- `WINDOWS_SETUP.md`: Step-by-step setup guide for Windows.

## Windows Development Notes
- **Virtual Environment**: Activate using `venv\Scripts\activate`.
- **Ollama**: Automatically runs as a service on Windows.
- **Audio (PyAudio)**: Installing PyAudio on Windows can be tricky. Use `pipwin install pyaudio` or download the precompiled `.whl`.
- **webrtcvad**: Use `webrtcvad-wheels` on Windows.
- **Auto-start**: Controlled via `waylay_start.bat` and Task Scheduler (or Startup folder).

## Next Steps / Backlog
- Create new skills in the `skills/` directory using the `@skill` decorator.
- Monitor `data/waylay.log` and `data/waylay_error.log` for debug information.
- Enhance intent filtering or update the system prompt in `system_prompt.txt` to modify Jarvis's behavior.
