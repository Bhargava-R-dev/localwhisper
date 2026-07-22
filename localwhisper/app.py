"""Wire everything together and run the IDLE <-> RECORDING state machine.

The main loop is crash-resilient: any error during a recording/transcribe/paste cycle
is logged and recovered from, so a single failure (e.g. the clipboard being briefly
locked) can never kill the hotkeys or wake word until the app is restarted.
"""
import os
import queue
import sys
import time
import traceback

import numpy as np

from localwhisper.config import load_config
from localwhisper.engine import WhisperEngine
from localwhisper.audio import Microphone
from localwhisper.wakeword import WakeWord
from localwhisper.endpointing import Endpointer
from localwhisper.triggers import HotkeyListener, Event
from localwhisper.inject import paste_at_cursor
from localwhisper.tray import TrayIcon
from localwhisper.overlay import Overlay
from localwhisper.recording import record_frames

_READ_TIMEOUT = 0.05   # seconds per record-loop iteration when no frame is ready


def _frames_to_float(frames):
    """List of int16 frames -> float32 mono in [-1, 1] for whisper."""
    if not frames:
        return np.zeros(0, dtype="float32")
    return np.concatenate(frames).astype("float32") / 32768.0


def _status(msg: str):
    """Print to the console if one exists; always mirror to the log file.

    A gui-scripts / pythonw launch has no console, so sys.stdout is None there and a
    bare print() would crash on startup. This is safe in that case and still gives
    normal console output when run from a real terminal (e.g. python -m localwhisper.app).
    """
    if sys.stdout is not None:
        try:
            print(msg)
        except Exception:
            pass
    _log(msg)


def _log(msg: str):
    """Append a line to the log file; never raises."""
    try:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        folder = os.path.join(base, "LocalWhisper")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "localwhisper.log"), "a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except Exception:
        pass


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
        self.overlay = Overlay(self.cfg.show_overlay)
        self._running = True
        fps = self.cfg.sample_rate / self.cfg.frame_len            # frames per second
        self._wake_cap = int(self.cfg.max_record_ms / 1000 * fps)   # hands-free safety cap
        self._hold_cap = int(self.cfg.max_hold_ms / 1000 * fps)     # push-to-talk runaway guard
        # loop iterates every _READ_TIMEOUT seconds when idle of frames:
        self._stall_iters = int(3.0 / _READ_TIMEOUT)               # ~3 s with no audio => stalled
        self._hold_release_iters = 1                               # release is a reliable event -> stop at once

    # ---- lifecycle ----
    def start(self):
        _status("LocalWhisper starting (loading model)...")
        self.engine = WhisperEngine(self.cfg)   # warm model load
        self.mic.start()
        self.hotkeys.start()
        self.tray.start()
        self.overlay.start()
        _status("Ready. Ctrl+B (hold), Alt+N (toggle), or say the wake word.")
        self._loop()

    def quit(self):
        self._running = False

    # ---- main loop ----
    def _loop(self):
        while self._running:
            try:
                self._tick()
            except Exception:
                # A recording cycle failed (clipboard locked, transcribe error, etc.).
                # Log it, return to a clean idle state, and KEEP LISTENING.
                _log("recording cycle error:\n" + traceback.format_exc())
                self._recover_idle()
        self._shutdown()

    def _tick(self):
        try:
            frame = self.mic.read(timeout=0.5)
        except queue.Empty:
            self._drain_events()
            return
        evt = self._next_event()
        if evt == Event.HOLD_START:
            self._record("hold")
        elif evt == Event.TOGGLE:
            self._record("toggle")
        elif self.wake.detect(frame):
            self._record("wake")

    def _record(self, mode: str):
        cap = self._wake_cap if mode == "wake" else self._hold_cap
        self.tray.set_state("listening")
        self.overlay.listening()
        self.tray.beep_start()
        self.endpointer.reset()
        self.mic.drain()          # start from fresh audio (no stale/pre-trigger backlog)

        t0 = time.time()
        frames, reason = record_frames(
            mode,
            read_frame=lambda: self.mic.read_or_none(_READ_TIMEOUT),
            is_hold_down=self.hotkeys.hold_key_is_down,
            pop_toggle=self._pop_toggle,
            on_wake_frame=lambda f: self.endpointer.update(f.astype("float32") / 32768.0),
            max_frames=cap,
            stall_iters=self._stall_iters,
            hold_release_iters=self._hold_release_iters,
        )
        self.hotkeys.release_hold()   # guarantee the trigger key is unblocked
        secs = len(frames) * self.cfg.frame_len / self.cfg.sample_rate
        _log(f"[rec] mode={mode} reason={reason} frames={len(frames)} "
             f"audio={secs:.1f}s wall={time.time() - t0:.1f}s")
        if reason == "stall":
            _log(f"[warn] microphone stalled during '{mode}' recording — restarting stream")
            self._restart_mic()

        self.tray.beep_stop()
        self.tray.set_state("busy")
        self.overlay.busy()
        time.sleep(0.05)          # let the overlay repaint "Working" before transcription hogs the CPU
        audio = _frames_to_float(frames)
        text = self.engine.transcribe(audio) if len(frames) else ""
        if text:
            paste_at_cursor(text)
        self.mic.drain()
        self._flush_events()
        self.tray.set_state("idle")
        self.overlay.hide()

    def _pop_toggle(self) -> bool:
        """True (consuming the event) when the toggle hotkey was pressed again."""
        return self._next_event() == Event.TOGGLE

    def _restart_mic(self):
        """Recover from a stalled stream by reopening it. Swallows failures."""
        try:
            self.mic.stop()
        except Exception:
            pass
        try:
            self.mic.start()
        except Exception as exc:
            _log("[error] mic restart failed: " + repr(exc))

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

    def _recover_idle(self):
        """Return to a safe idle state after an error, swallowing further failures."""
        for action in (self.mic.drain, self._flush_events,
                       lambda: self.tray.set_state("idle"), self.overlay.hide):
            try:
                action()
            except Exception:
                pass

    def _shutdown(self):
        self.hotkeys.stop()
        self.mic.stop()
        self.tray.stop()
        _status("LocalWhisper stopped.")


def main():
    App().start()


if __name__ == "__main__":
    sys.exit(main())
