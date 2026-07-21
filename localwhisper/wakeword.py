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
