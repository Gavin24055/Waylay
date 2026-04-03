# Waylay — Windows Setup Guide

Complete step-by-step guide to migrate Waylay from macOS to a Windows laptop.

---

## Prerequisites Check

Before starting, confirm your Windows machine has:
- Windows 10 (21H2+) or Windows 11
- At least 16 GB RAM (Ollama needs 8 GB free for qwen2.5:7b)
- 20 GB free disk space (models + venv)
- A working microphone
- Internet connection (first-time model downloads)

---

## Step 1 — Install Core Dependencies

### 1a. Install Python 3.11
1. Go to https://www.python.org/downloads/release/python-3119/
2. Download **Windows installer (64-bit)**
3. Run installer — **✅ tick "Add Python to PATH"** before clicking Install
4. Verify:
   ```
   python --version
   # Should print: Python 3.11.x
   ```

### 1b. Install Git
1. Download from https://git-scm.com/download/win
2. Install with defaults (keep "Git Bash" option checked)
3. Verify:
   ```
   git --version
   ```

### 1c. Install Ollama
1. Download from https://ollama.com/download/windows
2. Run the installer — Ollama installs as a desktop app and starts automatically
3. Verify (open Command Prompt):
   ```
   ollama --version
   ```

### 1d. Install Tesseract OCR (for screenshot skills)
1. Download from: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to default path: `C:\Program Files\Tesseract-OCR\`
3. Add to PATH:
   - Search "Environment Variables" in Start Menu
   - Edit PATH → Add `C:\Program Files\Tesseract-OCR`

### 1e. Install ADB (for Phone skills)
1. Download Platform Tools from https://developer.android.com/tools/releases/platform-tools
2. Extract to `C:\adb\`
3. Add `C:\adb` to your PATH

---

## Step 2 — Clone the Repository

Open **Command Prompt** or **PowerShell** (not as admin):

```cmd
cd %USERPROFILE%
git clone https://github.com/Gavin24055/Waylay.git jarvis
cd jarvis
```

---

## Step 3 — Create Virtual Environment

```cmd
cd %USERPROFILE%\jarvis
python -m venv venv
venv\Scripts\activate
```

You should see `(venv)` in your prompt. **Always activate the venv before running Waylay.**

---

## Step 4 — Install Python Packages

```cmd
pip install --upgrade pip
pip install -r requirements.txt
```

> **Note about PyAudio on Windows:**
> PyAudio often fails with pip on Windows. If you get an error:
> ```cmd
> pip install pipwin
> pipwin install pyaudio
> ```
> If that also fails, download the wheel from:
> https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
> Then: `pip install PyAudio‑0.2.14‑cp311‑cp311‑win_amd64.whl`

> **Note about webrtcvad on Windows:**
> If `webrtcvad` fails to install:
> ```cmd
> pip install webrtcvad-wheels
> ```
> The config already handles this fallback automatically.

> **Note about piper-tts on Windows:**
> If piper-tts fails (it sometimes does), install a pre-built binary:
> ```cmd
> pip install piper-tts --no-build-isolation
> ```
> Or skip it entirely — edge-tts is the primary TTS and doesn't need Piper.

---

## Step 5 — Pull Ollama Models

With Ollama running (it auto-starts on Windows after install):

```cmd
ollama pull qwen2.5:7b
ollama pull llama3.2:3b
```

> `qwen2.5:7b` is ~4.7 GB. `llama3.2:3b` is ~2.0 GB. Total ~7 GB.
> These only download once and are stored in `%USERPROFILE%\.ollama\models\`

Verify both are available:
```cmd
ollama list
```

---

## Step 6 — Download Piper Voice Model (Offline Fallback)

This is optional since edge-tts is primary, but good to have for offline use.

```cmd
mkdir %USERPROFILE%\jarvis\models
```

Download the model from:
https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx

Save it to: `%USERPROFILE%\jarvis\models\en_US-lessac-medium.onnx`

Also download the config:
https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json

Save to: `%USERPROFILE%\jarvis\models\en_US-lessac-medium.onnx.json`

---

## Step 7 — Configure Environment

```cmd
cd %USERPROFILE%\jarvis
copy .env.example .env
notepad .env
```

Edit `.env` with your values:

```env
# Required for Groq fallback LLM
GROQ_API_KEY=gsk_xxxxxxxxxxxx

# Required for weather skills
OPENWEATHER_API_KEY=xxxxxxxxxxxxxxxx

# Point to your credentials.json from Google Cloud Console
GOOGLE_CREDENTIALS_PATH=C:\Users\YourName\jarvis\credentials.json

