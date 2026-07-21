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
