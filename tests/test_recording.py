"""Regression stress tests for the recording loop's stop-condition logic.

These lock in the fixes for the two reported bugs:
  - toggle-off / hold-release must work EVEN when the microphone delivers no frames
  - a single flaky key-state reading must NOT cut off a walkie-talkie hold
"""
from localwhisper.recording import record_frames

FRAME = object()          # opaque stand-in for an audio frame
NO = lambda: False
NEVER = lambda _f: False


def counter(true_on):
    """Return a zero-arg callable that returns True on its `true_on`-th call."""
    state = {"n": 0}

    def fn():
        state["n"] += 1
        return state["n"] == true_on

    return fn


def frames_forever():
    return FRAME


def none_forever():
    return None


# --- toggle -----------------------------------------------------------------

def test_toggle_stops_on_second_toggle():
    frames, reason = record_frames(
        "toggle", frames_forever, NO, counter(true_on=5), NEVER,
        max_frames=1000, stall_iters=100, hold_release_iters=3,
    )
    assert reason == "toggle"
    assert len(frames) == 4          # 4 frames captured before the 5th poll fired


def test_toggle_stops_even_when_mic_stalls():
    # THE bug #2 fix: no frames arrive at all, but toggling off still stops it.
    frames, reason = record_frames(
        "toggle", none_forever, NO, counter(true_on=3), NEVER,
        max_frames=1000, stall_iters=100, hold_release_iters=3,
    )
    assert reason == "toggle"        # stopped on the toggle, NOT stuck spinning
    assert frames == []              # nothing captured (mic was silent) but we still exited


# --- hold -------------------------------------------------------------------

def test_hold_stops_after_release_debounce():
    # is_hold_down: True for 3 calls, then False forever.
    calls = {"n": 0}

    def is_down():
        calls["n"] += 1
        return calls["n"] <= 3

    frames, reason = record_frames(
        "hold", frames_forever, is_down, NO, NEVER,
        max_frames=1000, stall_iters=100, hold_release_iters=3,
    )
    assert reason == "hold_release"
    assert len(frames) == 5          # 3 held + 2 during the debounce window


def test_hold_ignores_single_flaky_release():
    # THE bug #1 fix: one spurious "key up" reading must not end the hold.
    calls = {"n": 0}

    def is_down():
        calls["n"] += 1
        return calls["n"] != 4       # a single False on the 4th reading

    frames, reason = record_frames(
        "hold", frames_forever, is_down, NO, NEVER,
        max_frames=8, stall_iters=100, hold_release_iters=3,
    )
    assert reason == "cap"           # ran to the cap — the flaky reading was ignored
    assert len(frames) == 8


# --- watchdog / cap / wake --------------------------------------------------

def test_stall_watchdog_bails_instead_of_spinning():
    frames, reason = record_frames(
        "wake", none_forever, NO, NO, NEVER,
        max_frames=1000, stall_iters=5, hold_release_iters=3,
    )
    assert reason == "stall"
    assert frames == []


def test_cap_reached():
    frames, reason = record_frames(
        "wake", frames_forever, NO, NO, NEVER,
        max_frames=8, stall_iters=100, hold_release_iters=3,
    )
    assert reason == "cap"
    assert len(frames) == 8


def test_wake_ends_on_endpoint():
    frames, reason = record_frames(
        "wake", frames_forever, NO, NO, on_wake_frame=lambda _f: len_hit(),
        max_frames=1000, stall_iters=100, hold_release_iters=3,
    )
    assert reason == "wake_endpoint"
    assert len(frames) == 4


_ep = {"n": 0}


def len_hit():
    _ep["n"] += 1
    return _ep["n"] == 4
