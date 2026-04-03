"""
Waylay — PC Control Skills
Cross-platform: macOS + Windows (Linux fallback).
Screenshot, OCR, app launch/close, browser, clipboard, shell.
"""

import logging
import os
import platform
import subprocess
import urllib.parse
from datetime import datetime
from pathlib import Path

from config import SAFE_SHELL_COMMANDS, DATA_DIR
from skills.loader import skill

logger = logging.getLogger("j.skills.pc")

IS_MAC = platform.system() == "Darwin"
IS_WIN = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"


# ── Screenshot ──────────────────────────────────────────────────

@skill
def take_screenshot() -> str:
    """Capture a full-screen screenshot and save it."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = DATA_DIR / f"screenshot_{ts}.png"

    if IS_MAC:
        result = subprocess.run(
            ["screencapture", "-x", str(filepath)],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and filepath.exists() and filepath.stat().st_size > 0:
            logger.info("Screenshot saved: %s", filepath)
            return f"Screenshot saved to {filepath}"
        err = result.stderr.strip()
        if "could not create image" in err.lower():
            return (
                "Screenshot failed — Screen Recording permission denied. "
                "Go to System Preferences → Privacy & Security → Screen Recording → enable Terminal."
            )
        # Fall through to pyautogui
        logger.warning("screencapture failed: %s — trying pyautogui", err)

    # Windows / Linux / macOS fallback
    try:
        import pyautogui
        img = pyautogui.screenshot()
        img.save(str(filepath))
        logger.info("Screenshot saved (pyautogui): %s", filepath)
        return f"Screenshot saved to {filepath}"
    except Exception as e:
        logger.error("Screenshot failed: %s", e)
        return f"Screenshot failed: {e}"


# ── Open Path ───────────────────────────────────────────────────

@skill
def open_path(path: str) -> str:
    """Open a file or folder in the default application / explorer."""
    expanded = str(Path(path).expanduser())
    try:
        if IS_WIN:
            os.startfile(expanded)
        elif IS_MAC:
            subprocess.Popen(["open", expanded])
        else:
            subprocess.Popen(["xdg-open", expanded])
        logger.info("Opened: %s", expanded)
        return f"Opened {expanded}"
    except Exception as e:
        logger.error("Failed to open %s: %s", expanded, e)
        return f"Failed to open: {e}"


# ── Launch App ──────────────────────────────────────────────────

@skill
def launch_app(name: str) -> str:
    """Launch an application by name."""
    try:
        if IS_MAC:
            result = subprocess.run(
                ["open", "-a", name],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                logger.info("Launched app: %s", name)
                return f"Launched {name}"
            return f"Couldn't find app: {name}"

        elif IS_WIN:
            # Try direct start first, then with .exe suffix
            try:
                subprocess.Popen(["start", "", name], shell=True)
                logger.info("Launched app (Windows): %s", name)
                return f"Launched {name}"
            except Exception:
                try:
                    subprocess.Popen([name + ".exe"])
                    return f"Launched {name}"
                except Exception as e2:
                    return f"Failed to launch {name}: {e2}"

        else:  # Linux
            subprocess.Popen([name.lower()])
            return f"Launched {name}"

    except Exception as e:
        logger.error("Launch failed for %s: %s", name, e)
        return f"Failed to launch {name}: {e}"


# ── Close App ───────────────────────────────────────────────────

@skill
def close_app(name: str) -> str:
    """Quit/close an application by name."""
    try:
        if IS_MAC:
            result = subprocess.run(
                ["osascript", "-e", f'tell application "{name}" to quit'],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                logger.info("Closed app: %s", name)
                return f"Closed {name}"
            # Fallback: killall
            subprocess.run(["killall", name], capture_output=True, timeout=3)
            return f"Force-closed {name}"

        elif IS_WIN:
            # Try taskkill by process name
            proc_name = name if name.endswith(".exe") else name + ".exe"
            result = subprocess.run(
                ["taskkill", "/IM", proc_name, "/F"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                logger.info("Closed app (Windows): %s", name)
                return f"Closed {name}"
            # Try without .exe
            subprocess.run(["taskkill", "/IM", name, "/F"],
                           capture_output=True, timeout=3)
            return f"Attempted to close {name}"

        else:  # Linux
            subprocess.run(["pkill", "-f", name], capture_output=True, timeout=3)
            return f"Closed {name}"

    except Exception as e:
        logger.error("Close failed for %s: %s", name, e)
        return f"Failed to close {name}: {e}"


# ── Open URL ────────────────────────────────────────────────────

@skill
def open_url(url: str) -> str:
    """Open a URL in the default browser."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        if IS_WIN:
            os.startfile(url)
        elif IS_MAC:
            subprocess.run(["open", url], capture_output=True, timeout=5)
        else:
            subprocess.run(["xdg-open", url], capture_output=True, timeout=5)
        logger.info("Opened URL: %s", url)
        return f"Opened {url}"
    except Exception as e:
        logger.error("Failed to open URL %s: %s", url, e)
        return f"Failed to open URL: {e}"


# ── Search in Browser ───────────────────────────────────────────

@skill
def search_in_browser(query: str) -> str:
    """Open a Google search in the default browser."""
    search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    try:
        if IS_WIN:
            os.startfile(search_url)
        elif IS_MAC:
            subprocess.run(["open", search_url], capture_output=True, timeout=5)
        else:
            subprocess.run(["xdg-open", search_url], capture_output=True, timeout=5)
        logger.info("Browser search: %s", query)
        return f"Opened Google search for: {query}"
    except Exception as e:
        logger.error("Browser search failed: %s", e)
        return f"Browser search failed: {e}"


