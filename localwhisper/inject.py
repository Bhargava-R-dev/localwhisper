"""Paste text at the cursor via the clipboard (reliable across all apps)."""
import time
import pyperclip
import keyboard


def _default_paste():
    keyboard.send("ctrl+v")


def paste_at_cursor(text: str, paste_fn=None, clipboard=pyperclip, sleep=time.sleep):
    """Save clipboard → put text → Ctrl+V → restore clipboard. No-op on blank text."""
    if not text or not text.strip():
        return
    paste_fn = paste_fn or _default_paste

    try:
        saved = clipboard.paste()
    except Exception:
        saved = ""

    clipboard.copy(text)
    sleep(0.05)          # let the OS register the new clipboard contents
    paste_fn()
    sleep(0.10)          # let the target app read the clipboard before we restore
    try:
        clipboard.copy(saved)
    except Exception:
        pass
