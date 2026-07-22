"""One shared microphone input stream producing fixed-size int16 frames.

The queue is bounded: if the consumer ever falls behind (e.g. during a slow
transcription), the oldest frames are dropped so latency can't grow without bound and
memory stays flat. During active recording the consumer keeps up, so nothing is dropped.
"""
import queue
import numpy as np
import sounddevice as sd


class Microphone:
    def __init__(self, sample_rate=16000, frame_len=1280, max_seconds=12):
        self.sample_rate = sample_rate
        self.frame_len = frame_len
        fps = sample_rate / frame_len
        self._q: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=int(fps * max_seconds))
        self._stream = None

    def _callback(self, indata, frames, time_info, status):
        frame = indata[:, 0].copy()          # (frame_len,) int16
        try:
            self._q.put_nowait(frame)
        except queue.Full:
            try:
                self._q.get_nowait()          # drop the oldest frame
            except queue.Empty:
                pass
            try:
                self._q.put_nowait(frame)
            except queue.Full:
                pass

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

    def read_or_none(self, timeout=0.05):
        """Return the next int16 frame, or None if none arrived within `timeout`."""
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None

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
