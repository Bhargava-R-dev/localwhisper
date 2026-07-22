"""Paste text at the cursor via the clipboard (reliable across all apps).

Hardened against the intermittent Windows failure where another process holds the
clipboard lock and pyperclip raises "Error calling OpenClipboard (Access denied)".
Such a failure must NEVER propagate — a single bad paste should not crash the app.
"""
import time
import pyperclip
import keyboard


def _default_paste():
    keyboard.send("ctrl+v")


def _copy_with_retry(clipboard, value, sleep, attempts=5):
    """Try to put `value` on the clipboard, retrying if it's momentarily locked.

    Returns True on success, False if every attempt failed. Never raises.
    """
    for i in range(attempts):
        try:
            clipboard.copy(value)
            return True
        except Exception:
            sleep(0.04 * (i + 1))   # brief backoff; the lock is usually released fast
    return False


def paste_at_cursor(text: str, paste_fn=None, clipboard=pyperclip, sleep=time.sleep):
    """Save clipboard -> put text -> Ctrl+V -> restore clipboard. No-op on blank text.

    Returns True if the text was placed and pasted, False if the clipboard was
    unavailable. Never raises, so the caller's loop keeps running no matter what.
    """
    if not text or not text.strip():
        return False
    paste_fn = paste_fn or _default_paste

    try:
        saved = clipboard.paste()
    except Exception:
        saved = ""

    if not _copy_with_retry(clipboard, text, sleep):
        return False               # clipboard stayed locked — give up quietly, don't crash

    sleep(0.05)                    # let the OS register the new clipboard contents
    try:
        paste_fn()
    except Exception:
        pass                       # a failed keystroke send shouldn't kill the app either

    sleep(0.10)                    # let the target app read the clipboard before we restore
    _copy_with_retry(clipboard, saved, sleep)
    return True
