import io
import wave
from abc import ABC, abstractmethod

try:
    import audioop
except ImportError:
    import audioop_lts as audioop

from openai import AsyncOpenAI

from backend.config import Settings

# Shared client — avoids per-call connection setup overhead
_openai_client: AsyncOpenAI | None = None


def _get_openai_client(settings: Settings) -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client


class STTService(ABC):
    @abstractmethod
    async def transcribe(self, mulaw_8khz: bytes) -> str:
        """Transcribe mulaw 8kHz mono audio to text."""
        pass


class OpenAIWhisperService(STTService):
    def __init__(self, settings: Settings):
        self.client = _get_openai_client(settings)
        self.model = settings.stt_model

    async def transcribe(self, mulaw_8khz: bytes) -> str:
        # 160 bytes of mulaw ≈ 20ms at 8kHz — reject tiny fragments
        if len(mulaw_8khz) < 160:
            return ""

        # Decode mulaw → PCM 16-bit at native 8kHz (NO resample to 16kHz).
        # Whisper / gpt-4o-mini-transcribe handle any sample rate internally.
        pcm_8k = audioop.ulaw2lin(mulaw_8khz, 2)
        wav_buffer = self._pcm_to_wav(pcm_8k, sample_rate=8000)

        transcript = await self.client.audio.transcriptions.create(
            model=self.model,
            file=("audio.wav", wav_buffer, "audio/wav"),
            response_format="text",
            language="ja",
        )
        return transcript.strip()

    def _pcm_to_wav(self, pcm_data: bytes, sample_rate: int) -> io.BytesIO:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_data)
        buf.seek(0)
        return buf


class SonioxSTTService(STTService):
    """Future: Soniox provider."""

    async def transcribe(self, mulaw_8khz: bytes) -> str:
        raise NotImplementedError("Soniox STT not yet implemented")


def create_stt_service(settings: Settings) -> STTService:
    if settings.stt_provider == "openai":
        return OpenAIWhisperService(settings)
    elif settings.stt_provider == "soniox":
        return SonioxSTTService(settings)
    raise ValueError(f"Unknown STT provider: {settings.stt_provider}")
