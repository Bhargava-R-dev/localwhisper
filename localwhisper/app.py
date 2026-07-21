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
