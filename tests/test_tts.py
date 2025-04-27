import pytest
from spike_cli.tts import ElevenLabsTTS

class DummyVoice:
    def __init__(self, voice_id, name, language_code, category):
        self.voice_id = voice_id
        self.name = name
        self.language_code = language_code
        self.category = category

def test_voice_lookup_success(monkeypatch):
    dummy_list = [
        DummyVoice("id1", "Aria", "en-US", "premade"),
        DummyVoice("id2", "Roger", "en-US", "premade"),
    ]
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake")
    monkeypatch.setattr(
        ElevenLabsTTS, "fetch_voices", staticmethod(lambda: dummy_list)
    )
    vid = ElevenLabsTTS.voice_id_for_name("aria")
    assert vid == "id1"

def test_voice_lookup_not_found(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake")
    monkeypatch.setattr(ElevenLabsTTS, "fetch_voices", staticmethod(lambda: []))
    with pytest.raises(KeyError):
        ElevenLabsTTS.voice_id_for_name("doesnotexist")