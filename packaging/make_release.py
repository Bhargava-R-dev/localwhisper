"""Assemble the shareable release ZIP.

Run AFTER packaging/build_exe.py, from the project root:
    .\.venv\Scripts\python.exe packaging\make_release.py

Produces dist/LocalWhisper-Setup.zip containing:
    LocalWhisper-Setup/
        LocalWhisper/        (the built app: exe + _internal + bundled models)
        Install.bat
        Uninstall.bat
        README.txt
Users extract it and double-click Install.bat.
"""
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_APP = os.path.join(ROOT, "dist", "LocalWhisper")
INSTALLER = os.path.join(ROOT, "packaging", "installer")
STAGE = os.path.join(ROOT, "dist", "LocalWhisper-Setup")
ZIP_BASE = os.path.join(ROOT, "dist", "LocalWhisper-Setup")

README_TXT = """LocalWhisper — local, offline voice-to-text for Windows
========================================================

TO INSTALL:
  1. Keep this whole folder together (do not move Install.bat out).
  2. Double-click Install.bat and approve the admin prompt.

It installs, starts now, and auto-starts every time you log in.

HOW TO USE (put your cursor where you want text to appear):
  - Hold  Ctrl+B   and speak, release to insert
  - Tap   Alt+N    to start, tap again to stop
  - Say   "Hey Jarvis"  then speak (hands-free)

A tray icon shows state (grey=idle, green=recording, amber=working).
Right-click it to Quit.

NOTE: Windows SmartScreen may warn ("Windows protected your PC") because
this app is new and unsigned. Click "More info" -> "Run anyway".

TO REMOVE: double-click Uninstall.bat.
"""


def main():
    if not os.path.isfile(os.path.join(DIST_APP, "LocalWhisper.exe")):
        raise SystemExit("dist/LocalWhisper/LocalWhisper.exe not found — run build_exe.py first.")

    if os.path.isdir(STAGE):
        shutil.rmtree(STAGE)
    os.makedirs(STAGE)

    print("Copying app...")
    shutil.copytree(DIST_APP, os.path.join(STAGE, "LocalWhisper"))
    for bat in ("Install.bat", "Uninstall.bat"):
        # Batch files must use CRLF line endings to be safe on cmd.exe.
        with open(os.path.join(INSTALLER, bat), "r", encoding="utf-8") as fh:
            text = fh.read().replace("\r\n", "\n").replace("\n", "\r\n")
        with open(os.path.join(STAGE, bat), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    with open(os.path.join(STAGE, "README.txt"), "w", encoding="utf-8") as fh:
        fh.write(README_TXT)

    print("Zipping...")
    if os.path.isfile(ZIP_BASE + ".zip"):
        os.remove(ZIP_BASE + ".zip")
    shutil.make_archive(ZIP_BASE, "zip", root_dir=os.path.join(ROOT, "dist"), base_dir="LocalWhisper-Setup")

    size_mb = os.path.getsize(ZIP_BASE + ".zip") / (1024 * 1024)
    print(f"\nDone: dist/LocalWhisper-Setup.zip ({size_mb:.0f} MB)")


if __name__ == "__main__":
    main()
