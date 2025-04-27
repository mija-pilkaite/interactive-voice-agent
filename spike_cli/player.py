import numpy as np
import sounddevice as sd
import asyncio

class Player:
    """
    Plays back raw PCM bytes via sounddevice.
    Assumes 16 kHz, mono, 16-bit PCM.
    """
    def __init__(self, sample_rate=16000, channels=1):
        self.sample_rate = sample_rate
        self.channels    = channels

    def play(self, pcm_bytes: bytes):
        # Turn the raw bytes into an int16 numpy array
        audio = np.frombuffer(pcm_bytes, dtype=np.int16)
        # If it's multi-channel interleaved, reshape accordingly:
        if self.channels > 1:
            audio = audio.reshape(-1, self.channels)

        # Play and block until done
        sd.play(audio, samplerate=self.sample_rate)
        sd.wait()

    async def stream_play(self, pcm_queue: asyncio.Queue):
        """
        Consume raw PCM chunks from an asyncio.Queue and play them continuously
        via a single RawOutputStream to avoid tiny blocking plays.
        """
        # Open one continuous stream
        stream = sd.RawOutputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype='int16'
        )
        stream.start()
        try:
            while True:
                chunk = await pcm_queue.get()
                # If your pipeline never ends with a sentinel, this will run until
                # you CTRL-C out of the whole app.
                if not chunk:
                    # skip any empty frames
                    continue
                stream.write(chunk)
        finally:
            stream.stop()
            stream.close()