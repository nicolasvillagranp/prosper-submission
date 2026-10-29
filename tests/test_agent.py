import asyncio
import json

import pytest

from agent.expert import SAMPLE, latency_summary, load_topic
from agent.prompt import build_instructions
from common import db
from livekit.agents import tokenize
from schema.models import Topic


def sample() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def test_prompt_has_persona_rules_brief_and_sources():
    topic = Topic.model_validate(sample())
    prompt = build_instructions(topic)
    assert prompt.startswith("You are Lucía Arenas")
    assert "Always speak Spanish (es-ES)" in prompt
    assert "at most 2 spoken sentences" in prompt  # answer_length: short
    assert "Never invent numbers" in prompt
    assert "fictional character voiced by an AI" in prompt
    assert topic.brief.strip() in prompt
    assert "[1] " in prompt and f"[{len(topic.sources)}] " in prompt


def test_prompt_follows_the_topic_config():
    data = sample()
    data["config"].update(answer_length="long", audience_level="beginner")
    prompt = build_instructions(Topic.model_validate(data))
    assert "at most 4 spoken sentences" in prompt
    assert "no jargon" in prompt


def test_console_and_playground_get_the_sample_topic():
    assert load_topic(None).persona.name == "Lucía Arenas"
    assert load_topic('{"something": "else"}').persona.name == "Lucía Arenas"


class FakeQuery:
    def __init__(self, rows):
        self.rows, self.filters = rows, {}

    def select(self, *_):
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def limit(self, _):
        return self

    def execute(self):
        return type("Result", (), {"data": [r for r in self.rows if r["id"] == self.filters.get("id")]})


class FakeDB:
    def __init__(self, rows):
        self.query = FakeQuery(rows)

    def table(self, name):
        assert name == "topics"
        return self.query


def test_dispatched_job_loads_its_topic_from_supabase(monkeypatch):
    row = {"id": "t-1", "user_id": "u-1", "date": "2026-10-25", "rank": 1, **sample()}
    monkeypatch.setattr(db, "client", lambda: FakeDB([row]))
    assert load_topic('{"topic_id": "t-1"}').title == row["title"]
    with pytest.raises(LookupError):
        load_topic('{"topic_id": "missing"}')


def test_pronunciations_reach_the_voice_even_when_streamed_in_pieces():
    async def stream():
        for chunk in ["Habla de Ge", "nie 3 y de Deep", "Mind. "]:
            yield chunk

    async def speak():
        out = tokenize.utils.replace_words(text=stream(), replacements=sample()["config"]["pronunciations"])
        return "".join([c async for c in out])

    spoken = asyncio.run(speak())
    assert "Yíni" in spoken and "Dip Maind" in spoken and "Genie" not in spoken


def test_latency_summary():
    assert latency_summary([]) == "no replies measured"
    assert latency_summary([0.8, 1.4, 0.6]) == "3 replies, median 0.80s, max 1.40s"


def test_the_host_can_pick_an_allowed_voice_only():
    blanca = "538a8872-3799-4df5-b373-b78493b766c6"  # Spanish voice in config/voices.yaml
    marian = "26403c37-80c1-4a1a-8692-540551ca2ae5"  # English voice: not for a Spanish topic
    assert load_topic(json.dumps({"voice_id": blanca})).config.tts.voice_id == blanca
    assert load_topic(json.dumps({"voice_id": marian})).config.tts.voice_id == sample()["config"]["tts"]["voice_id"]
    assert load_topic(json.dumps({"voice_id": "made-up"})).config.tts.voice_id == sample()["config"]["tts"]["voice_id"]
