import json

from localwhisper import config as config_mod
from localwhisper.config import Config, load_config


def test_defaults_match_spec():
    c = Config()   # pure built-in defaults, no external override
    assert c.model_name == "small.en"
    assert c.language == "en"
    assert c.sample_rate == 16000
    assert c.frame_len == 1280            # 80 ms @ 16 kHz
    assert c.hold_hotkey == "ctrl+b"
    assert c.toggle_hotkey == "alt+n"
    assert c.wakeword_model == "hey_jarvis"
    assert c.endpoint_silence_ms == 1500
    assert c.max_record_ms == 30000       # wake safety cap bounds false-trigger damage
    assert c.max_hold_ms == 120000
    assert c.compute_type == "int8"
    assert c.beep is True
    assert c.show_overlay is True


def test_wake_word_is_off_by_default():
    # Safety default: the always-on listener must NOT run unless explicitly enabled.
    assert Config().wakeword_enabled is False
    assert Config().wakeword_threshold >= 0.7   # strict enough to resist false triggers
    assert Config().wakeword_patience >= 2


def test_config_json_override(tmp_path, monkeypatch):
    override = tmp_path / "config.json"
    override.write_text(json.dumps({"wakeword_enabled": True, "wakeword_threshold": 0.9}))
    monkeypatch.setattr(config_mod, "_override_path", lambda: str(override))

    c = load_config()
    assert c.wakeword_enabled is True        # user opted in without rebuilding
    assert c.wakeword_threshold == 0.9
    assert c.model_name == "small.en"        # untouched fields keep their defaults


def test_malformed_override_is_ignored(tmp_path, monkeypatch):
    bad = tmp_path / "config.json"
    bad.write_text("{ this is not valid json")
    monkeypatch.setattr(config_mod, "_override_path", lambda: str(bad))

    c = load_config()                         # must not raise
    assert c.wakeword_enabled is False        # falls back to safe defaults
