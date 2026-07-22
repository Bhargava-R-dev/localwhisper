"""Wire everything together and run the IDLE <-> RECORDING state machine.

The main loop is crash-resilient: any error during a recording/transcribe/paste cycle
is logged and recovered from, so a single failure (e.g. the clipboard being briefly
locked) can never kill the hotkeys or wake word until the app is restarted.
"""
import os
import queue
import sys
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


def _frames_to_float(frames):
    """List of int16 frames -> float32 mono in [-1, 1] for whisper."""
    if not frames:
        return np.zeros(0, dtype="float32")
    return np.concatenate(frames).astype("float32") / 32768.0


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

    # ---- lifecycle ----
    def start(self):
        print("LocalWhisper starting (loading model)...")
        self.engine = WhisperEngine(self.cfg)   # warm model load
        self.mic.start()
        self.hotkeys.start()
        self.tray.start()
        self.overlay.start()
        print("Ready. Ctrl+B (hold), Alt+N (toggle), or say the wake word.")
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
        frames = []
        self.endpointer.reset()

        while self._running and len(frames) < cap:
            try:
                frame = self.mic.read(timeout=0.5)
            except queue.Empty:
                # No audio this instant. In hold mode, still notice a key release.
                if mode == "hold" and not self.hotkeys.hold_key_is_down():
                    break
                continue
            frames.append(frame)

            if mode == "hold" and not self.hotkeys.hold_key_is_down():
                break
            if mode == "toggle" and self._next_event() == Event.TOGGLE:
                break
            if mode == "wake":
                if self.endpointer.update(frame.astype("float32") / 32768.0):
                    break

        self.tray.beep_stop()
        self.tray.set_state("busy")
        self.overlay.busy()
        audio = _frames_to_float(frames)
        text = self.engine.transcribe(audio)
        if text:
            paste_at_cursor(text)
        self.mic.drain()
        self._flush_events()
        self.tray.set_state("idle")
        self.overlay.hide()

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
        print("LocalWhisper stopped.")


def main():
    App().start()


if __name__ == "__main__":
    sys.exit(main())
