"""Writes the page's voice picker data from config/voices.yaml: one short mp3 per voice and a list.

    python -m pipeline.voice_samples          # only voices without a sample yet
    python -m pipeline.voice_samples --all    # redo every sample

    web/public/voices/<voice_id>.mp3   what the "Sample" button plays (static, same for everyone)
    web/src/voices.json                id -> name, gender, accent, language

Run it again after changing config/voices.yaml.
"""

from __future__ import annotations

import argparse
import json

import httpx

from common.config import ROOT
from pipeline.briefing import synthesize
from schema.models import VOICES

LINE = {
    "es": "Hola, esta es mi voz. Cuando quieras, empezamos la entrevista.",
    "en": "Hi, this is my voice. Whenever you're ready, let's start the interview.",
}
SAMPLES = ROOT / "web" / "public" / "voices"
LIST = ROOT / "web" / "src" / "voices.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Voice samples and list for the page's voice picker.")
    parser.add_argument("--all", action="store_true", help="redo samples that already exist")
    args = parser.parse_args()
    SAMPLES.mkdir(parents=True, exist_ok=True)
    listing = {}
    with httpx.Client() as http:
        for language, voices in VOICES.items():
            for v in voices:
                listing[v["id"]] = {"name": v["name"], "gender": v["gender"], "accent": v["accent"], "language": language}
                out = SAMPLES / f"{v['id']}.mp3"
                if out.exists() and not args.all:
                    continue
                out.write_bytes(synthesize(http, LINE[language], language, voice=v["id"]))
                print(f"sample: {language} {v['name']}")
    LIST.write_text(json.dumps(listing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(listing)} voices in {LIST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
