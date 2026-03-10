import logging

from fastapi import APIRouter, Depends, Request, WebSocket
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from twilio.twiml.voice_response import Connect, Stream, VoiceResponse

from backend.config import settings
from backend.database import async_session, get_db
from backend.models import Scenario
from backend.services.call_handler import CallHandler

logger = logging.getLogger(__name__)

router = APIRouter()


async def find_scenario_by_phone(
    db: AsyncSession, phone_number: str
) -> Scenario | None:
    result = await db.execute(
        select(Scenario).where(
            Scenario.twilio_phone_number == phone_number
        )
    )
    return result.scalar_one_or_none()


@router.api_route("/twilio/incoming", methods=["GET", "POST"])
async def handle_incoming_call():
    response = VoiceResponse()
    response.say("This is a test.")
    response.hangup()
    return Response(content=str(response), media_type="application/xml")
@router.websocket("/ws/call/{scenario_id}")
async def websocket_call(websocket: WebSocket, scenario_id: int):
    """Bidirectional Media Stream WebSocket for an active call."""
    await websocket.accept()

    async with async_session() as db:
        scenario = await db.get(Scenario, scenario_id)

    if not scenario:
        logger.error("Scenario %d not found, closing WebSocket", scenario_id)
        await websocket.close()
        return

    logger.info(
        "WebSocket call started for scenario %d (%s)",
        scenario.id,
        scenario.name,
    )

    handler = CallHandler(websocket, scenario, settings)
    await handler.run()
