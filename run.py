"""Executable entry point for LocalWhisper.

Used both as the PyInstaller entry script and as the `localwhisper` console command.
Because the packaged build is windowed (no console), any startup crash is written to
%LOCALAPPDATA%\\LocalWhisper\\localwhisper.log so problems are diagnosable on machines
with no terminal attached.
"""
import os
import traceback


def _log_path():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, "LocalWhisper")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "localwhisper.log")


def _selftest():
    """Verify the bundled model loads and transcribes. Writes result to selftest.txt.

    Windowed builds have no console, so the outcome is written to a file next to the log
    and the process exits 0 on success / 1 on failure.
    """
    import os
    import sys
    import wave
    import numpy as np

    out = os.path.join(os.path.dirname(_log_path()), "selftest.txt")
    try:
        from localwhisper.config import load_config
        from localwhisper.engine import WhisperEngine

        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        wav = os.path.join(base, "selftest", "jfk.wav")
        with wave.open(wav, "rb") as w:
            pcm = w.readframes(w.getnframes())
        audio = np.frombuffer(pcm, dtype="<i2").astype("float32") / 32768.0

        engine = WhisperEngine(load_config())
        text = engine.transcribe(audio)
        ok = "country" in text.lower()
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(f"{'SELFTEST_OK' if ok else 'SELFTEST_FAIL'} text={text!r}\n")
        return 0 if ok else 1
    except Exception:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write("SELFTEST_ERROR\n" + traceback.format_exc() + "\n")
        return 1


def main():
    import sys
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    try:
        from localwhisper.app import main as app_main
        app_main()
    except Exception:
        try:
            with open(_log_path(), "a", encoding="utf-8") as fh:
                fh.write(traceback.format_exc() + "\n")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
