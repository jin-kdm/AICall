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


@router.post("/twilio/incoming")
async def handle_incoming_call(
    request: Request, db: AsyncSession = Depends(get_db)
):
    """Twilio webhook for incoming calls. Returns TwiML to connect Media Stream."""
    form = await request.form()
    to_number = form.get("To", "")
    call_sid = form.get("CallSid", "")

    logger.info("Incoming call: To=%s, CallSid=%s", to_number, call_sid)

    scenario = await find_scenario_by_phone(db, to_number)

    response = VoiceResponse()

    if not scenario:
        logger.warning("No scenario for phone number %s", to_number)
        response.say(
            "Sorry, this number is not configured.",
            language="ja-JP",
        )
        response.hangup()
    else:
        connect = Connect()
        stream = Stream(
            url=f"{settings.ws_base_url}/ws/call/{scenario.id}"
        )
        stream.parameter(name="callSid", value=call_sid)
        connect.append(stream)
        response.append(connect)
        logger.info(
            "Connecting call to scenario %d (%s)", scenario.id, scenario.name
        )

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
