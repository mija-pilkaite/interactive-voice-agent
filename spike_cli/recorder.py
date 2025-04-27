import queue
import threading
import webrtcvad
import sounddevice as sd

class Recorder:
    """
    Recorder with VAD-based utterance segmentation and pause/resume support.
    Records short frames, detects speech start/end, and emits complete utterances.
    """
    def __init__(self, samplerate=16000, frame_duration=30, aggressiveness=2):
        """
        samplerate: samples per second
        frame_duration: duration of each frame in ms (10, 20, or 30)
        aggressiveness: VAD sensitivity 0-3 (higher more aggressive)
        """
        self.samplerate = samplerate
        self.frame_duration = frame_duration
        self.frame_size = int(samplerate * frame_duration / 1000)
        self.vad = webrtcvad.Vad(aggressiveness)
        self._audio_queue = queue.Queue()
        self._thread = None
        self._running = False
        self._stream = None

    def start(self, callback):
        """
        Start recording. callback will be called with full utterance bytes.
        """
        if self._running:
            return
        self._running = True

        # Launch background thread to segment utterances
        self._thread = threading.Thread(target=self._process_audio, args=(callback,))
        self._thread.daemon = True
        self._thread.start()

        # Start non-blocking audio stream
        self._stream = sd.InputStream(
            samplerate=self.samplerate,
            blocksize=self.frame_size,
            channels=1,
            dtype='int16',
            callback=self._enqueue
        )
        self._stream.start()

    def _enqueue(self, indata, frames, time, status):
        """
        Sounddevice callback: push raw bytes of each frame to queue.
        """
        if status:
            print(f"⚠️ Recorder status: {status}")
        self._audio_queue.put(indata.tobytes())

    def _process_audio(self, callback):
        """
        Consume frames, apply VAD, accumulate into utterances.
        """
        triggered = False
        silent_frames = 0
        utterance = bytearray()
        threshold_silent = int(600 / self.frame_duration)  # ms of silence to end

        while self._running:
            try:
                frame = self._audio_queue.get(timeout=1)
            except queue.Empty:
                continue

            is_speech = self.vad.is_speech(frame, sample_rate=self.samplerate)

            if not triggered:
                if is_speech:
                    triggered = True
                    utterance.extend(frame)
            else:
                utterance.extend(frame)
                if not is_speech:
                    silent_frames += 1
                    if silent_frames > threshold_silent:
                        callback(bytes(utterance))
                        triggered = False
                        silent_frames = 0
                        utterance = bytearray()
                else:
                    silent_frames = 0

        # Emit any final utterance
        if utterance:
            callback(bytes(utterance))

    def pause(self):
        """
        Pause audio input to avoid feedback during playback.
        """
        if self._stream and self._running:
            try:
                self._stream.stop()
            except Exception:
                pass

    def resume(self):
        """
        Resume audio input after playback.
        """
        if self._stream and self._running:
            try:
                self._stream.start()
            except Exception:
                pass

    def stop(self):
        """
        Stop recording and terminate background thread.
        """
        self._running = False
        # Stop and close the stream if active
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
        # We no longer join the VAD thread here to avoid joining from within the same thread.
        # The thread will exit naturally once _running is False.
