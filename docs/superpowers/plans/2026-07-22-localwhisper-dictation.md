# LocalWhisper Dictation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Windows background app that transcribes speech to text and pastes it at the cursor, triggered by Ctrl+B (hold), Alt+N (toggle), or the "Hey Jarvis" wake word.

**Architecture:** A single Python process owns one 16 kHz mic stream and runs a state machine (IDLE ↔ RECORDING). In IDLE it feeds mic frames to an openWakeWord detector; global hotkeys (via the `keyboard` library, running on their own thread) push events onto a queue. On any trigger it records audio, hands it to a warm faster-whisper model, and pastes the result at the cursor via the clipboard. A system-tray icon shows state.

**Tech Stack:** Python 3.12, faster-whisper (CTranslate2), sounddevice, openwakeword, keyboard, pyperclip, pystray/Pillow, winsound (stdlib), pytest.

**Project root:** `C:\Users\Laptop-577\localwhisper` (all paths below are relative to it).

---

## File Structure

```
localwhisper/
├── requirements.txt          # pinned dependencies
├── .gitignore                # venv, __pycache__, models
├── README.md                 # setup + run instructions
├── localwhisper/
│   ├── __init__.py
│   ├── config.py             # Config dataclass + defaults
│   ├── engine.py             # WhisperEngine (faster-whisper wrapper, warm model)
│   ├── inject.py             # paste_at_cursor (clipboard method)
│   ├── endpointing.py        # Endpointer (energy-based silence detection)
│   ├── audio.py              # Microphone (shared 16 kHz int16 stream)
│   ├── wakeword.py           # WakeWord (openWakeWord detector)
│   ├── triggers.py           # HotkeyListener (Ctrl+B hold / Alt+N toggle → event queue)
│   ├── tray.py               # TrayIcon (state indicator + quit) + beeps
│   └── app.py                # wiring + main state-machine loop
└── tests/
    ├── __init__.py
    ├── fixtures/jfk.wav       # copied from whisper.cpp samples (deterministic test audio)
    ├── test_config.py
    ├── test_engine.py
    ├── test_inject.py
    └── test_endpointing.py
```

**Responsibilities:** `config` = tunable settings in one place; `engine` = audio→text only; `inject` = text→cursor only; `endpointing` = "did the speaker stop?" pure logic; `audio` = mic frames; `wakeword` = "was the phrase said?"; `triggers` = keyboard→events; `tray` = user-visible state; `app` = orchestration. Files that change together stay together; each has one job.

---

## Task 0: Project scaffolding & dependencies

**Files:**
- Create: `requirements.txt`, `.gitignore`, `localwhisper/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Create `requirements.txt`**

```
faster-whisper>=1.0.0
sounddevice>=0.4.6
numpy>=1.24
keyboard>=0.13.5
openwakeword>=0.6.0
onnxruntime>=1.16
pyperclip>=1.8.2
pystray>=0.19
Pillow>=10.0
pytest>=8.0
```

- [ ] **Step 2: Create `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 3: Create empty package files**

Create `localwhisper/__init__.py` and `tests/__init__.py` as empty files.

- [ ] **Step 4: Create the virtual environment and install dependencies**

Run (PowerShell, from project root):
```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
Expected: all packages install without a compiler error (all are prebuilt wheels). This downloads ~200–400 MB.

- [ ] **Step 5: Download openWakeWord's base models**

Run:
```powershell
.\.venv\Scripts\python.exe -c "import openwakeword.utils as u; u.download_models()"
```
Expected: downloads the pretrained wake-word models (including `hey_jarvis`) into the openwakeword package data dir. No error.

- [ ] **Step 6: Copy the test audio fixture**

Run:
```powershell
New-Item -ItemType Directory -Force tests\fixtures | Out-Null
Copy-Item "C:\Users\Laptop-577\whisper.cpp\samples\jfk.wav" tests\fixtures\jfk.wav
```
Expected: `tests/fixtures/jfk.wav` exists.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt .gitignore localwhisper/__init__.py tests/__init__.py tests/fixtures/jfk.wav
git commit -m "chore: scaffold project, deps, and test fixture"
```

---

## Task 1: Config module

