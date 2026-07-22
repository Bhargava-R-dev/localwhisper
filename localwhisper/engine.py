"""Wraps faster-whisper. Loads the model once and keeps it warm in RAM."""
import numpy as np
from faster_whisper import WhisperModel

from localwhisper.paths import whisper_model_source


class WhisperEngine:
    def __init__(self, config):
        self.language = config.language
        self.model = WhisperModel(
            whisper_model_source(config),
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
