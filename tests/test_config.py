import pytest

from common.config import CONFIG, require


def test_config_has_the_sections_every_part_reads():
    assert {"llm", "morning", "voice"} <= CONFIG.keys()
    assert CONFIG["morning"]["topics_per_day"] == 5


def test_require_names_the_missing_variable(monkeypatch):
    monkeypatch.delenv("SOME_MISSING_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SOME_MISSING_KEY"):
        require("SOME_MISSING_KEY")
