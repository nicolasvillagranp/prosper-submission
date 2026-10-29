"""Loads config/config.yaml (product settings) and .env (secrets)."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

load_dotenv(ROOT / ".env")

with open(ROOT / "config" / "config.yaml", encoding="utf-8") as f:
    CONFIG: dict = yaml.safe_load(f)


def require(name: str) -> str:
    """The environment variable `name`, or a clear error naming what's missing."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing {name} in .env (see .env.example)")
    return value
