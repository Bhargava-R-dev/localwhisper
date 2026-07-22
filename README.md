# LocalWhisper 🎙️

**Local, offline voice-to-text for Windows.** Speak, and it types wherever your cursor is — in any app. No cloud, no account, no data leaves your PC.

Three ways to trigger it:

| Trigger | How | Best for |
|---|---|---|
| **Ctrl + B** | Hold and speak, release to insert | quick phrases (walkie-talkie) |
| **Alt + N** | Tap to start, tap again to stop | longer dictation (hands free) |
| **"Hey Jarvis"** | Say it, then speak | fully hands-free |

Powered by [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (`small.en` model) and [openWakeWord](https://github.com/dscripka/openWakeWord).

---

## Install (easiest — no Python needed)

1. Go to the [**Releases**](https://github.com/Bhargava-R-dev/localwhisper/releases) page and download **`LocalWhisper-Setup.zip`**.
2. **Extract** the ZIP (right-click → Extract All). Keep the folder structure.
3. Double-click **`Install.bat`** and approve the Windows admin prompt.

That's it. LocalWhisper installs, starts immediately, and **launches automatically every time you log in**. A small tray icon shows its state:

- ⚪ grey = idle &nbsp;&nbsp; 🟢 green = recording &nbsp;&nbsp; 🟠 amber = transcribing

Right-click the tray icon to **Quit**. To remove it later, run **`Uninstall.bat`**.

### First-launch notes
- **Windows SmartScreen** may show *"Windows protected your PC"* — this is expected for a new, unsigned app. Click **More info → Run anyway**.
- Administrator rights are required because global hotkeys (Ctrl+B / Alt+N) need a system-level keyboard hook. The installer sets this up for you.
- If nothing happens on launch, check the log at `%LOCALAPPDATA%\LocalWhisper\localwhisper.log`.
- Needs a 64-bit Windows 10/11 PC and a microphone. If the app won't start, install the [Microsoft Visual C++ Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe).

---

## Install via pip (for Python users)

If you already have **Python 3.9+**:

```bash
pip install localwhisper
localwhisper
```

On first run it downloads the `small.en` model (~240 MB) and the wake-word models automatically. Run your terminal **as Administrator** so the global hotkeys work.

---

## Tuning

Behavior lives in [`localwhisper/config.py`](localwhisper/config.py) (edit + rerun from source, or rebuild):

| Setting | Default | What it does |
|---|---|---|
| `model_name` | `small.en` | Transcription model. `base.en` is faster, less accurate. |
| `wakeword_model` | `hey_jarvis` | Also: `alexa`, `hey_mycroft`, `hey_rhasspy`. |
| `wakeword_threshold` | `0.5` | Lower = triggers more easily; raise if it false-fires. |
| `endpoint_silence_ms` | `1500` | Silence (ms) that ends a hands-free utterance. |
| `energy_threshold` | `0.01` | Loudness that counts as speech. |

---

## Build from source / run the tests

```powershell
git clone https://github.com/Bhargava-R-dev/localwhisper
cd localwhisper
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -c "import openwakeword.utils as u; u.download_models()"

# run from source
.\.venv\Scripts\python.exe -m localwhisper.app

# run the tests
.\.venv\Scripts\python.exe -m pytest -v
```

### Build the distributable EXE

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe packaging\build_exe.py
```

Output lands in `dist\LocalWhisper\`. See [`packaging/`](packaging/) for the installer scripts and how the release ZIP is assembled.

---

## How it works

One microphone stream feeds a small state machine. When idle it runs the wake-word
detector; the two hotkeys post events from a background thread. Any trigger records
audio, hands it to the warm whisper model, and pastes the result at the cursor via the
clipboard. Everything runs locally on CPU.

## License

[MIT](LICENSE)
