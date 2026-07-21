# LocalWhisper — Local Voice-to-Text Dictation App

**Date:** 2026-07-22
**Status:** Design approved (pending spec review)

## Summary

A local, always-running Windows background app that turns speech into text and
types it wherever the cursor is — comparable to Wispr Flow. Three triggers feed
one shared pipeline:

- **Ctrl+B** — hold (walkie-talkie): record while held, transcribe on release.
- **Alt+N** — toggle: tap to start, tap again to stop and transcribe.
- **"Hey PC"** — hands-free wake word: detect the phrase, record until you stop
  talking, transcribe.

All three do the same thing: **record → transcribe → paste at cursor.** No AI
assistant, no command execution — pure dictation. Runs 100% locally.

## Decisions (locked)

| Area | Decision | Rationale |
|---|---|---|
| Architecture | Python background/tray app | Fastest to build, easy to iterate, all triggers share one codebase. |
| Transcription engine | **faster-whisper** (CTranslate2) | Pure `pip install`, no C++ compiler/build needed; prebuilt wheels; strong CPU performance; same OpenAI Whisper models. |
| Model | English-only **`small.en`** | User prioritizes quality; `small.en` is noticeably more accurate than `base.en` and remains workable on the target CPU for push-to-talk. |
| Warm model | Model loaded once, kept in RAM | Avoids per-utterance reload latency; snappy dictation. |
| Ctrl+B | Hold / walkie-talkie | User preference. |
| Alt+N | Toggle on/off | User preference. |
| Wake word | **openWakeWord**, ready-made phrase first | Fully offline + open source. Custom "Hey PC" model deferred to a later step. |
| Text injection | Clipboard paste (save → set → Ctrl+V → restore) | Most reliable across all apps (Word, browser, terminal, chat). |
| Feedback | System-tray icon + optional beeps | Clear recording state, low intrusion. |

### Target machine
- CPU: Intel i5-10210U (4c/8t, low-power laptop)
- GPU: Intel UHD (integrated) → CPU inference
- RAM: 16 GB
- OS: Windows 10 Pro
- Python: 3.12.10 (installed)

Push-to-talk (record-then-transcribe) rather than live streaming, so real-time
throughput is not required — a short sentence transcribing in ~1–2 s is the goal.

## Architecture

Isolated single-purpose components communicating through well-defined interfaces:

1. **`config`** — Loads settings from a single editable file: model name/size,
   hotkey bindings, wake-word phrase + sensitivity, injection method, endpoint
   silence timeout, beep on/off. One place to tweak behavior.

2. **`engine`** — Wraps faster-whisper. Loads the model once on startup and keeps
   it warm. Interface: `transcribe(audio: np.ndarray) -> str`. No knowledge of
   triggers or injection.

3. **`audio`** — Owns a single 16 kHz mono microphone input stream (sounddevice).
   Two modes: (a) *idle* — streams frames to the wake-word listener; (b)
   *recording* — buffers frames for the engine. Guarantees only one consumer at a
   time so triggers never fight over the mic.

4. **`triggers`** — Three producers, one internal command queue:
   - **Hotkey listener** (`keyboard` lib): Ctrl+B key-down → start-hold-recording,
     key-up → stop; Alt+N press → toggle recording state.
   - **Wake-word listener** (openWakeWord, background thread): consumes idle mic
     frames; on detection, starts a recording session with silence endpointing.
   - Emits a uniform `StartRecording(mode)` / `StopRecording` signal set.

5. **`endpointing`** — For the hands-free path only: detects end of speech via
   energy/VAD. Stops recording after ~1.5 s of trailing silence; hard cap ~15 s.
   (Hotkey paths are bounded by the key, so they skip this.)

6. **`inject`** — Pastes text at the cursor using the clipboard method: read and
   stash current clipboard, set clipboard to transcribed text, send Ctrl+V, then
   restore the original clipboard after a short delay. Interface:
   `paste_at_cursor(text: str)`.

7. **`tray`** — pystray system-tray icon reflecting state (idle / listening /
   transcribing), a quit item, and optional short start/stop beeps.

8. **`app`** — Wires everything: builds config, loads engine, starts audio +
   listeners, consumes the command queue, orchestrates
   record → transcribe → paste.

## Control flow

```
idle → wake-word listener running on shared mic stream
  │
  ├─ Ctrl+B held ─────► record while held ──────────┐
  ├─ Alt+N tapped ────► record until re-tap ────────┼─► engine.transcribe (warm)
  └─ "Hey PC" heard ──► record until trailing silence ┘        │
                                                               ▼
                                          inject.paste_at_cursor(text) → idle
```

Invariants:
- Exactly one recording session active at a time.
- Wake-word detection is paused while a recording session is active, then resumed.
- Empty/whitespace-only transcriptions are dropped (no paste).

## Dependencies

- `faster-whisper` — transcription
- `sounddevice` (+ `numpy`) — mic capture
- `keyboard` — global hotkeys (Ctrl+B / Alt+N)
- `openwakeword` — wake-word detection
- `pyperclip` — clipboard get/set
- `pystray` + `Pillow` — tray icon
- (optional) `webrtcvad` — better endpointing than raw energy threshold

No C++ build step. `keyboard` may require running the app as Administrator on
Windows for global hotkeys to work system-wide — to be confirmed during
implementation.

## Testing

- **`engine`** — unit test: transcribe a bundled sample WAV, assert expected text.
- **`inject`** — unit test: round-trip clipboard save/set/restore (mock the paste
  keystroke).
- **`endpointing`** — unit test: feed synthetic audio (speech then silence),
  assert stop fires at the right frame.
- **`triggers`** — manual smoke test (global hotkeys and mic can't be unit-tested
  headlessly).

## Out of scope (YAGNI / deferred)

- AI question-answering or command execution ("Just dictate" was chosen).
- Custom "Hey PC" wake-word model (start with a ready-made phrase; train later).
- Multilingual transcription (English-only).
- GPU acceleration (CPU is adequate for push-to-talk).
- Auto-start on Windows login, installer/packaging (can add once it's proven).

## Open items to resolve during implementation

- Confirm whether `keyboard` needs Administrator elevation on this machine.
- Pick the default ready-made openWakeWord phrase (e.g. "Hey Jarvis") and expose
  it in config so it's easy to swap.
- Default model is `small.en` (quality priority). If a sentence feels too slow to
  transcribe on this CPU, `base.en` is a one-line config fallback.
