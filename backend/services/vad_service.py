import webrtcvad

from backend.config import Settings
from backend.services.audio_utils import mulaw_to_pcm


class VADService:
    def __init__(self, settings: Settings):
        self.vad = webrtcvad.Vad(settings.vad_aggressiveness)
        self.silence_timeout_ms = settings.vad_silence_timeout_ms
        self.min_speech_ms = settings.vad_min_speech_ms
        self.frame_duration_ms = 20  # Twilio sends 20ms frames at 8kHz

        # State
        self.has_speech_started = False
        self.speech_frames = 0
        self.silence_frames = 0

    def reset(self):
        """Reset state for a new listening period."""
        self.has_speech_started = False
        self.speech_frames = 0
        self.silence_frames = 0

    def is_speech_frame(self, mulaw_frame: bytes) -> bool:
        """Quick check if a single frame contains speech (for barge-in)."""
        pcm_frame = mulaw_to_pcm(mulaw_frame)
        # webrtcvad requires 20ms at 8kHz = 160 samples = 320 bytes (16-bit)
        if len(pcm_frame) < 320:
            return False
        return self.vad.is_speech(pcm_frame[:320], 8000)

    def process_frame(self, mulaw_frame: bytes) -> bool:
        """Process one frame. Returns True if end-of-speech detected."""
        is_speech = self.is_speech_frame(mulaw_frame)

        if is_speech:
            self.has_speech_started = True
            self.speech_frames += 1
            self.silence_frames = 0
        elif self.has_speech_started:
            self.silence_frames += 1

        if self.has_speech_started:
            speech_duration_ms = self.speech_frames * self.frame_duration_ms
            silence_duration_ms = self.silence_frames * self.frame_duration_ms

            if (
                speech_duration_ms >= self.min_speech_ms
                and silence_duration_ms >= self.silence_timeout_ms
            ):
                return True

        return False
