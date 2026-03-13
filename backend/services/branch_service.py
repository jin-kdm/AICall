import json
import logging
from abc import ABC, abstractmethod

from backend.config import Settings
from backend.models import BranchDecisionResult
from backend.services.openai_client import get_openai_client

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
        self.client = get_openai_client(settings)
        self.model = settings.branch_model

    async def decide(
        self,
        transcription: str,
        conditions: list[dict],
        current_script: str,
    ) -> BranchDecisionResult:
        conditions_text = "\n".join(
            f'- "{c["condition"]}" -> {c["target_node_id"]}'
            for c in conditions
        )

        system_prompt = (
            "You route phone calls. Given caller speech and branch conditions, "
            "select the best-matching condition.\n"
            "Rules: select exactly one condition by semantic meaning. "
            "If unclear, pick the most general/default.\n"
            'Respond ONLY with JSON: {"matched_condition":"...","target_node_id":"...","confidence":0.0-1.0}'
        )

        user_prompt = (
            f'System said: "{current_script}"\n'
            f'Caller said: "{transcription}"\n'
            f"Conditions:\n{conditions_text}"
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=100,
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
