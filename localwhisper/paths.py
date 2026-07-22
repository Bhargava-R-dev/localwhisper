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


def ensure_wakeword_models():
    """Download openWakeWord's ONNX models if missing (source/pip mode only).

    No-op in a frozen build, where the models are already bundled and the package
    directory is read-only.
    """
    if is_frozen():
        return
    import openwakeword
    base = os.path.join(
        os.path.dirname(os.path.abspath(openwakeword.__file__)), "resources", "models"
    )
    if os.path.isfile(os.path.join(base, "hey_jarvis_v0.1.onnx")):
        return
    from openwakeword.utils import download_models
    download_models()
