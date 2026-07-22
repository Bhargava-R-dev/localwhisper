"""Pure recording-loop logic, decoupled from hardware so it can be stress-tested.

The key design rule: **stop conditions are evaluated every iteration, whether or not a
frame arrived.** A stalled microphone can therefore never leave a toggle recording stuck
"listening" (bug that coupled the stop check to frame delivery), and a single flaky
key-state reading can't cut off a walkie-talkie hold (the release is debounced).
"""


def record_frames(mode, read_frame, is_hold_down, pop_toggle, on_wake_frame,
                  max_frames, stall_iters, hold_release_iters):
    """Collect audio frames for one utterance.

    Args:
        mode: "hold" | "toggle" | "wake".
        read_frame: () -> frame or None. None means "no audio available right now".
        is_hold_down: () -> bool. True while the hold hotkey is physically pressed.
        pop_toggle: () -> bool. True (consuming the event) when toggle was pressed again.
        on_wake_frame: (frame) -> bool. True when the endpointer says speech ended.
        max_frames: hard cap on captured frames (runaway guard).
        stall_iters: consecutive no-frame iterations before we give up (mic stalled).
        hold_release_iters: consecutive "key up" reads required to end a hold (debounce).

    Returns:
        (frames, reason) where reason is one of:
        "toggle" | "hold_release" | "wake_endpoint" | "cap" | "stall".
    """
    frames = []
    empty_streak = 0
    up_streak = 0

    while len(frames) < max_frames:
        # --- stop conditions FIRST, every iteration, independent of frame arrival ---
        if mode == "hold":
            if is_hold_down():
                up_streak = 0
            else:
                up_streak += 1
                if up_streak >= hold_release_iters:
                    return frames, "hold_release"
        elif mode == "toggle":
            if pop_toggle():
                return frames, "toggle"

        frame = read_frame()
        if frame is None:
            empty_streak += 1
            if empty_streak >= stall_iters:
                return frames, "stall"          # mic stalled — bail, never spin forever
            continue
        empty_streak = 0
        frames.append(frame)

        if mode == "wake" and on_wake_frame(frame):
            return frames, "wake_endpoint"

    return frames, "cap"