**Files:**
- Create: `localwhisper/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
from localwhisper.config import Config, load_config


def test_defaults_match_spec():
    c = load_config()
    assert isinstance(c, Config)
    assert c.model_name == "small.en"
    assert c.language == "en"
    assert c.sample_rate == 16000
    assert c.frame_len == 1280            # 80 ms @ 16 kHz
    assert c.hold_hotkey == "ctrl+b"
    assert c.toggle_hotkey == "alt+n"
    assert c.wakeword_model == "hey_jarvis"
    assert 0.0 < c.wakeword_threshold < 1.0
    assert c.endpoint_silence_ms == 1500
    assert c.max_record_ms == 15000
    assert c.compute_type == "int8"
    assert c.beep is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'localwhisper.config'`

- [ ] **Step 3: Write minimal implementation**

`localwhisper/config.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add localwhisper/config.py tests/test_config.py
git commit -m "feat: add Config with spec defaults"
```

---

## Task 2: Whisper engine (warm faster-whisper wrapper)

**Files:**
- Create: `localwhisper/engine.py`
- Test: `tests/test_engine.py`

- [ ] **Step 1: Write the failing test**

The test uses `tiny.en` for speed (small download); it exercises the wrapper, not model quality. Production uses `small.en` via config. `decode_audio` loads the WAV to the float32 mono 16 kHz array the engine expects.

`tests/test_engine.py`:
```python
from dataclasses import replace
from faster_whisper.audio import decode_audio
from localwhisper.config import load_config
from localwhisper.engine import WhisperEngine


def test_transcribes_known_audio():
    cfg = replace(load_config(), model_name="tiny.en")  # fast model for the test
    engine = WhisperEngine(cfg)
    audio = decode_audio("tests/fixtures/jfk.wav", sampling_rate=cfg.sample_rate)
    text = engine.transcribe(audio)
    assert "country" in text.lower()


def test_blank_audio_returns_empty():
    import numpy as np
    cfg = replace(load_config(), model_name="tiny.en")
    engine = WhisperEngine(cfg)
    silence = np.zeros(cfg.sample_rate, dtype="float32")  # 1 s of silence
    assert engine.transcribe(silence).strip() == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'localwhisper.engine'`

- [ ] **Step 3: Write minimal implementation**

`localwhisper/engine.py`:
```python
"""Wraps faster-whisper. Loads the model once and keeps it warm in RAM."""
import numpy as np
from faster_whisper import WhisperModel


class WhisperEngine:
    def __init__(self, config):
        self.language = config.language
        self.model = WhisperModel(
            config.model_name,
            device=config.device,
            compute_type=config.compute_type,
        )

    def transcribe(self, audio: np.ndarray) -> str:
        """audio: float32 mono @ 16 kHz in [-1, 1]. Returns stripped text."""
        audio = np.asarray(audio, dtype="float32")
        segments, _ = self.model.transcribe(
            audio,
            language=self.language,
            beam_size=5,
            vad_filter=True,          # drops leading/trailing non-speech
            condition_on_previous_text=False,
        )
        return " ".join(s.text.strip() for s in segments).strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_engine.py -v`
Expected: PASS (first run downloads `tiny.en`, a few seconds).

- [ ] **Step 5: Commit**

```bash
git add localwhisper/engine.py tests/test_engine.py
git commit -m "feat: add warm faster-whisper transcription engine"
```

---

## Task 3: Text injection (clipboard paste at cursor)

**Files:**
- Create: `localwhisper/inject.py`
- Test: `tests/test_inject.py`

- [ ] **Step 1: Write the failing test**

`tests/test_inject.py`:
```python
from localwhisper import inject


class FakeClip:
    def __init__(self, initial=""):
        self.value = initial

    def paste(self):
        return self.value

    def copy(self, v):
        self.value = v


def test_pastes_text_then_restores_clipboard():
    clip = FakeClip("original")
    seen = {}

    def fake_paste():
        seen["at_paste"] = clip.value   # what was on the clipboard when Ctrl+V fired

    inject.paste_at_cursor(
        "hello world", paste_fn=fake_paste, clipboard=clip, sleep=lambda _s: None
    )

    assert seen["at_paste"] == "hello world"   # text was on clipboard at paste time
    assert clip.value == "original"            # original clipboard restored afterward


def test_blank_text_is_a_noop():
    clip = FakeClip("original")
    called = []
    inject.paste_at_cursor(
        "   ", paste_fn=lambda: called.append(1), clipboard=clip, sleep=lambda _s: None
    )
    assert called == []
    assert clip.value == "original"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_inject.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'localwhisper.inject'`

- [ ] **Step 3: Write minimal implementation**

