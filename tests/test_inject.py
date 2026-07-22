from localwhisper import inject


class FakeClip:
    def __init__(self, initial=""):
        self.value = initial

    def paste(self):
        return self.value

    def copy(self, v):
        self.value = v


def test_pastes_text_then_restores_clipboard():
    clip = FakeClip("original")
    seen = {}

    def fake_paste():
        seen["at_paste"] = clip.value   # what was on the clipboard when Ctrl+V fired

    inject.paste_at_cursor(
        "hello world", paste_fn=fake_paste, clipboard=clip, sleep=lambda _s: None
    )

    assert seen["at_paste"] == "hello world"   # text was on clipboard at paste time
    assert clip.value == "original"            # original clipboard restored afterward


def test_blank_text_is_a_noop():
    clip = FakeClip("original")
    called = []
    inject.paste_at_cursor(
        "   ", paste_fn=lambda: called.append(1), clipboard=clip, sleep=lambda _s: None
    )
    assert called == []
    assert clip.value == "original"


class LockedClip:
    """Simulates a clipboard held by another app: copy() always raises."""

    def paste(self):
        raise RuntimeError("Error calling OpenClipboard (Access denied)")

    def copy(self, v):
        raise RuntimeError("Error calling OpenClipboard (Access denied)")


def test_locked_clipboard_does_not_raise():
    # The core reliability fix: a locked clipboard must never propagate an exception
    # (that used to crash the whole app, killing hotkeys + wake word until restart).
    result = inject.paste_at_cursor(
        "hello", paste_fn=lambda: None, clipboard=LockedClip(), sleep=lambda _s: None
    )
    assert result is False   # reported failure, but returned cleanly instead of raising


class FlakyClip(FakeClip):
    """Fails the first N copy() calls, then succeeds — mimics a transient lock."""

    def __init__(self, fail_times):
        super().__init__("original")
        self.fail_times = fail_times

    def copy(self, v):
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("clipboard busy")
        self.value = v


def test_retries_transient_clipboard_lock():
    clip = FlakyClip(fail_times=2)   # first 2 attempts fail, 3rd succeeds
    seen = {}
    inject.paste_at_cursor(
        "typed text", paste_fn=lambda: seen.setdefault("at_paste", clip.value),
        clipboard=clip, sleep=lambda _s: None,
    )
    assert seen["at_paste"] == "typed text"   # succeeded after retrying
