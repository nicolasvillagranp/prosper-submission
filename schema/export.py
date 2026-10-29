"""Writes schema/topic.schema.json, the shape the morning job asks the LLM to fill.

    python -m schema.export
"""

import json

from common.config import ROOT
from schema.models import Topic

SCHEMA_PATH = ROOT / "schema" / "topic.schema.json"


def topic_schema() -> str:
    return json.dumps(Topic.model_json_schema(), indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    SCHEMA_PATH.write_text(topic_schema(), encoding="utf-8")
    print(f"Wrote {SCHEMA_PATH.relative_to(ROOT)}")