`localwhisper/inject.py`:
```python
"""Paste text at the cursor via the clipboard (reliable across all apps)."""
import time
import pyperclip
import keyboard


def _default_paste():
    keyboard.send("ctrl+v")


def paste_at_cursor(text: str, paste_fn=None, clipboard=pyperclip, sleep=time.sleep):
    """Save clipboard → put text → Ctrl+V → restore clipboard. No-op on blank text."""
    if not text or not text.strip():
        return
    paste_fn = paste_fn or _default_paste

    try:
        saved = clipboard.paste()
    except Exception:
        saved = ""

    clipboard.copy(text)
    sleep(0.05)          # let the OS register the new clipboard contents
    paste_fn()
    sleep(0.10)          # let the target app read the clipboard before we restore
    try:
        clipboard.copy(saved)
    except Exception:
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_inject.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add localwhisper/inject.py tests/test_inject.py
git commit -m "feat: add clipboard-based paste-at-cursor"
```

---

## Task 4: Endpointing (energy-based silence detection)

**Files:**
- Create: `localwhisper/endpointing.py`
- Test: `tests/test_endpointing.py`

- [ ] **Step 1: Write the failing test**

`tests/test_endpointing.py`:
```python
import numpy as np
from localwhisper.endpointing import Endpointer


def _loud(n):
    return np.full(n, 0.2, dtype="float32")   # RMS 0.2 > threshold


def _quiet(n):
    return np.zeros(n, dtype="float32")        # RMS 0 < threshold


def test_fires_after_silence_following_speech():
    ep = Endpointer(sample_rate=16000, silence_ms=1500, energy_threshold=0.01, frame_ms=80)
    n = 1280  # 80 ms

    # 3 speech frames — must not fire yet
    assert not any(ep.update(_loud(n)) for _ in range(3))

    # silence_ms / frame_ms = 1500/80 = 18.75 -> 19 silent frames needed
    fired = [ep.update(_quiet(n)) for _ in range(19)]
    assert fired[-1] is True          # fires on the 19th silent frame
    assert not any(fired[:18])        # not before


def test_does_not_fire_without_prior_speech():
    ep = Endpointer(sample_rate=16000, silence_ms=1500, energy_threshold=0.01, frame_ms=80)
    n = 1280
    assert not any(ep.update(_quiet(n)) for _ in range(50))  # pure silence never ends


def test_reset_clears_state():
    ep = Endpointer(sample_rate=16000, silence_ms=1500, energy_threshold=0.01, frame_ms=80)
    n = 1280
    ep.update(_loud(n))
    ep.reset()
    assert not any(ep.update(_quiet(n)) for _ in range(50))  # speech was forgotten
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_endpointing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'localwhisper.endpointing'`

- [ ] **Step 3: Write minimal implementation**

`localwhisper/endpointing.py`:
```python
"""Decide when the speaker has stopped, for the hands-free path."""
import math
import numpy as np


class Endpointer:
    def __init__(self, sample_rate=16000, silence_ms=1500, energy_threshold=0.01, frame_ms=80):
        self.energy_threshold = energy_threshold
        self.silence_frames_needed = math.ceil(silence_ms / frame_ms)
        self.reset()

    def reset(self):
        self.had_speech = False
        self.silent_frames = 0

    def update(self, frame: np.ndarray) -> bool:
        """Feed one audio frame (float32). Returns True once the endpoint is reached."""
        frame = np.asarray(frame, dtype="float32")
        rms = float(np.sqrt(np.mean(frame ** 2))) if frame.size else 0.0
        if rms >= self.energy_threshold:
            self.had_speech = True
            self.silent_frames = 0
        else:
            self.silent_frames += 1
        return self.had_speech and self.silent_frames >= self.silence_frames_needed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_endpointing.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add localwhisper/endpointing.py tests/test_endpointing.py
git commit -m "feat: add energy-based endpointer for hands-free recording"
```

---

## Task 5: Microphone (shared 16 kHz int16 stream)

Not unit-tested (requires hardware). Verified by a manual smoke test at the end of this task.

**Files:**
- Create: `localwhisper/audio.py`

- [ ] **Step 1: Write the implementation**

