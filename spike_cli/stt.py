import asyncio

_orig_create_conn = asyncio.BaseEventLoop.create_connection
async def _create_connection_allow_headers(self, protocol_factory, host=None, port=None, **kwargs):
    kwargs.pop("extra_headers", None)
    return await _orig_create_conn(self, protocol_factory, host, port, **kwargs)
asyncio.BaseEventLoop.create_connection = _create_connection_allow_headers

import os
import io

from deepgram import Deepgram
import wave

class STT:
    """Base class for speech-to-text implementations."""
    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe audio bytes into text."""
        raise NotImplementedError

class DeepgramSTT(STT):
    """Deepgram STT supporting both prerecord and live streaming via WebSockets."""
    def __init__(self, sample_rate: int = 16000):
        api_key = os.getenv("DEEPGRAM_API_KEY")
        if not api_key:
            raise ValueError("Missing DEEPGRAM_API_KEY in environment")
        self.dg_client = Deepgram(api_key)
        self.sample_rate = sample_rate

    async def transcribe(self, audio_bytes: bytes) -> str:
        # fallback prerecord method
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_bytes)
        wav_buffer.seek(0)
        try:
            source  = {'buffer': wav_buffer, 'mimetype': 'audio/wav'}
            opts = {'punctuate': True}
            resp = await self.dg_client.transcription.prerecorded(source, opts)
        except Exception as e:
            print(f"⚠️ STT error: {e}")
            return ""
        try:
            alt = resp['results']['channels'][0]['alternatives'][0]
            return alt.get('transcript', "")
        except Exception:
            return ""

    async def stream(self, audio_queue: asyncio.Queue, callback):
        """
        Live stream transcription: reads raw PCM frames from an asyncio.Queue,
        sends to Deepgram live WS, and invokes callback on each final transcript.
        """
        socket = await self.dg_client.transcription.live(
            {"encoding": "linear16", "sample_rate": self.sample_rate},
            {"punctuate": True}
        )
        async def sender():
            while True:
                frame = await audio_queue.get()
                await socket.send({"type": "Binary", "data": frame})
        async def receiver():
            async for msg in socket:
                if msg.get('is_final'):
                    text = msg['channel']['alternatives'][0].get('transcript', "").strip()
                    if text:
                        callback(text)
        await asyncio.gather(sender(), receiver())
