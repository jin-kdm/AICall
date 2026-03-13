"""Combined STT + Branch Decision in a single API call.

Uses a model with audio input capability (e.g. gpt-4o-mini-audio-preview)
to listen to the caller's speech and return the branch decision directly,
eliminating one API round-trip compared to the sequential STT → Branch
pipeline.
"""

import base64
import io
import json
import logging
import wave

try:
    import audioop
except ImportError:
    import audioop_lts as audioop

from backend.config import Settings
from backend.models import BranchDecisionResult
from backend.services.openai_client import get_openai_client

logger = logging.getLogger(__name__)


class AudioBranchService:
    """Listen to caller audio and decide branch in one API call."""

    def __init__(self, settings: Settings):
        self.client = get_openai_client(settings)
        self.model = settings.audio_branch_model

    async def decide_from_audio(
        self,
        mulaw_8khz: bytes,
        conditions: list[dict],
        current_script: str,
    ) -> tuple[BranchDecisionResult, str]:
        """Analyse caller audio and return (decision, transcription).

        Raises on API error so the caller can fall back to the
        separate STT → Branch pipeline.
        """
        if len(mulaw_8khz) < 160:
            raise ValueError("Audio too short for analysis")

        # mulaw → PCM 8 kHz → WAV → base64
        pcm_8k = audioop.ulaw2lin(mulaw_8khz, 2)
        wav_b64 = self._pcm_to_wav_b64(pcm_8k, sample_rate=8000)

        conditions_text = "\n".join(
            f'- "{c["condition"]}" -> {c["target_node_id"]}'
            for c in conditions
        )

        system_prompt = (
            "You route phone calls. You will hear caller audio and see branch conditions. "
            "Listen to what the caller says, then select the best-matching condition.\n"
            "Rules: select exactly one condition by semantic meaning. "
            "If unclear, pick the most general/default.\n"
            "Respond ONLY with JSON: "
            '{"matched_condition":"...","target_node_id":"...","confidence":0.0-1.0,"transcription":"..."}\n'
            'The "transcription" field must contain what the caller said in their language.'
        )

        user_content = [
            {
                "type": "text",
                "text": (
                    f'System said: "{current_script}"\n'
                    f"Conditions:\n{conditions_text}\n\n"
                    "Listen to the caller's audio and decide which condition matches:"
                ),
            },
            {
                "type": "input_audio",
                "input_audio": {
                    "data": wav_b64,
                    "format": "wav",
                },
            },
        ]

        response = await self.client.chat.completions.create(
            model=self.model,
            modalities=["text"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=200,
        )

        result_json = json.loads(response.choices[0].message.content)
        transcription = result_json.pop("transcription", "")

        logger.info(
            "AudioBranch: transcription=%r -> %s (confidence=%.2f)",
            transcription,
            result_json.get("matched_condition"),
            result_json.get("confidence", 0),
        )

        return BranchDecisionResult(**result_json), transcription

    # ------------------------------------------------------------------

    @staticmethod
    def _pcm_to_wav_b64(pcm_data: bytes, sample_rate: int) -> str:
        """Wrap raw PCM in a WAV container and return as base64 string."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_data)
        return base64.b64encode(buf.getvalue()).decode("ascii")


def create_audio_branch_service(settings: Settings) -> AudioBranchService:
    return AudioBranchService(settings)