`localwhisper/audio.py`:
```python
"""One shared microphone input stream producing fixed-size int16 frames."""
import queue
import numpy as np
import sounddevice as sd


class Microphone:
    def __init__(self, sample_rate=16000, frame_len=1280):
        self.sample_rate = sample_rate
        self.frame_len = frame_len
        self._q: "queue.Queue[np.ndarray]" = queue.Queue()
        self._stream = None

    def _callback(self, indata, frames, time_info, status):
        # indata: int16 shape (frame_len, 1) -> flatten to (frame_len,)
        self._q.put(indata[:, 0].copy())

    def start(self):
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            blocksize=self.frame_len,
            channels=1,
            dtype="int16",
            callback=self._callback,
        )
        self._stream.start()

    def read(self, timeout=1.0) -> np.ndarray:
        """Return the next int16 frame, or raise queue.Empty after timeout."""
        return self._q.get(timeout=timeout)

    def drain(self):
        """Discard any buffered frames (call after a recording ends)."""
        try:
            while True:
                self._q.get_nowait()
        except queue.Empty:
            pass

    def stop(self):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
```

- [ ] **Step 2: Manual smoke test**

Create a throwaway check and run it:
```powershell
.\.venv\Scripts\python.exe -c "from localwhisper.audio import Microphone; m=Microphone(); m.start(); import numpy as np; f=m.read(); print('frame', f.shape, f.dtype, 'peak', int(np.abs(f).max())); m.stop()"
```
Speak while it runs. Expected: prints `frame (1280,) int16 peak <n>` with a non-trivial peak (e.g. > 200). If `peak` stays ~0, the wrong input device is default — note it; we surface device selection later if needed.

- [ ] **Step 3: Commit**

```bash
git add localwhisper/audio.py
git commit -m "feat: add shared microphone stream"
```

---

## Task 6: Hotkey triggers (Ctrl+B hold / Alt+N toggle)

Not unit-tested (global keyboard hooks need a real session). Verified by manual smoke test.

**Files:**
- Create: `localwhisper/triggers.py`

- [ ] **Step 1: Write the implementation**

`localwhisper/triggers.py`:
```python
"""Global hotkeys -> events on a shared queue. Runs on the keyboard lib's thread."""
import queue
from enum import Enum, auto
import keyboard


class Event(Enum):
    HOLD_START = auto()   # Ctrl+B pressed: begin walkie-talkie recording
    TOGGLE = auto()       # Alt+N tapped: start or stop toggle recording


class HotkeyListener:
    def __init__(self, config, event_queue: "queue.Queue[Event]"):
        self.hold_hotkey = config.hold_hotkey
        self.toggle_hotkey = config.toggle_hotkey
        self.events = event_queue
        self._handles = []

    def start(self):
        # Fire HOLD_START on key-down (not release) so we can record while held.
        self._handles.append(
            keyboard.add_hotkey(
                self.hold_hotkey,
                lambda: self.events.put(Event.HOLD_START),
                trigger_on_release=False,
            )
        )
        self._handles.append(
            keyboard.add_hotkey(
                self.toggle_hotkey,
                lambda: self.events.put(Event.TOGGLE),
            )
        )

    def hold_key_is_down(self) -> bool:
        """True while the hold combo is physically pressed (drives walkie-talkie stop)."""
        return keyboard.is_pressed(self.hold_hotkey)

    def stop(self):
        for h in self._handles:
            keyboard.remove_hotkey(h)
        self._handles.clear()
```

- [ ] **Step 2: Manual smoke test**

```powershell
.\.venv\Scripts\python.exe -c "import queue; from localwhisper.config import load_config; from localwhisper.triggers import HotkeyListener, Event; q=queue.Queue(); h=HotkeyListener(load_config(), q); h.start(); print('Press Ctrl+B then Alt+N within 15s...'); import time; end=time.time()+15
while time.time()<end:
    try: print('got', q.get(timeout=1))
    except queue.Empty: pass
h.stop()"
```
Expected: pressing Ctrl+B prints `got Event.HOLD_START`, Alt+N prints `got Event.TOGGLE`. If nothing prints, re-run the terminal **as Administrator** (the `keyboard` lib needs elevation for global hooks on some Windows setups) — record this finding for the README.

- [ ] **Step 3: Commit**

```bash
git add localwhisper/triggers.py
git commit -m "feat: add global hotkey listener (Ctrl+B hold, Alt+N toggle)"
```

---

## Task 7: Wake word (openWakeWord detector)

Not unit-tested (needs the ONNX model + live audio). Verified by manual smoke test.

**Files:**
- Create: `localwhisper/wakeword.py`

- [ ] **Step 1: Write the implementation**

