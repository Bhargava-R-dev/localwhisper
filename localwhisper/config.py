"""Central configuration.

Defaults below are the built-in values. They can be overridden at runtime WITHOUT
rebuilding by dropping a JSON file at ``%LOCALAPPDATA%\\LocalWhisper\\config.json`` with any
subset of these fields, e.g. to turn the wake word on:

    { "wakeword_enabled": true, "wakeword_threshold": 0.8 }
"""
import json
import os
from dataclasses import dataclass, fields


@dataclass
class Config:
    # Transcription
    model_name: str = "small.en"       # quality priority; "base.en" is a faster fallback
    device: str = "cpu"
    compute_type: str = "int8"         # fastest good-quality CPU mode
    language: str = "en"

    # Audio
    sample_rate: int = 16000
    frame_len: int = 1280              # 80 ms per frame (openWakeWord's expected chunk)

    # Hotkeys
    hold_hotkey: str = "ctrl+b"        # walkie-talkie: record while held
    toggle_hotkey: str = "alt+n"       # tap to start, tap to stop

    # Wake word — OFF by default. It is an always-on listener that types transcribed audio
    # into the focused app, so false triggers are disruptive. Opt in via config.json.
    wakeword_enabled: bool = False
    wakeword_model: str = "hey_jarvis" # ready-made phrase; swap once custom "Hey PC" is trained
    wakeword_threshold: float = 0.75   # higher = fewer false triggers (0.5 was too sensitive)
    wakeword_patience: int = 3         # consecutive frames above threshold required to fire

    # Endpointing (hands-free / wake-word path only)
    endpoint_silence_ms: int = 1500    # PRIMARY stop for hands-free: stop after this much trailing silence
    max_record_ms: int = 30000         # wake safety cap (30 s) — bounds damage from any false trigger
    energy_threshold: float = 0.01     # RMS above this = speech

    # Push-to-talk safety cap (hold/toggle end on the key/tap, not this — this is just a runaway guard)
    max_hold_ms: int = 120000          # 2 minutes; long enough for real dictation

    # Feedback
    beep: bool = True
    show_overlay: bool = True          # Siri-style on-screen "listening" indicator


def _override_path() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "LocalWhisper", "config.json")


def load_config() -> Config:
    """Built-in defaults, overridden by any fields present in the user's config.json."""
    cfg = Config()
    path = _override_path()
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            valid = {f.name for f in fields(Config)}
            for key, value in data.items():
                if key in valid:
                    setattr(cfg, key, value)
    except Exception:
        pass   # a malformed override file must never stop the app from starting
    return cfg
