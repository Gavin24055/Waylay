@echo off
REM ─────────────────────────────────────────────────────────────
REM Waylay Start Script (Windows)
REM Drop a shortcut to this file in shell:startup for auto-launch.
REM Or use Task Scheduler for more control (see README).
REM ─────────────────────────────────────────────────────────────

echo [%DATE% %TIME%] Waylay startup... >> "%USERPROFILE%\jarvis\data\waylay.log"

REM Change to project directory
cd /d "%USERPROFILE%\jarvis"

REM Activate virtual environment
call "%USERPROFILE%\jarvis\venv\Scripts\activate.bat"

REM Start Ollama minimised in background (if not already running)
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe" > NUL
if "%ERRORLEVEL%"=="1" (
    echo [%DATE% %TIME%] Starting Ollama... >> "%USERPROFILE%\jarvis\data\waylay.log"
    start /min "" ollama serve
    timeout /t 4 /nobreak > NUL
) else (
    echo [%DATE% %TIME%] Ollama already running >> "%USERPROFILE%\jarvis\data\waylay.log"
)

REM Start Waylay hidden (pythonw = no console window)
REM stdout/stderr captured to log file
pythonw "%USERPROFILE%\jarvis\main.py" >> "%USERPROFILE%\jarvis\data\waylay.log" 2>> "%USERPROFILE%\jarvis\data\waylay_error.log"
