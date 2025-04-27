import os
import asyncio
from elevenlabs import ElevenLabs, VoiceSettings

class ElevenLabsTTS:
    """
    ElevenLabs TTS wrapper supporting both batch synthesize and async streaming.
    """
    @staticmethod
    def fetch_voices():
        key = os.getenv("ELEVENLABS_API_KEY", "").strip()
        if not key:
            raise ValueError("Missing ELEVENLABS_API_KEY")
        client = ElevenLabs(api_key=key)
        print("Fetching ElevenLabs voices...")
        voices = client.voices.get_all().voices
        print(f"Found {len(voices)} voices:")
        print(f'Voices: {", ".join([v.name for v in voices])}')
        print(f"Voice IDs: {', '.join([v.voice_id for v in voices])}")
        return client.voices.get_all().voices

    @staticmethod
    def voice_id_for_name(name: str):
        """
        Look up the first voice whose .name matches (case-insensitive) the given name.
        Raises KeyError if no match is found.
        """
        for v in ElevenLabsTTS.fetch_voices():
            if v.name.lower() == name.lower():
                return v.voice_id
        raise KeyError(f"No ElevenLabs voice named {name!r}")

    def __init__(self, config: dict):
        raw_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
        if not raw_key:
            raise ValueError("Missing ELEVENLABS_API_KEY")
        self.client = ElevenLabs(api_key=raw_key)

        cfg_tts = config.get("tts", {})
        vid      = cfg_tts.get("voice_id", "")         # could be an ID …
        vname    = cfg_tts.get("voice_name", "")       # … or a friendly name
        if vname:
            try:
                vid = ElevenLabsTTS.voice_id_for_name(vname)
            except KeyError as e:
                raise ValueError(f"Voice lookup error: {e}")

        # if neither provided, auto-pick the first
        if not vid:
            vid = self.client.voices.get_all().voices[0].voice_id
        self.voice_id      = vid
        self.model_id      = cfg_tts.get("model_id", "eleven_multilingual_v2")
        self.output_format = cfg_tts.get("output_format", "pcm_16000")
        self.voice_settings = VoiceSettings(
            stability=cfg_tts.get("stability", 0.75),
            similarity_boost=cfg_tts.get("similarity_boost", 0.75)
        )

    def synthesize(self, text: str) -> bytes:
        """
        Synchronous batch synthesis: returns full PCM bytes.
        """
        audio_chunks = self.client.text_to_speech.convert(
            text=text,
            voice_id=self.voice_id,
            model_id=self.model_id,
            voice_settings=self.voice_settings,
            output_format=self.output_format
        )
        try:
            return b"".join(audio_chunks)
        except TypeError:
            # if single bytes
            return audio_chunks

    async def stream(self, text: str, pcm_queue: asyncio.Queue):
        """
        Async streaming synthesis: pushes raw PCM chunks to an asyncio.Queue
        as they arrive from the ElevenLabs streaming API.
        """
        loop = asyncio.get_event_loop()
        # convert() returns a generator of byte chunks
        def generate():
            return self.client.text_to_speech.convert(
                text=text,
                voice_id=self.voice_id,
                model_id=self.model_id,
                voice_settings=self.voice_settings,
                output_format=self.output_format
            )

        # Run blocking stream in thread to feed queue
        def _stream_to_queue():
            for chunk in generate():
                # feed into Python queue via threadsafe
                asyncio.run_coroutine_threadsafe(pcm_queue.put(chunk), loop)

        # launch in executor
        await loop.run_in_executor(None, _stream_to_queue)
