import base64
import enum
import json
import logging
import time

import httpx
from starlette.websockets import WebSocket, WebSocketDisconnect

from backend.config import Settings
from backend.models import Node, NodeType, Scenario
from backend.services.audio_utils import mulaw_8khz_to_pcm_16khz
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

    CHUNK_SIZE = 640  # 80ms of mulaw 8kHz audio

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
        self.stt = create_stt_service(settings)
        self.branch = create_branch_service(settings)

        self.mark_counter = 0
        self.pending_marks: dict[str, str] = {}

        # Barge-in requires sustained speech to avoid false triggers from noise
        self.barge_in_speech_count = 0
        self.BARGE_IN_THRESHOLD = 150  # 150 frames × 20ms = 3 seconds of speech needed

    def _find_start_node(self) -> Node:
        for node in self.scenario.nodes:
            if node.node_type == NodeType.START:
                return node
        # Fallback: first node
        if self.scenario.nodes:
            return self.scenario.nodes[0]
        raise ValueError("Scenario has no nodes")

    def _find_node_by_id(self, node_id: str) -> Node | None:
        for node in self.scenario.nodes:
            if node.id == node_id:
                return node
        return None

    async def run(self):
        """Main loop: receive Twilio WebSocket messages and dispatch."""
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

    async def _play_node_audio(self, node: Node):
        """Send pre-generated audio for a node in chunks."""
        self.phase = CallPhase.PLAYING_AUDIO
        self.barge_in_speech_count = 0

        if not node.audio_cache or not node.audio_cache.audio_data:
            logger.warning(
                "No audio data for node %s (cache=%s), skipping playback",
                node.id,
                "exists" if node.audio_cache else "None",
            )
            self.phase = CallPhase.LISTENING
            self.audio_buffer.clear()
            self.vad.reset()
            return

        raw_mulaw = node.audio_cache.audio_data

        logger.info(
            "Playing audio for node %s (%d bytes, %d chunks)",
            node.id,
            len(raw_mulaw),
            (len(raw_mulaw) + self.CHUNK_SIZE - 1) // self.CHUNK_SIZE,
        )

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

        # Send a mark to detect playback completion
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
                        "Barge-in confirmed (%d consecutive speech frames), clearing playback",
                        self.barge_in_speech_count,
                    )
                    await self._clear_playback()
                    self.phase = CallPhase.LISTENING
                    self.audio_buffer.clear()
                    self.vad.reset()
                    self.barge_in_speech_count = 0
            else:
                # Reset counter on non-speech frame
                self.barge_in_speech_count = 0
            return

        if self.phase != CallPhase.LISTENING:
            return

        self.audio_buffer.extend(audio_bytes)
        end_of_speech = self.vad.process_frame(audio_bytes)

        if end_of_speech:
            self.phase = CallPhase.PROCESSING
            await self._process_speech()

    async def _process_speech(self):
        """STT -> Branch Decision -> Play Next Node audio."""
        t_start = time.monotonic()

        # Convert mulaw 8kHz -> PCM 16kHz for Whisper
        pcm_audio = mulaw_8khz_to_pcm_16khz(bytes(self.audio_buffer))

        # STT
        transcription = await self.stt.transcribe(pcm_audio)
        t_stt = time.monotonic()
        logger.info(
            "STT completed in %.0fms: %r",
            (t_stt - t_start) * 1000,
            transcription,
        )

        if not transcription or not transcription.strip():
            logger.info("Empty transcription, returning to listening")
            self.phase = CallPhase.LISTENING
            self.audio_buffer.clear()
            self.vad.reset()
            return

        # Get outgoing edges from current node
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

        # Branch decision
        conditions = [
            {
                "condition": e.condition_label,
                "target_node_id": e.target_node_id,
            }
            for e in outgoing_edges
        ]
        decision = await self.branch.decide(
            transcription, conditions, self.current_node.script
        )
        t_branch = time.monotonic()
        logger.info(
            "Branch decision in %.0fms: %s -> %s",
            (t_branch - t_stt) * 1000,
            decision.matched_condition,
            decision.target_node_id,
        )

        # Find target node
        target_node = self._find_node_by_id(decision.target_node_id)
        if not target_node:
            logger.error("Target node %s not found", decision.target_node_id)
            self.phase = CallPhase.LISTENING
            self.audio_buffer.clear()
            self.vad.reset()
            return

        # Transition to target node
        self.current_node = target_node
        self.audio_buffer.clear()

        t_total = time.monotonic()
        logger.info(
            "Total processing time: %.0fms", (t_total - t_start) * 1000
        )

        await self._play_node_audio(target_node)

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