`localwhisper/wakeword.py`:
```python
"""openWakeWord detector. Feed int16 frames; returns True when the phrase is heard."""
import numpy as np
from openwakeword.model import Model


class WakeWord:
    def __init__(self, config):
        self.name = config.wakeword_model
        self.threshold = config.wakeword_threshold
        self.model = Model(
            wakeword_models=[self.name],
            inference_framework="onnx",
        )

    def detect(self, frame_int16: np.ndarray) -> bool:
        """frame_int16: 1280-sample int16 frame. True once the phrase crosses threshold."""
        scores = self.model.predict(np.asarray(frame_int16, dtype="int16"))
        if scores.get(self.name, 0.0) >= self.threshold:
            self.model.reset()   # avoid immediate re-trigger on the same utterance
            return True
        return False
```

- [ ] **Step 2: Manual smoke test**

```powershell
.\.venv\Scripts\python.exe -c "from localwhisper.config import load_config; from localwhisper.audio import Microphone; from localwhisper.wakeword import WakeWord; c=load_config(); m=Microphone(c.sample_rate,c.frame_len); w=WakeWord(c); m.start(); print('Say: Hey Jarvis (20s window)...'); import time; end=time.time()+20
while time.time()<end:
    if w.detect(m.read()): print('DETECTED'); break
m.stop()"
```
Expected: saying "Hey Jarvis" prints `DETECTED`. If it never fires, lower `wakeword_threshold` toward 0.3 in config; if it false-fires, raise it. Record the value that works.

- [ ] **Step 3: Commit**

```bash
git add localwhisper/wakeword.py
git commit -m "feat: add openWakeWord detector"
```

---

## Task 8: Tray icon + beeps

Not unit-tested (UI). Verified visually in the final app run.

**Files:**
- Create: `localwhisper/tray.py`

- [ ] **Step 1: Write the implementation**

`localwhisper/tray.py`:
```python
"""System-tray state indicator + short audible cues (winsound is stdlib on Windows)."""
import threading
import winsound
import pystray
from PIL import Image


_COLORS = {
    "idle": (90, 90, 90),        # grey
    "listening": (40, 160, 40),  # green (recording)
    "busy": (200, 140, 0),       # amber (transcribing)
}


def _icon_image(color):
    img = Image.new("RGB", (64, 64), color)
    return img


class TrayIcon:
    def __init__(self, on_quit, enable_beep=True):
        self.enable_beep = enable_beep
        self._icon = pystray.Icon(
            "LocalWhisper",
            _icon_image(_COLORS["idle"]),
            "LocalWhisper (idle)",
            menu=pystray.Menu(pystray.MenuItem("Quit", lambda: on_quit())),
        )

    def start(self):
        threading.Thread(target=self._icon.run, daemon=True).start()

    def set_state(self, state: str):
        self._icon.icon = _icon_image(_COLORS.get(state, _COLORS["idle"]))
        self._icon.title = f"LocalWhisper ({state})"

    def beep_start(self):
        if self.enable_beep:
            winsound.Beep(880, 120)

    def beep_stop(self):
        if self.enable_beep:
            winsound.Beep(440, 120)

    def stop(self):
        self._icon.stop()
```

- [ ] **Step 2: Commit**

```bash
git add localwhisper/tray.py
git commit -m "feat: add tray state indicator and beeps"
```

---

## Task 9: App wiring + main state-machine loop

**Files:**
- Create: `localwhisper/app.py`

- [ ] **Step 1: Write the implementation**

