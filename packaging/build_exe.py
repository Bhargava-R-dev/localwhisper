"""Build the bundled Windows executable with PyInstaller.

Run from the project root with the project's venv python:
    .\.venv\Scripts\python.exe packaging\build_exe.py

Steps:
1. Locate the cached faster-whisper small.en CTranslate2 model and copy it into
   packaging/_model/whisper-small.en (so PyInstaller can bundle it).
2. Run PyInstaller (one-folder) with the collectors/hidden-imports the ML stack needs.
Output: dist/LocalWhisper/LocalWhisper.exe (plus dist/LocalWhisper/_internal/...).
"""
import glob
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_STAGE = os.path.join(ROOT, "packaging", "_model", "whisper-small.en")
HF_HUB = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")


def stage_whisper_model():
    """Copy the small.en CT2 model files from the HF cache into the staging dir."""
    pattern = os.path.join(
        HF_HUB, "models--Systran--faster-whisper-small.en", "snapshots", "*"
    )
    snapshots = [p for p in glob.glob(pattern) if os.path.isdir(p)]
    if not snapshots:
        sys.exit(
            "small.en model not found in HF cache. Run once from source first:\n"
            '  .\\.venv\\Scripts\\python.exe -c "from faster_whisper import WhisperModel; '
            "WhisperModel('small.en', device='cpu', compute_type='int8')\""
        )
    snapshot = snapshots[0]
    if os.path.isdir(MODEL_STAGE):
        shutil.rmtree(MODEL_STAGE)
    os.makedirs(MODEL_STAGE)
    copied = []
    for name in os.listdir(snapshot):
        src = os.path.join(snapshot, name)
        # Resolve through the blob (symlink or plain file) and copy the real bytes.
        real = os.path.realpath(src)
        if os.path.isfile(real):
            shutil.copy2(real, os.path.join(MODEL_STAGE, name))
            copied.append(name)
    print(f"Staged whisper model files: {copied}")
    if not any(n == "model.bin" for n in copied):
        sys.exit("model.bin missing after staging — aborting.")


def run_pyinstaller():
    add_data_sep = ";"  # Windows
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",                       # no console window (tray app)
        "--name", "LocalWhisper",
        "--collect-all", "faster_whisper",  # includes the bundled silero VAD asset
        "--collect-all", "onnxruntime",
        "--collect-all", "ctranslate2",
        "--collect-all", "openwakeword",    # bundles the wake-word ONNX models
        "--collect-all", "sounddevice",     # bundles the PortAudio DLL
        "--collect-all", "av",              # PyAV/ffmpeg, imported by faster-whisper
        "--hidden-import", "pystray._win32",
        "--hidden-import", "tkinter",       # overlay indicator (lazy-imported)
        "--hidden-import", "_tkinter",
        "--add-data", f"{MODEL_STAGE}{add_data_sep}models/whisper-small.en",
        "--add-data", f"{os.path.join(ROOT, 'tests', 'fixtures', 'jfk.wav')}{add_data_sep}selftest",
        os.path.join(ROOT, "run.py"),
    ]
    print("Running:", " ".join(args))
    subprocess.check_call(args, cwd=ROOT)


if __name__ == "__main__":
    stage_whisper_model()
    run_pyinstaller()
    print("\nBuild complete: dist/LocalWhisper/LocalWhisper.exe")
