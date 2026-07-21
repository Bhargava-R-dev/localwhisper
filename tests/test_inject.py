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
