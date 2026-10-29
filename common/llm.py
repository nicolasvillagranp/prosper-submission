"""Structured Claude calls shared by the morning job and the audio briefing."""

from __future__ import annotations

from pydantic import BaseModel

from common.config import CONFIG

MODEL = CONFIG["llm"]["research_model"]
LANGUAGE = {"es": "Spanish", "en": "English"}


class LLMError(RuntimeError):
    pass


def ask(client, schema: type[BaseModel], system: str, user: str, effort: str, max_tokens: int = 16000):
    """One structured call. Server-side fallback in case Sonnet's safety filter declines."""
    response = client.beta.messages.parse(
        model=MODEL, max_tokens=max_tokens,
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        output_config={"effort": effort},
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
        output_format=schema,
    )
    if response.stop_reason != "end_turn" or response.parsed_output is None:
        raise LLMError(f"no {schema.__name__}: stop_reason={response.stop_reason}")
    return response.parsed_output
