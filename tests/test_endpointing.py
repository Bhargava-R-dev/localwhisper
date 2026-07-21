import numpy as np
from localwhisper.endpointing import Endpointer


def _loud(n):
    return np.full(n, 0.2, dtype="float32")   # RMS 0.2 > threshold


def _quiet(n):
    return np.zeros(n, dtype="float32")        # RMS 0 < threshold


def test_fires_after_silence_following_speech():
    ep = Endpointer(sample_rate=16000, silence_ms=1500, energy_threshold=0.01, frame_ms=80)
    n = 1280  # 80 ms

    # 3 speech frames — must not fire yet
    assert not any(ep.update(_loud(n)) for _ in range(3))

    # silence_ms / frame_ms = 1500/80 = 18.75 -> 19 silent frames needed
    fired = [ep.update(_quiet(n)) for _ in range(19)]
    assert fired[-1] is True          # fires on the 19th silent frame
    assert not any(fired[:18])        # not before


def test_does_not_fire_without_prior_speech():
    ep = Endpointer(sample_rate=16000, silence_ms=1500, energy_threshold=0.01, frame_ms=80)
    n = 1280
    assert not any(ep.update(_quiet(n)) for _ in range(50))  # pure silence never ends


def test_reset_clears_state():
    ep = Endpointer(sample_rate=16000, silence_ms=1500, energy_threshold=0.01, frame_ms=80)
    n = 1280
    ep.update(_loud(n))
    ep.reset()
    assert not any(ep.update(_quiet(n)) for _ in range(50))  # speech was forgotten
