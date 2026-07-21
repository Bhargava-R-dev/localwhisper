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

    # Endpointing (hands-free path only)
    endpoint_silence_ms: int = 1500    # stop after this much trailing silence
    max_record_ms: int = 15000         # hard cap on a single utterance
    energy_threshold: float = 0.01     # RMS above this = speech

    # Feedback
    beep: bool = True


def load_config() -> Config:
    return Config()