# Piper model path (Windows uses backslash OR forward slash — both work)
PIPER_MODEL_PATH=C:\Users\YourName\jarvis\models\en_US-lessac-medium.onnx

# Your name
USER_NAME=Gavin
USER_LOCATION=Bengaluru
```

> The `OLLAMA_HOST`, `VOICE_NAME`, `VOICE_RATE`, `VOICE_PITCH`, and
> `INTENT_FILTER_MODEL` are already set to good defaults — no need to change them.

---

## Step 8 — Google OAuth Setup (Gmail/Calendar)

1. Go to https://console.cloud.google.com/
2. Create a project → Enable Gmail API + Google Calendar API
3. Create OAuth 2.0 credentials → Download as `credentials.json`
4. Place `credentials.json` in `%USERPROFILE%\jarvis\`
5. First run will open a browser to authorize — follow the prompts
6. A `token.json` will be created automatically

---

## Step 9 — Test the Installation

```cmd
cd %USERPROFILE%\jarvis
venv\Scripts\activate
python main.py --test "what time is it"
```

Expected output:
```
  Waylay — Test Mode: "what time is it"

  Result: It's [current time], Gavin.
```

---

## Step 10 — Run Full Voice Mode

```cmd
cd %USERPROFILE%\jarvis
venv\Scripts\activate
python main.py
```

You'll see a health check table, then Waylay will say **"Waylay is online. What's up, Gavin?"**

Just talk — no wake word needed. The VAD mic will pick up your voice.

---

## Step 11 — Auto-Start on Windows Login (Optional)

### Method A: Startup Folder (Simple)

1. Press `Win + R` → type `shell:startup` → press Enter
2. Right-click in the folder → New → Shortcut
3. Target: `C:\Users\YourName\jarvis\waylay_start.bat`
4. Name it: `Waylay`
5. Right-click the shortcut → Properties → Run: **Minimized**

### Method B: Task Scheduler (Recommended — more reliable)

1. Open **Task Scheduler** (search in Start Menu)
2. Create Basic Task:
   - Name: `Waylay AI`
   - Trigger: When I log on
   - Action: Start a program
   - Program: `C:\Users\YourName\jarvis\waylay_start.bat`
   - Start in: `C:\Users\YourName\jarvis\`
3. Finish → right-click the task → Properties → General:
   - ✅ "Run only when user is logged on"
   - ✅ "Run with highest privileges" (needed for mic access)
4. Apply & OK

### Verify auto-start works:

```cmd
cd %USERPROFILE%\jarvis
waylay_start.bat
```

---

## Troubleshooting

### "No module named 'pyaudio'"
```cmd
pip install pipwin && pipwin install pyaudio
```

### "No module named 'webrtcvad'"
```cmd
pip install webrtcvad-wheels
```

### "Ollama connection refused"
Ollama should auto-start on Windows. If not:
```cmd
ollama serve
```
Or find "Ollama" in your system tray and click "Start".

### "edge-tts timeout / no audio"
edge-tts requires internet. Check your connection. Waylay will auto-fall back to Piper (offline).

### "Microphone not detected"
- Open Windows Settings → Privacy → Microphone → Allow desktop apps: **ON**
- Check Device Manager → Audio inputs → ensure your mic isn't disabled

### "Google OAuth redirect_uri_mismatch"
Add `http://localhost` to your OAuth 2.0 authorized redirect URIs in Google Cloud Console.

### Piper model not found
If Piper is missing, Waylay falls back to edge-tts. No action needed.
Delete the `PIPER_MODEL_PATH` line from `.env` to suppress the warning.

---

## Key Differences: macOS vs Windows

| Feature | macOS | Windows |
|---------|-------|---------|
| Auto-start | LaunchAgent plist | Task Scheduler / Startup folder |
| Start script | `waylay_start.sh` | `waylay_start.bat` |
| Venv activate | `source venv/bin/activate` | `venv\Scripts\activate` |
| Piper install | `pip install piper-tts` | May need `--no-build-isolation` |
| PyAudio install | `pip install pyaudio` | Use `pipwin install pyaudio` |
| webrtcvad | `pip install webrtcvad` | `pip install webrtcvad-wheels` |
| ADB path | `/usr/local/bin/adb` | `C:\adb\adb.exe` |
| Tesseract | `brew install tesseract` | Manual installer |

---

## Quick Reference Commands (Windows)

```cmd
REM Activate environment
cd %USERPROFILE%\jarvis && venv\Scripts\activate

REM Run Waylay
python main.py

REM Test mode
python main.py --test "what's the weather"

REM Pull a new Ollama model
ollama pull llama3.2:3b

REM Update from Git
git pull origin main

REM Update packages
pip install -r requirements.txt --upgrade
```
