import sounddevice as sd

class Recorder:
    def __init__(self, samplerate=16_000, block_duration=1.0, device=None):
        self.samplerate = samplerate
        self.block_size = int(samplerate * block_duration)
        self.device = device
    def start(self, callback):
        """Continuously read blocks and call `callback(bytes)`."""
        def _audio_callback(indata, frames, time, status):
            callback(bytes(indata))

        self.stream = sd.InputStream(
            samplerate=self.samplerate,
            blocksize=self.block_size,
            channels=1,
            device=self.device,
            callback=_audio_callback
        )
        self.stream.start()

    def stop(self):
        self.stream.stop()
        self.stream.close()
