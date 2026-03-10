import json
import logging
from abc import ABC, abstractmethod

from openai import AsyncOpenAI

from backend.config import Settings
from backend.models import BranchDecisionResult

logger = logging.getLogger(__name__)


class BranchService(ABC):
    @abstractmethod
    async def decide(
        self,
        transcription: str,
        conditions: list[dict],
        current_script: str,
    ) -> BranchDecisionResult:
        """Determine which branch condition matches the caller's speech."""
        pass


class OpenAIBranchService(BranchService):
    def __init__(self, settings: Settings):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.branch_model

    async def decide(
        self,
        transcription: str,
        conditions: list[dict],
        current_script: str,
    ) -> BranchDecisionResult:
        conditions_text = "\n".join(
            f'- Condition: "{c["condition"]}" -> target: {c["target_node_id"]}'
            for c in conditions
        )

        system_prompt = (
            "You are a phone call routing assistant. You analyze what a caller "
            "said and determine which branch condition best matches their response.\n\n"
            "Rules:\n"
            "- You MUST select exactly one condition from the provided list.\n"
            "- Match based on semantic meaning, not exact wording.\n"
            "- If no condition clearly matches, select the most general/default condition.\n"
            '- Respond with ONLY a JSON object: {"matched_condition": "...", '
            '"target_node_id": "...", "confidence": 0.0-1.0}'
        )

        user_prompt = (
            f'The automated system just said:\n"{current_script}"\n\n'
            f'The caller responded:\n"{transcription}"\n\n'
            f"Available branch conditions:\n{conditions_text}\n\n"
            "Which condition best matches the caller's response?"
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=150,
        )

        result_json = json.loads(response.choices[0].message.content)
        logger.info(
            "Branch decision: transcription=%r -> %s (confidence=%.2f)",
            transcription,
            result_json.get("matched_condition"),
            result_json.get("confidence", 0),
        )
        return BranchDecisionResult(**result_json)


def create_branch_service(settings: Settings) -> BranchService:
    return OpenAIBranchService(settings)
