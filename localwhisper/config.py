"""Central configuration. Edit the defaults below to tune behavior."""
from dataclasses import dataclass


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

    # Wake word
    wakeword_model: str = "hey_jarvis" # ready-made phrase; swap once custom "Hey PC" is trained
    wakeword_threshold: float = 0.5

    # Endpointing (hands-free / wake-word path only)
    endpoint_silence_ms: int = 1500    # PRIMARY stop for hands-free: stop after this much trailing silence
    max_record_ms: int = 120000        # runaway safety cap only (2 min); silence normally stops it first
    energy_threshold: float = 0.01     # RMS above this = speech

    # Push-to-talk safety cap (hold/toggle end on the key/tap, not this — this is just a runaway guard)
    max_hold_ms: int = 120000          # 2 minutes; long enough for real dictation, avoids
                                       # pathologically slow single-shot transcription of huge clips

    # Feedback
    beep: bool = True
    show_overlay: bool = True          # Siri-style on-screen "listening" indicator


def load_config() -> Config:
    return Config()