# ── Delete File ─────────────────────────────────────────────────

@skill
def delete_file(path: str) -> str:
    """Move a file or folder to Trash/Recycle Bin (safe delete)."""
    target = Path(path).expanduser().resolve()
    if not target.exists():
        return f"Not found: {path}"

    try:
        if IS_MAC:
            result = subprocess.run(
                ["osascript", "-e",
                 f'tell application "Finder" to delete POSIX file "{target}"'],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                logger.info("Moved to Trash: %s", target)
                return f"Moved to Trash: {target.name}"
            return f"Could not delete: {result.stderr.strip()}"

        elif IS_WIN:
            try:
                import send2trash
                send2trash.send2trash(str(target))
                logger.info("Sent to Recycle Bin: %s", target)
                return f"Sent to Recycle Bin: {target.name}"
            except ImportError:
                # Fallback: try PowerShell
                subprocess.run(
                    ["powershell", "-Command",
                     f'Remove-Item "{target}" -Recurse -Force'],
                    capture_output=True, timeout=10,
                )
                return f"Deleted: {target.name}"

        else:  # Linux
            import shutil
            trash = Path.home() / ".local/share/Trash/files"
            trash.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(trash / target.name))
            return f"Moved to Trash: {target.name}"

    except Exception as e:
        logger.error("Delete failed: %s", e)
        return f"Delete failed: {e}"


# ── Type Text ───────────────────────────────────────────────────

@skill
def type_text(text: str) -> str:
    """Type text using keyboard automation."""
    try:
        import pyautogui
        pyautogui.typewrite(text, interval=0.02)
        logger.info("Typed text: %s", text[:50])
        return "Typed successfully"
    except Exception as e:
        logger.error("Type failed: %s", e)
        return f"Type failed: {e}"


# ── Shell Command ───────────────────────────────────────────────

@skill
def shell_command(cmd: str) -> str:
    """Run a safe shell command and return the output."""
    parts = cmd.strip().split()
    if not parts:
        return "Empty command"

    base_cmd = parts[0].lower()
    # Normalize Windows commands
    if IS_WIN and base_cmd == "ls":
        cmd = cmd.replace("ls", "dir", 1)
        base_cmd = "dir"

    if base_cmd not in SAFE_SHELL_COMMANDS:
        logger.warning("Blocked unsafe command: %s", cmd)
        return f"Command '{base_cmd}' is not in the approved safe list. Ask me first if you want me to run it."

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30,
        )
        output = result.stdout.strip() or result.stderr.strip()
        logger.info("Shell: %s → %s", cmd, output[:100])
        return output[:2000]
    except subprocess.TimeoutExpired:
        return "Command timed out (30s limit)"
    except Exception as e:
        return f"Command failed: {e}"


# ── Clipboard ───────────────────────────────────────────────────

@skill
def get_clipboard() -> str:
    """Get the current clipboard content."""
    try:
        import pyperclip
        return pyperclip.paste()[:1000]
    except Exception:
        pass
    try:
        if IS_MAC:
            result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=3)
            return result.stdout[:1000]
        elif IS_WIN:
            result = subprocess.run(
                ["powershell", "-command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=3,
            )
            return result.stdout.strip()[:1000]
    except Exception as e:
        return f"Clipboard read failed: {e}"
    return "Clipboard unavailable"


@skill
def set_clipboard(text: str) -> str:
    """Set the clipboard content."""
    try:
        import pyperclip
        pyperclip.copy(text)
        return "Copied to clipboard"
    except Exception:
        pass
    try:
        if IS_MAC:
            proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            proc.communicate(text.encode())
            return "Copied to clipboard"
        elif IS_WIN:
            subprocess.run(
                ["powershell", "-command", f'Set-Clipboard "{text}"'],
                capture_output=True, timeout=3,
            )
            return "Copied to clipboard"
    except Exception as e:
        return f"Clipboard write failed: {e}"
    return "Clipboard write failed"


# ── Active Window ───────────────────────────────────────────────

@skill
def get_active_window() -> str:
    """Get the title of the currently focused window."""
    if IS_MAC:
        try:
            result = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get name of first application process whose frontmost is true'],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

    elif IS_WIN:
        try:
            import pygetwindow as gw
            win = gw.getActiveWindow()
            return win.title if win else "Unknown"
        except Exception:
            pass
        try:
            result = subprocess.run(
                ["powershell", "-command",
                 "(Get-Process | Where-Object {$_.MainWindowTitle} | Sort-Object CPU -Descending | Select-Object -First 1).MainWindowTitle"],
                capture_output=True, text=True, timeout=3,
            )
            return result.stdout.strip() or "Unknown"
        except Exception:
            pass

    # pyautogui fallback (all platforms)
    try:
        import pyautogui
        win = pyautogui.getActiveWindow()
        return win.title if win else "Unknown"
    except Exception:
        return "Unknown"


# ── OCR ─────────────────────────────────────────────────────────

@skill
def read_screen_text() -> str:
    """Take a screenshot and extract all visible text using OCR."""
    try:
        screenshot_result = take_screenshot()
        if "failed" in screenshot_result.lower():
            return screenshot_result

        path = screenshot_result.replace("Screenshot saved to ", "").strip()
        from PIL import Image
        import pytesseract
        img = Image.open(path)
        text = pytesseract.image_to_string(img)
        logger.info("OCR extracted %d chars", len(text))
        return text[:3000]
    except Exception as e:
        logger.error("OCR failed: %s", e)
        return f"OCR failed: {e}"
