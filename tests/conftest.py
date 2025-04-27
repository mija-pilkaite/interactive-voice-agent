import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import spike_cli.stt as stt_mod

@pytest.fixture(autouse=True)
def stub_deepgram(monkeypatch):
    """
    Replace deepgram.Deepgram with a dummy that provides a *single*
    transcription client object, so patching .prerecorded will work.
    """
    class DummyTranscriptionClient:
        async def prerecorded(self, *args, **kwargs):
            return {}

    class DummyDGClient:
        def __init__(self, api_key):
            self.transcription = DummyTranscriptionClient()

    monkeypatch.setattr(stt_mod, "Deepgram", DummyDGClient)
    monkeypatch.setenv("DEEPGRAM_API_KEY", "fake")
    monkeypatch.setenv("OPENAI_API_KEY",    "fake")