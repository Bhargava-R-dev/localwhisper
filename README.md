# LocalWhisper

Local, offline voice-to-text for Windows. Speak, and it types at your cursor.

## Triggers
- **Ctrl+B** — hold to talk (release to insert)
- **Alt+N** — tap to start, tap to stop
- **"Hey Jarvis"** — hands-free (swap the phrase in `localwhisper/config.py`)

## Setup
```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -c "import openwakeword.utils as u; u.download_models()"
```

## Run
```powershell
.\.venv\Scripts\python.exe -m localwhisper.app
```
First launch downloads the `small.en` model (~240 MB) once. A tray icon shows state:
grey = idle, green = recording, amber = transcribing.

## Notes
- If hotkeys don't fire, run the terminal **as Administrator** (Windows global-hook requirement).
- Tuning lives in `localwhisper/config.py`: `model_name` (`small.en` ↔ `base.en` for speed),
  `wakeword_threshold`, `endpoint_silence_ms`.

## Tests
```powershell
.\.venv\Scripts\python.exe -m pytest -v
```
