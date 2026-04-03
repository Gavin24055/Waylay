#!/bin/bash
# ─────────────────────────────────────────────────────────────
# Waylay Start Script (macOS)
# Runs by LaunchAgent on login, or manually: bash waylay_start.sh
# ─────────────────────────────────────────────────────────────

set -euo pipefail

JARVIS_DIR="/Users/gavin.p/jarvis"
LOG_DIR="$JARVIS_DIR/data"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

echo "[$(date)] Waylay startup script running..." >> "$LOG_DIR/waylay.log"

# Change to project directory
cd "$JARVIS_DIR"

# Activate virtual environment
source "$JARVIS_DIR/venv/bin/activate"

# ── Start Ollama if not running ──────────────────────────────
if ! pgrep -x "ollama" > /dev/null 2>&1; then
    echo "[$(date)] Starting Ollama..." >> "$LOG_DIR/waylay.log"
    ollama serve >> "$LOG_DIR/ollama.log" 2>&1 &
    # Give Ollama 3 seconds to bind its port
    sleep 3
else
    echo "[$(date)] Ollama already running" >> "$LOG_DIR/waylay.log"
fi

# ── Confirm Ollama is up ─────────────────────────────────────
for i in 1 2 3 4 5; do
    if curl -sf "http://localhost:11434/api/tags" > /dev/null 2>&1; then
        echo "[$(date)] Ollama confirmed up" >> "$LOG_DIR/waylay.log"
        break
    fi
    echo "[$(date)] Waiting for Ollama (attempt $i)..." >> "$LOG_DIR/waylay.log"
    sleep 2
done

# ── Start Waylay ─────────────────────────────────────────────
echo "[$(date)] Starting Waylay main.py..." >> "$LOG_DIR/waylay.log"
exec python3 "$JARVIS_DIR/main.py" >> "$LOG_DIR/waylay.log" 2>> "$LOG_DIR/waylay_error.log"
