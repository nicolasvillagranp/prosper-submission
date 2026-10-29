"""The live expert: a LiveKit Agents worker that plays one topic's persona.

Same pattern as Orbio's backend-layer/voice/agent.py: Deepgram STT, Cartesia TTS and Silero
VAD called directly with their own keys, LiveKit Cloud only carrying the audio. Claude writes
the replies from a prompt built from the topic (agent/prompt.py).

    python -m agent.expert          # talk from the terminal with the sample topic (= console)
    python -m agent.expert dev      # register as AGENT_NAME; the web server dispatches jobs
                                    # with metadata {"topic_id": ...} (Agents Playground too)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import statistics
import sys
from collections.abc import AsyncIterable

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    ConversationItemAddedEvent,
    NOT_GIVEN,
    JobContext,
    ModelSettings,
    cli,
    room_io,
    tokenize,
)
from livekit.plugins import anthropic, cartesia, deepgram, silero

from agent.prompt import GOODBYE, GREETING, build_instructions
from common.config import ROOT
from schema.models import VOICES, Topic

logger = logging.getLogger("expert")

AGENT_NAME = os.getenv("AGENT_NAME") or "expert"
MAX_SESSION_MIN = float(os.getenv("MAX_SESSION_MIN") or 20)
SAMPLE = ROOT / "samples" / "world-models.json"


def load_topic(metadata: str | None) -> Topic:
    """The topic named in the job metadata, or the sample when there is none (console, playground).

    The page may send the voice the host picked (`voice_id`); it replaces the topic's voice only
    if config/voices.yaml allows it for the topic's language."""
    meta = json.loads(metadata or "{}")
    if not meta.get("topic_id"):
        topic = Topic.model_validate_json(SAMPLE.read_text(encoding="utf-8"))
    else:
        from common.db import load_topic as load_from_db  # only jobs from the page need Supabase

        topic = load_from_db(meta["topic_id"])
    voice = meta.get("voice_id")
    if voice and voice in {v["id"] for v in VOICES[topic.config.language]}:
        topic.config.tts.voice_id = voice
    return topic


def latency_summary(latencies: list[float]) -> str:
    """Median and worst reply latency (host stops speaking -> expert starts), for the logs."""
    if not latencies:
        return "no replies measured"
    return (f"{len(latencies)} replies, median {statistics.median(latencies):.2f}s, "
            f"max {max(latencies):.2f}s")


class Expert(Agent):
    def __init__(self, topic: Topic):
        super().__init__(instructions=build_instructions(topic))
        self.pronunciations = topic.config.pronunciations

    async def tts_node(self, text: AsyncIterable[str], model_settings: ModelSettings):
        """Spell names the way the voice should say them (e.g. Genie -> Yíni). The transcript keeps the original."""
        if self.pronunciations:
            text = tokenize.utils.replace_words(text=text, replacements=self.pronunciations)
        async for frame in Agent.default.tts_node(self, text, model_settings):
            yield frame


server = AgentServer()


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: JobContext) -> None:
    topic = await asyncio.to_thread(load_topic, ctx.job.metadata)
    meta = json.loads(ctx.job.metadata or "{}")
    session_id, record = meta.get("session_id"), meta.get("record") is True
    cfg = topic.config
    await ctx.connect()

    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language=cfg.language,
                         keyterm=list(cfg.pronunciations) or NOT_GIVEN),  # helps it hear the names
        llm=anthropic.LLM(model=cfg.llm.model, max_tokens=400, caching="ephemeral"),
        tts=cartesia.TTS(model="sonic-3", voice=cfg.tts.voice_id, language=cfg.language,
                         speed=cfg.tts.speed, emotion=cfg.tts.emotion or None),
        vad=silero.VAD.load(),
        # VAD + endpointing only: the default turn detector would call LiveKit Inference in dev
        # and load a ~244 MB model; revisit if turn-taking feels bad.
        turn_handling={"turn_detection": "vad",
                       "endpointing": {"min_delay": cfg.turns.min_endpointing_ms / 1000,
                                       "max_delay": cfg.turns.max_endpointing_ms / 1000}},
    )

    latencies: list[float] = []

    @session.on("conversation_item_added")
    def log_latency(ev: ConversationItemAddedEvent) -> None:
        item = ev.item
        if getattr(item, "role", None) == "assistant" and (e2e := item.metrics.get("e2e_latency")) is not None:
            latencies.append(e2e)
            logger.info("reply latency %.2fs (llm ttft %.2fs, tts ttfb %.2fs)", e2e,
                        item.metrics.get("llm_node_ttft", float("nan")),
                        item.metrics.get("tts_node_ttfb", float("nan")))

    # Who has the floor, for debugging turn-taking from the logs (e.g. a noisy mic that never goes silent).
    session.on("user_state_changed", lambda ev: logger.info("host: %s", ev.new_state))
    session.on("agent_state_changed", lambda ev: logger.info("expert: %s", ev.new_state))

    async def end_at_cap() -> None:
        """Session cap: say goodbye at MAX_SESSION_MIN, then close once it has been spoken."""
        await asyncio.sleep(MAX_SESSION_MIN * 60)
        logger.info("session cap of %s min reached", MAX_SESSION_MIN)
        await session.generate_reply(instructions=GOODBYE, allow_interruptions=False)
        session.shutdown(drain=True)

    async def on_shutdown() -> None:
        cap.cancel()  # the host may have left first
        logger.info("session latency: %s", latency_summary(latencies))
        if not session_id:  # console / playground: nothing to save
            return
        await session.aclose()  # makes sure the recorder has written its file
        from agent.episodes import save_episode, transcript_from
        from common.db import client

        recording = ctx.session_directory / "audio.ogg" if record else None
        await asyncio.to_thread(save_episode, client(), session_id, transcript_from(session.history.items), recording)

    # Audio only if the host ticked "record"; never traces, logs or transcripts to LiveKit Cloud.
    await session.start(room=ctx.room, agent=Expert(topic),
                        room_options=room_io.RoomOptions(delete_room_on_close=True),
                        record={"audio": record, "traces": False, "logs": False, "transcript": False})
    session.generate_reply(instructions=GREETING)
    cap = asyncio.create_task(end_at_cap())
    ctx.add_shutdown_callback(on_shutdown)


if __name__ == "__main__":
    if len(sys.argv) == 1:  # no command: just talk to it
        sys.argv.append("console")
    cli.run_app(server)