`localwhisper/app.py`:
```python
"""Wire everything together and run the IDLE <-> RECORDING state machine."""
import queue
import sys
import numpy as np

from localwhisper.config import load_config
from localwhisper.engine import WhisperEngine
from localwhisper.audio import Microphone
from localwhisper.wakeword import WakeWord
from localwhisper.endpointing import Endpointer
from localwhisper.triggers import HotkeyListener, Event
from localwhisper.inject import paste_at_cursor
from localwhisper.tray import TrayIcon


def _frames_to_float(frames):
    """List of int16 frames -> float32 mono in [-1, 1] for whisper."""
    if not frames:
        return np.zeros(0, dtype="float32")
    return np.concatenate(frames).astype("float32") / 32768.0


class App:
    def __init__(self):
        self.cfg = load_config()
        self.events: "queue.Queue[Event]" = queue.Queue()
        self.mic = Microphone(self.cfg.sample_rate, self.cfg.frame_len)
        self.wake = WakeWord(self.cfg)
        self.hotkeys = HotkeyListener(self.cfg, self.events)
        self.endpointer = Endpointer(
            self.cfg.sample_rate, self.cfg.endpoint_silence_ms,
            self.cfg.energy_threshold, frame_ms=1000 * self.cfg.frame_len // self.cfg.sample_rate,
        )
        self.tray = TrayIcon(self.quit, self.cfg.beep)
        self._running = True
        self._max_frames = self.cfg.max_record_ms * self.cfg.sample_rate // 1000 // self.cfg.frame_len

    # ---- lifecycle ----
    def start(self):
        print("LocalWhisper starting (loading model)...")
        self.engine = WhisperEngine(self.cfg)   # warm model load
        self.mic.start()
        self.hotkeys.start()
        self.tray.start()
        print("Ready. Ctrl+B (hold), Alt+N (toggle), or say the wake word.")
        self._loop()

    def quit(self):
        self._running = False

    # ---- main loop ----
    def _loop(self):
        while self._running:
            try:
                frame = self.mic.read(timeout=0.5)
            except queue.Empty:
                self._drain_events()
                continue

            evt = self._next_event()
            if evt == Event.HOLD_START:
                self._record("hold")
            elif evt == Event.TOGGLE:
                self._record("toggle")
            elif self.wake.detect(frame):
                self._record("wake")

        self._shutdown()

    def _record(self, mode: str):
        self.tray.set_state("listening")
        self.tray.beep_start()
        frames = []
        self.endpointer.reset()

        while self._running and len(frames) < self._max_frames:
            try:
                frame = self.mic.read(timeout=0.5)
            except queue.Empty:
                continue
            frames.append(frame)

            if mode == "hold" and not self.hotkeys.hold_key_is_down():
                break
            if mode == "toggle" and self._next_event() == Event.TOGGLE:
                break
            if mode == "wake":
                f32 = frame.astype("float32") / 32768.0
                if self.endpointer.update(f32):
                    break

        self.tray.beep_stop()
        self.tray.set_state("busy")
        audio = _frames_to_float(frames)
        text = self.engine.transcribe(audio)
        if text:
            paste_at_cursor(text)
        self.mic.drain()
        self._flush_events()
        self.tray.set_state("idle")

    # ---- event helpers ----
    def _next_event(self):
        try:
            return self.events.get_nowait()
        except queue.Empty:
            return None

    def _drain_events(self):
        self._next_event()

    def _flush_events(self):
        while self._next_event() is not None:
            pass

    def _shutdown(self):
        self.hotkeys.stop()
        self.mic.stop()
        self.tray.stop()
        print("LocalWhisper stopped.")


def main():
    App().start()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Full manual acceptance test**

Run:
```powershell
.\.venv\Scripts\python.exe -m localwhisper.app
```
Wait for `Ready.`, then verify each trigger by placing the cursor in Notepad:
1. **Ctrl+B hold:** hold Ctrl+B, say "hello world", release. Expected: "hello world" appears at the cursor; green→amber→grey tray; two beeps.
2. **Alt+N toggle:** tap Alt+N, say "this is a test", tap Alt+N. Expected: text appears.
3. **Wake word:** say "Hey Jarvis", then "open the door". Expected: after a pause, "open the door" appears.
4. **Quit:** right-click tray icon → Quit. Expected: process exits cleanly.

If a trigger misbehaves, adjust the matching config value (`wakeword_threshold`, `energy_threshold`, `endpoint_silence_ms`) and re-run.

- [ ] **Step 3: Commit**

```bash
git add localwhisper/app.py
git commit -m "feat: wire app together with IDLE/RECORDING state machine"
```

---

## Task 10: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write the README**

`README.md`:
```markdown
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
```

- [ ] **Step 2: Run the full test suite**

Run: `.\.venv\Scripts\python.exe -m pytest -v`
Expected: all tests in `test_config.py`, `test_engine.py`, `test_inject.py`, `test_endpointing.py` PASS.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add README with setup and usage"
```

---

## Done

The app now supports all three triggers feeding one transcribe→paste pipeline, runs fully locally, and has unit coverage on the pure-logic units (config, engine, inject, endpointing) plus documented manual smoke tests for the hardware/UI units (audio, hotkeys, wakeword, tray, app).

**Follow-ups (deferred, per spec):** train a custom "Hey PC" openWakeWord model; add run-on-login; package as a single `.exe`.
