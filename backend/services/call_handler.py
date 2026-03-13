import asyncio
import base64
import enum
import json
import logging
import time

import httpx
from sqlalchemy import select as sa_select
from starlette.websockets import WebSocket, WebSocketDisconnect

from backend.config import Settings
from backend.database import async_session
from backend.models import AudioCache, Node, NodeType, Scenario
from backend.services.audio_branch_service import create_audio_branch_service
from backend.services.branch_service import create_branch_service
from backend.services.stt_service import create_stt_service
from backend.services.vad_service import VADService

logger = logging.getLogger(__name__)


class CallPhase(str, enum.Enum):
    PLAYING_AUDIO = "playing_audio"
    LISTENING = "listening"
    PROCESSING = "processing"
    ENDED = "ended"


class CallHandler:
    """Manages a single active call via Twilio bidirectional Media Stream."""

    # Send audio in ~1-second chunks (fewer WS messages = less overhead)
    CHUNK_SIZE = 8000

    def __init__(
        self, websocket: WebSocket, scenario: Scenario, settings: Settings
    ):
        self.ws = websocket
        self.scenario = scenario
        self.settings = settings

        self.stream_sid: str | None = None
        self.call_sid: str | None = None
        self.current_node: Node = self._find_start_node()
        self.phase = CallPhase.PLAYING_AUDIO

        self.audio_buffer = bytearray()
        self.vad = VADService(settings)
        self.audio_branch = create_audio_branch_service(settings)
        # Fallback services (used when combined audio-branch call fails)
        self.stt = create_stt_service(settings)
        self.branch = create_branch_service(settings)

        self.mark_counter = 0
        self.pending_marks: dict[str, str] = {}

        # Barge-in requires sustained speech to avoid false triggers from noise
        self.barge_in_speech_count = 0
        self.BARGE_IN_THRESHOLD = 150  # 150 frames × 20ms = 3 seconds

        # All audio data: node_id -> mulaw bytes (bulk-loaded at start)
        self._audio_data: dict[str, bytes] = {}

    def _find_start_node(self) -> Node:
        for node in self.scenario.nodes:
            if node.node_type == NodeType.START:
                return node
        if self.scenario.nodes:
            return self.scenario.nodes[0]
        raise ValueError("Scenario has no nodes")

    def _find_node_by_id(self, node_id: str) -> Node | None:
        for node in self.scenario.nodes:
            if node.id == node_id:
                return node
        return None

    # --- Bulk audio loading (single DB query for ALL nodes) ---

    async def _load_all_audio(self):
        """Load audio_data for ALL nodes in the scenario in one DB query."""
        node_ids = [n.id for n in self.scenario.nodes]
        if not node_ids:
            return

        async with async_session() as db:
            result = await db.execute(
                sa_select(AudioCache.node_id, AudioCache.audio_data)
                .where(AudioCache.node_id.in_(node_ids))
            )
            for row in result.all():
                if row.audio_data:
                    self._audio_data[row.node_id] = row.audio_data

        logger.info(
            "Bulk-loaded audio for %d/%d nodes",
            len(self._audio_data), len(node_ids),
        )

    # --- Main loop ---

    async def run(self):
        """Main loop: receive Twilio WebSocket messages and dispatch."""
        # Bulk-load ALL audio NOW (before Twilio sends 'start')
        audio_load_task = asyncio.create_task(self._load_all_audio())

        try:
            while True:
                raw = await self.ws.receive_text()
                msg = json.loads(raw)
                event = msg.get("event")

                if event == "connected":
                    logger.info("WebSocket connected")
                elif event == "start":
                    self.stream_sid = msg["start"]["streamSid"]
                    custom_params = msg["start"].get("customParameters", {})
                    self.call_sid = custom_params.get("callSid")
                    logger.info(
                        "Stream started: stream_sid=%s, call_sid=%s",
                        self.stream_sid,
                        self.call_sid,
                    )
                    # Ensure all audio is ready (likely already done)
                    await audio_load_task
                    await self._play_node_audio(self.current_node)
                elif event == "media":
                    await self._handle_incoming_audio(msg["media"]["payload"])
                elif event == "mark":
                    await self._handle_mark(msg["mark"]["name"])
                elif event == "stop":
                    logger.info("Stream stopped")
                    break
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception:
            logger.exception("CallHandler run() crashed")

    # --- Audio playback ---

    async def _play_node_audio(self, node: Node):
        """Send pre-generated audio for a node."""
        self.phase = CallPhase.PLAYING_AUDIO
        self.barge_in_speech_count = 0

        raw_mulaw = self._audio_data.get(node.id)

        if not raw_mulaw:
            logger.warning("No audio data for node %s, skipping", node.id)
            self.phase = CallPhase.LISTENING
            self.audio_buffer.clear()
            self.vad.reset()
            return

        n_chunks = (len(raw_mulaw) + self.CHUNK_SIZE - 1) // self.CHUNK_SIZE
        logger.info(
            "Playing node %s (%d bytes, %d chunk(s))",
            node.id, len(raw_mulaw), n_chunks,
        )

        # Send audio in large chunks (fewer WS messages = less overhead)
        for i in range(0, len(raw_mulaw), self.CHUNK_SIZE):
            chunk = raw_mulaw[i : i + self.CHUNK_SIZE]
            payload = base64.b64encode(chunk).decode("ascii")
            await self.ws.send_json(
                {
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {"payload": payload},
                }
            )

        # Mark to detect playback completion
        mark_name = f"node-{node.id}-{self.mark_counter}"
        self.mark_counter += 1

        if node.node_type == NodeType.END:
            self.pending_marks[mark_name] = "end_call"
        else:
            self.pending_marks[mark_name] = "playback_complete"

        await self.ws.send_json(
            {
                "event": "mark",
                "streamSid": self.stream_sid,
                "mark": {"name": mark_name},
            }
        )

        logger.info("Audio + mark sent for node %s", node.id)

    # --- Event handlers ---

    async def _handle_mark(self, mark_name: str):
        """Handle mark acknowledgment from Twilio (audio playback finished)."""
        purpose = self.pending_marks.pop(mark_name, None)
        if purpose == "end_call":
            logger.info("End node audio finished, hanging up")
            self.phase = CallPhase.ENDED
            await self._hangup_call()
        elif purpose == "playback_complete":
            logger.info("Audio playback complete, now listening")
            self.phase = CallPhase.LISTENING
            self.audio_buffer.clear()
            self.vad.reset()

    async def _handle_incoming_audio(self, payload_b64: str):
        """Process incoming audio from caller."""
        audio_bytes = base64.b64decode(payload_b64)

        if self.phase == CallPhase.PLAYING_AUDIO:
            # Barge-in: require consecutive speech frames to avoid false triggers
            if self.vad.is_speech_frame(audio_bytes):
                self.barge_in_speech_count += 1
                if self.barge_in_speech_count >= self.BARGE_IN_THRESHOLD:
                    logger.info(
                        "Barge-in confirmed (%d frames), clearing playback",
                        self.barge_in_speech_count,
                    )
                    await self._clear_playback()
                    self.phase = CallPhase.LISTENING
                    self.audio_buffer.clear()
                    self.vad.reset()
                    self.barge_in_speech_count = 0
            else:
                self.barge_in_speech_count = 0
            return

        if self.phase != CallPhase.LISTENING:
            return

        self.audio_buffer.extend(audio_bytes)
        end_of_speech = self.vad.process_frame(audio_bytes)

        if end_of_speech:
            self.phase = CallPhase.PROCESSING
            await self._process_speech()

    # --- Speech processing ---

    async def _process_speech(self):
        """Analyse caller speech and play the matching branch audio.

        Primary path: combined audio-branch (1 API call).
        Fallback:     separate STT → Branch (2 API calls).
        """
        t_start = time.monotonic()

        # Prepare outgoing edges first (needed by both paths)
        outgoing_edges = [
            e
            for e in self.scenario.edges
            if e.source_node_id == self.current_node.id
        ]

        if not outgoing_edges:
            logger.warning("No outgoing edges from node %s", self.current_node.id)
            self.phase = CallPhase.ENDED
            await self._hangup_call()
            return

        conditions = [
            {
                "condition": e.condition_label,
                "target_node_id": e.target_node_id,
            }
            for e in outgoing_edges
        ]

        audio_bytes = bytes(self.audio_buffer)
        decision = None
        transcription = ""

        # --- Primary: combined audio-branch (single API call) ---
        try:
            decision, transcription = (
                await self.audio_branch.decide_from_audio(
                    audio_bytes, conditions, self.current_node.script
                )
            )
            logger.info(
                "Combined AudioBranch in %.0fms: %r -> %s",
                (time.monotonic() - t_start) * 1000,
                transcription,
                decision.target_node_id,
            )
        except Exception:
            logger.warning(
                "Combined AudioBranch failed, falling back to STT+Branch",
                exc_info=True,
            )

            # --- Fallback: separate STT → Branch ---
            transcription = await self.stt.transcribe(audio_bytes)
            t_stt = time.monotonic()
            logger.info(
                "STT fallback in %.0fms: %r",
                (t_stt - t_start) * 1000,
                transcription,
            )

            if not transcription or not transcription.strip():
                logger.info("Empty transcription, returning to listening")
                self.phase = CallPhase.LISTENING
                self.audio_buffer.clear()
                self.vad.reset()
                return

            decision = await self.branch.decide(
                transcription, conditions, self.current_node.script
            )
            logger.info(
                "Branch fallback in %.0fms: %s -> %s",
                (time.monotonic() - t_stt) * 1000,
                decision.matched_condition,
                decision.target_node_id,
            )

        # Empty transcription from combined call
        if not transcription or not transcription.strip():
            logger.info("Empty transcription, returning to listening")
            self.phase = CallPhase.LISTENING
            self.audio_buffer.clear()
            self.vad.reset()
            return

        # Find target node
        target_node = self._find_node_by_id(decision.target_node_id)
        if not target_node:
            logger.error("Target node %s not found", decision.target_node_id)
            self.phase = CallPhase.LISTENING
            self.audio_buffer.clear()
            self.vad.reset()
            return

        self.current_node = target_node
        self.audio_buffer.clear()

        logger.info(
            "Total processing: %.0fms", (time.monotonic() - t_start) * 1000
        )

        await self._play_node_audio(target_node)

    # --- Utilities ---

    async def _clear_playback(self):
        """Send clear message to Twilio to stop current audio playback."""
        await self.ws.send_json(
            {"event": "clear", "streamSid": self.stream_sid}
        )
        self.pending_marks.clear()

    async def _hangup_call(self):
        """Terminate the call via Twilio REST API."""
        if not self.call_sid:
            logger.warning("No call_sid, cannot hang up")
            return

        try:
            url = (
                f"https://api.twilio.com/2010-04-01/Accounts/"
                f"{self.settings.twilio_account_sid}/Calls/{self.call_sid}.json"
            )
            async with httpx.AsyncClient() as client:
                await client.post(
                    url,
                    data={"Status": "completed"},
                    auth=(
                        self.settings.twilio_account_sid,
                        self.settings.twilio_auth_token,
                    ),
                )
            logger.info("Call %s hung up successfully", self.call_sid)
        except Exception:
            logger.exception("Failed to hang up call %s", self.call_sid)
