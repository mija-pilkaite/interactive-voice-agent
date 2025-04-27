import webrtcvad
from spike_cli.recorder import Recorder

def test_vad_segment(monkeypatch):
    # 1) Stub out webrtcvad so only b"\x01" frames count as speech
    class DummyVad:
        def __init__(self, *args): pass
        def is_speech(self, frame, sample_rate):
            return frame == b"\x01"

    monkeypatch.setattr(webrtcvad, "Vad", DummyVad)

    # 2) Create a Recorder with tiny frames & default thresholds
    rec = Recorder(samplerate=1000, frame_duration=600, aggressiveness=0)
    print("rec", rec)
    # 3) Prepare a series of frames: 2 silence, 2 speech, 2 silence
    frames = [b"\x00", b"\x00", b"\x01", b"\x01", b"\x00", b"\x00", b"\x00", b"\x00"]
    for f in frames:
        rec._audio_queue.put(f)
    print("rec._audio_queue", rec._audio_queue)
    segments = []

    # 4) Callback: collect utterance then stop the loop immediately
    def cb(utterance: bytes):
        segments.append(utterance)
        rec._running = False

    # 5) Kick off processing
    rec._running = True
    rec._process_audio(cb)

    # 6) We should have exactly one segment: the two b"\x01" and two b"\x00" frames concatenated as the threshold is one frame of silence, thus two exceeds it so the last two get cut
    assert segments == [b"\x01\x01\x00\x00"]