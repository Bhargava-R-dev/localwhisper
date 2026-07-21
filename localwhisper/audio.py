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
