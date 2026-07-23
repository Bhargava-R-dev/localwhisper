"""openWakeWord detector. Feed int16 frames; returns True when the phrase is heard."""
import numpy as np
from openwakeword.model import Model

from localwhisper.paths import ensure_wakeword_models


class WakeWord:
    def __init__(self, config):
        self.name = config.wakeword_model
        self.threshold = config.wakeword_threshold
        self.patience = max(1, int(getattr(config, "wakeword_patience", 1)))
        self._streak = 0
        ensure_wakeword_models()   # source/pip mode: fetch models on first use
        self.model = Model(
            wakeword_models=[self.name],
            inference_framework="onnx",
        )

    def detect(self, frame_int16: np.ndarray) -> bool:
        """True only after `patience` consecutive frames cross the threshold.

        Requiring several consecutive high frames rejects the transient single-frame
        spikes that cause false triggers on ordinary speech and background noise.
        """
        scores = self.model.predict(np.asarray(frame_int16, dtype="int16"))
        if scores.get(self.name, 0.0) >= self.threshold:
            self._streak += 1
            if self._streak >= self.patience:
                self._streak = 0
                self.model.reset()   # avoid immediate re-trigger on the same utterance
                return True
        else:
            self._streak = 0
        return False
