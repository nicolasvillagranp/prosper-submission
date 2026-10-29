import json

import pytest
from pydantic import ValidationError

from common.config import ROOT
from schema.export import SCHEMA_PATH, topic_schema
from schema.models import Profile, Topic

SAMPLE = ROOT / "samples" / "world-models.json"


def sample() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def test_sample_topic_is_valid():
    topic = Topic.model_validate(sample())
    assert topic.config.language == "es"
    assert len(topic.sources) == 7


def test_voice_outside_the_allowlist_is_rejected():
    data = sample()
    data["config"]["tts"]["voice_id"] = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(ValidationError, match="voices.yaml"):
        Topic.model_validate(data)


def test_english_voice_is_rejected_for_a_spanish_expert():
    data = sample()
    data["config"]["tts"]["voice_id"] = "26403c37-80c1-4a1a-8692-540551ca2ae5"  # Marian (en)
    with pytest.raises(ValidationError, match="voices.yaml"):
        Topic.model_validate(data)


@pytest.mark.parametrize("speed", [0.5, 1.6])
def test_speed_out_of_range_is_rejected(speed):
    data = sample()
    data["config"]["tts"]["speed"] = speed
    with pytest.raises(ValidationError):
        Topic.model_validate(data)


def test_citation_without_a_source_is_rejected():
    data = sample()
    data["brief"] += "\n- Una afirmación inventada [9]."
    with pytest.raises(ValidationError, match=r"\[9\]"):
        Topic.model_validate(data)


def test_brief_without_citations_is_rejected():
    data = sample()
    data["brief"] = data["brief"].replace("[", "(").replace("]", ")")
    data["study_dialogue"] = data["study_dialogue"].replace("[", "(").replace("]", ")")
    with pytest.raises(ValidationError, match="cite"):
        Topic.model_validate(data)


def test_endpointing_min_above_max_is_rejected():
    data = sample()
    data["config"]["turns"] = {"min_endpointing_ms": 1500, "max_endpointing_ms": 1000}
    with pytest.raises(ValidationError):
        Topic.model_validate(data)


def test_profile_defaults_and_limits():
    assert Profile(interests="modelos del mundo, robótica").tone == "balanced"
    with pytest.raises(ValidationError):
        Profile(interests="ai", tone="angry")


def test_exported_json_schema_is_up_to_date():
    assert SCHEMA_PATH.read_text(encoding="utf-8") == topic_schema(), "run: python -m schema.export"
