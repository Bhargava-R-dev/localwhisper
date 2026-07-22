"""Resolve the whisper model location for source vs frozen (PyInstaller) builds."""
import os
import sys


def is_frozen() -> bool:
    """True when running inside a PyInstaller-built executable."""
    return bool(getattr(sys, "frozen", False))


def whisper_model_source(config) -> str:
    """Bundled small.en directory when frozen; otherwise the HF model name from config.

    In a frozen build the CTranslate2 model files are bundled under
    ``models/whisper-small.en`` next to the executable's resources, so faster-whisper
    loads them from disk with no network access. From source we return the plain model
    name and let faster-whisper fetch/cache it from Hugging Face as usual.
    """
    if is_frozen():
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
        return os.path.join(base, "models", "whisper-small.en")
    return config.model_name
