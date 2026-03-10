import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings
from backend.models import AudioCache, AudioGenerationResult, Scenario
from backend.services.audio_utils import pcm_to_mulaw_8khz
from backend.services.storage_service import (
    create_storage_service,
    invalidate_audio_cache,
)


class TTSService(ABC):
    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Generate raw PCM audio from text. Returns PCM 16-bit mono."""
        pass

    @abstractmethod
    def get_sample_rate(self) -> int:
        """Return the native sample rate of the provider's output."""
        pass


class OpenAITTSService(TTSService):
    def __init__(self, settings: Settings):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.voice = settings.tts_voice
        self.model = settings.tts_model

    async def synthesize(self, text: str) -> bytes:
        pcm_data = bytearray()
        async with self.client.audio.speech.with_streaming_response.create(
            model=self.model,
            voice=self.voice,
            input=text,
            response_format="pcm",
        ) as response:
            async for chunk in response.iter_bytes():
                pcm_data.extend(chunk)
        return bytes(pcm_data)

    def get_sample_rate(self) -> int:
        return 24000


class FishSpeechTTSService(TTSService):
    """Future: Fish Speech provider."""

    async def synthesize(self, text: str) -> bytes:
        raise NotImplementedError("Fish Speech TTS not yet implemented")

    def get_sample_rate(self) -> int:
        return 44100


def create_tts_service(settings: Settings) -> TTSService:
    if settings.tts_provider == "openai":
        return OpenAITTSService(settings)
    elif settings.tts_provider == "fish_speech":
        return FishSpeechTTSService(settings)
    raise ValueError(f"Unknown TTS provider: {settings.tts_provider}")


async def generate_audio_for_scenario(
    scenario: Scenario, db: AsyncSession, settings: Settings
) -> AudioGenerationResult:
    """Pre-generate all TTS audio for a scenario's nodes."""
    tts = create_tts_service(settings)
    storage = create_storage_service(settings)
    result = AudioGenerationResult(generated=0, skipped=0, errors=[])

    for node in scenario.nodes:
        if not node.script.strip():
            result.skipped += 1
            continue

        script_hash = hashlib.sha256(node.script.encode()).hexdigest()

        # Check if cache is valid
        if node.audio_cache and node.audio_cache.script_hash == script_hash:
            result.skipped += 1
            continue

        try:
            pcm_data = await tts.synthesize(node.script)
            mulaw_data = pcm_to_mulaw_8khz(pcm_data, tts.get_sample_rate())

            filename = f"{scenario.id}_{node.id}.mulaw"
            stored_path = await storage.upload(filename, mulaw_data)
            invalidate_audio_cache(stored_path)

            if node.audio_cache:
                node.audio_cache.file_path = stored_path
                node.audio_cache.script_hash = script_hash
                node.audio_cache.generated_at = datetime.now(timezone.utc)
            else:
                cache = AudioCache(
                    node_id=node.id,
                    file_path=stored_path,
                    format="mulaw",
                    script_hash=script_hash,
                )
                db.add(cache)

            result.generated += 1
        except Exception as e:
            result.errors.append({"node_id": node.id, "error": str(e)})

    await db.commit()
    return result
