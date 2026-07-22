from localwhisper.config import Config, load_config


def test_defaults_match_spec():
    c = load_config()
    assert isinstance(c, Config)
    assert c.model_name == "small.en"
    assert c.language == "en"
    assert c.sample_rate == 16000
    assert c.frame_len == 1280            # 80 ms @ 16 kHz
    assert c.hold_hotkey == "ctrl+b"
    assert c.toggle_hotkey == "alt+n"
    assert c.wakeword_model == "hey_jarvis"
    assert 0.0 < c.wakeword_threshold < 1.0
    assert c.endpoint_silence_ms == 1500
    assert c.max_record_ms == 15000
    assert c.max_hold_ms == 300000        # push-to-talk can run well past 15 s
    assert c.compute_type == "int8"
    assert c.beep is True
    assert c.show_overlay is True
