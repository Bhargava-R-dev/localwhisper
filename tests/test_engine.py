from dataclasses import replace
from faster_whisper.audio import decode_audio
from localwhisper.config import load_config
from localwhisper.engine import WhisperEngine


def test_transcribes_known_audio():
    cfg = replace(load_config(), model_name="tiny.en")  # fast model for the test
    engine = WhisperEngine(cfg)
    audio = decode_audio("tests/fixtures/jfk.wav", sampling_rate=cfg.sample_rate)
    text = engine.transcribe(audio)
    assert "country" in text.lower()


def test_blank_audio_returns_empty():
    import numpy as np
    cfg = replace(load_config(), model_name="tiny.en")
    engine = WhisperEngine(cfg)
    silence = np.zeros(cfg.sample_rate, dtype="float32")  # 1 s of silence
    assert engine.transcribe(silence).strip() == ""
