import numpy as np
import soxr

try:
    import audioop
except ImportError:
    import audioop_lts as audioop


def pcm_to_mulaw_8khz(pcm_data: bytes, source_sample_rate: int) -> bytes:
    """Convert PCM 16-bit mono audio to mulaw 8kHz (Twilio native format)."""
    pcm_array = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float64)
    resampled = soxr.resample(pcm_array, source_sample_rate, 8000)
    resampled_int16 = np.clip(resampled, -32768, 32767).astype(np.int16).tobytes()
    return audioop.lin2ulaw(resampled_int16, 2)


def mulaw_8khz_to_pcm_16khz(mulaw_data: bytes) -> bytes:
    """Convert mulaw 8kHz to PCM 16-bit 16kHz (for Whisper STT)."""
    pcm_8k = audioop.ulaw2lin(mulaw_data, 2)
    pcm_array = np.frombuffer(pcm_8k, dtype=np.int16).astype(np.float64)
    resampled = soxr.resample(pcm_array, 8000, 16000)
    return np.clip(resampled, -32768, 32767).astype(np.int16).tobytes()


def mulaw_to_pcm(mulaw_data: bytes) -> bytes:
    """Convert mulaw to linear PCM 16-bit (same sample rate)."""
    return audioop.ulaw2lin(mulaw_data, 2)
