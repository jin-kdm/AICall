import logging

from fastapi import APIRouter, Depends, Request, WebSocket
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from twilio.twiml.voice_response import Connect, Stream, VoiceResponse

from backend.config import settings
from backend.database import async_session, get_db
from backend.models import Node, NodeType, Scenario
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
async def handle_incoming_call(
    request: Request, db: AsyncSession = Depends(get_db)
):
    form = await request.form()
    to_number = form.get("To", "")
    call_sid = form.get("CallSid", "")
    from_number = form.get("From", "")

    logger.info(
        "Incoming call: From=%s, To=%s, CallSid=%s",
        from_number, to_number, call_sid,
    )

    response = VoiceResponse()

    # Find scenario by the called phone number
    scenario = await find_scenario_by_phone(db, str(to_number))

    if not scenario:
        logger.warning("No scenario found for phone number: %s", to_number)
        response.say(
            "申し訳ございません。この番号は現在ご利用いただけません。",
            voice="alice",
            language="ja-JP",
        )
        response.hangup()
        return Response(content=str(response), media_type="application/xml")

    # Verify scenario has nodes
    has_start = any(n.node_type == NodeType.START for n in scenario.nodes)
    if not scenario.nodes or not has_start:
        logger.warning("Scenario %d has no start node", scenario.id)
        response.say(
            "申し訳ございません。シナリオが設定されていません。",
            voice="alice",
            language="ja-JP",
        )
        response.hangup()
        return Response(content=str(response), media_type="application/xml")

    # Route call to WebSocket with scenario
    ws_url = f"{settings.effective_ws_base_url}/ws/call/{scenario.id}"
    logger.info("Routing call to WebSocket: %s", ws_url)

    connect = Connect()
    stream = Stream(url=ws_url)
    stream.parameter(name="callSid", value=str(call_sid))
    connect.append(stream)
    response.append(connect)

    return Response(content=str(response), media_type="application/xml")

@router.websocket("/ws/call/{scenario_id}")
async def websocket_call(websocket: WebSocket, scenario_id: int):
    """Bidirectional Media Stream WebSocket for an active call."""
    await websocket.accept()

    # Explicitly load all nested relationships (nodes → audio_cache, edges)
    # so they remain available after the session closes.
    async with async_session() as db:
        result = await db.execute(
            select(Scenario)
            .options(
                selectinload(Scenario.nodes).selectinload(Node.audio_cache),
                selectinload(Scenario.edges),
            )
            .where(Scenario.id == scenario_id)
        )
        scenario = result.scalar_one_or_none()

    if not scenario:
        logger.error("Scenario %d not found, closing WebSocket", scenario_id)
        await websocket.close()
        return

    logger.info(
        "WebSocket call started for scenario %d (%s) — %d nodes, %d edges",
        scenario.id,
        scenario.name,
        len(scenario.nodes),
        len(scenario.edges),
    )

    # Log audio cache status for debugging
    for node in scenario.nodes:
        has_cache = node.audio_cache is not None
        data_size = len(node.audio_cache.audio_data) if has_cache and node.audio_cache.audio_data else 0
        logger.info(
            "  Node %s (%s): audio_cache=%s, audio_data=%d bytes",
            node.id, node.node_type.value, has_cache, data_size,
        )

    try:
        handler = CallHandler(websocket, scenario, settings)
        await handler.run()
    except Exception:
        logger.exception("CallHandler crashed for scenario %d", scenario_id)
