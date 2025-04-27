import io
import wave
import pytest
from spike_cli.stt import DeepgramSTT, STT
pytest_plugins = ("pytest_asyncio",)

class DummyAlt:
    def __init__(self, transcript):
        self.transcript = transcript
    def get(self, key, default=None):
        return getattr(self, key, default)

class DummyChannel:
    def __init__(self, alt):
        self.alternatives = [alt]

class DummyResults:
    def __init__(self, transcript):
        self.results = {
            "channels": [ {"alternatives": [ {"transcript": transcript} ]} ]
        }
    
@pytest.mark.asyncio
async def test_transcribe_success(mocker, tmp_path, monkeypatch):
    pcm = (b"\x00\x00" * 8000)  
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(pcm)
    buf.seek(0)
    audio_bytes = pcm

    dummy_response = {
        "results": {
            "channels": [
                {"alternatives": [{"transcript": "hello world"}]}
            ]
        }
    }
    dg = DeepgramSTT(sample_rate=16000)
    mock_transcribe = mocker.patch.object(
        dg.dg_client.transcription, "prerecorded", return_value=dummy_response
    )

    text = await dg.transcribe(audio_bytes)
    assert text == "hello world"
    mock_transcribe.assert_called_once()

@pytest.mark.asyncio
async def test_transcribe_error_returns_empty(mocker, monkeypatch):
    dg = DeepgramSTT(sample_rate=16000)
    mocker.patch.object(
        dg.dg_client.transcription, "prerecorded", side_effect=Exception("boom")
    )
    text = await dg.transcribe(b"\x00\x00")
    assert text == ""