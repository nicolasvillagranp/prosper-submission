"""The data shared by the morning job, the agent and the web server.

A Topic is everything the expert needs for one interview: who it is (persona), how it
speaks (config), what it knows (brief, sources) and what the host studies (study_dialogue).
The same shapes are stored in Supabase as jsonb and checked here before every write.
"""

from __future__ import annotations

import re
from typing import Literal

import yaml
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from common.config import CONFIG, ROOT

Language = Literal["es", "en"]
Depth = Literal["beginner", "intermediate", "expert"]
Tone = Literal["explainer", "balanced", "sparring"]
# Cartesia sonic-3 emotions that suit an interview (the plugin accepts many more).
Emotion = Literal["Calm", "Curious", "Content", "Enthusiastic", "Excited", "Trust", "Sympathetic", "Anticipation"]

with open(ROOT / "config" / "voices.yaml", encoding="utf-8") as f:
    VOICES: dict[str, list[dict]] = yaml.safe_load(f)


class Profile(BaseModel):
    """What the user sets at onboarding and can change in Settings."""

    interests: str = Field(min_length=3, max_length=2000)
    language: Language = "es"
    depth: Depth = "intermediate"
    tone: Tone = "balanced"


class Persona(BaseModel):
    """A fictional expert. Never a real person, never someone's voice."""

    name: str = Field(min_length=2, max_length=80)
    background: str = Field(min_length=20, max_length=800)
    expertise: str = Field(min_length=3, max_length=200)
    default_stance: str = Field(min_length=10, max_length=400)
    speaking_style: str = Field(min_length=10, max_length=400)


class TTSConfig(BaseModel):
    voice_id: str
    speed: float = Field(1.0, ge=0.6, le=1.5)
    emotion: list[Emotion] = Field(default_factory=list, max_length=2)


class LLMConfig(BaseModel):
    # No temperature: the Claude 5 models reject it.
    model: str = CONFIG["llm"]["live_model"]


class TurnsConfig(BaseModel):
    """Silence before the host's turn counts as finished."""

    min_endpointing_ms: int = Field(int(CONFIG["voice"]["min_delay"] * 1000), ge=100, le=2000)
    max_endpointing_ms: int = Field(int(CONFIG["voice"]["max_delay"] * 1000), ge=300, le=5000)

    @model_validator(mode="after")
    def min_below_max(self) -> TurnsConfig:
        if self.min_endpointing_ms > self.max_endpointing_ms:
            raise ValueError("min_endpointing_ms must not exceed max_endpointing_ms")
        return self


class VoiceOption(BaseModel):
    """One voice the host can pick for this expert, as scored by the writer."""

    voice_id: str
    score: int = Field(ge=0, le=100)
    why: str = Field(max_length=200)


class SessionConfig(BaseModel):
    """How the expert behaves and sounds in this interview."""

    language: Language
    accent: str = Field(min_length=2, max_length=20)
    audience_level: Depth  # the spec's "register": how technical the answers are
    stance: str = Field(min_length=10, max_length=400)
    answer_length: Literal["short", "medium", "long"] = "short"
    sensitivity: Literal["low", "medium", "high"] = "medium"
    pronunciations: dict[str, str] = Field(default_factory=dict)  # written form -> how TTS should say it
    tts: TTSConfig
    voice_options: list[VoiceOption] = Field(default_factory=list, max_length=3)  # best first
    llm: LLMConfig = Field(default_factory=LLMConfig)
    turns: TurnsConfig = Field(default_factory=TurnsConfig)

    @model_validator(mode="after")
    def voice_is_allowed(self) -> SessionConfig:
        allowed = {v["id"] for v in VOICES.get(self.language, [])}
        for voice in [self.tts.voice_id, *(o.voice_id for o in self.voice_options)]:
            if voice not in allowed:
                raise ValueError(f"voice {voice} is not in config/voices.yaml for '{self.language}'")
        return self


class Source(BaseModel):
    n: int = Field(ge=1)
    title: str
    url: HttpUrl
    date: str | None = None
    publisher: str | None = None


CITATION = re.compile(r"\[(\d+)\]")


class Topic(BaseModel):
    """One of the user's daily topics: a ready-to-record interview."""

    title: str = Field(min_length=5, max_length=160)
    summary: str = Field(min_length=20, max_length=600)
    persona: Persona
    config: SessionConfig
    brief: str = Field(min_length=200)
    study_dialogue: str = Field(min_length=200)
    sources: list[Source] = Field(min_length=1)

    @field_validator("sources")
    @classmethod
    def numbered_once(cls, sources: list[Source]) -> list[Source]:
        numbers = [s.n for s in sources]
        if len(numbers) != len(set(numbers)):
            raise ValueError("source numbers must be unique")
        return sources

    @model_validator(mode="after")
    def citations_exist(self) -> Topic:
        known = {s.n for s in self.sources}
        cited = {int(n) for n in CITATION.findall(self.brief + self.study_dialogue)}
        if missing := sorted(cited - known):
            raise ValueError(f"cited sources {missing} are not in sources")
        if not cited:
            raise ValueError("the brief must cite its sources as [n]")
        return self
