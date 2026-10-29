"""Topic covers with fake Claude, OpenAI and Storage."""

import base64
from types import SimpleNamespace

from pipeline.covers import Subjects, cover_path, make_covers


class FakeLLM:
    def __init__(self, subjects):
        self.subjects, self.prompts = subjects, []
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self.parse))

    def parse(self, *, output_format, messages, **_):
        assert output_format is Subjects
        self.prompts.append(messages[0]["content"])
        return SimpleNamespace(parsed_output=Subjects(subjects=self.subjects), stop_reason="end_turn")


class FakeHTTP:
    def __init__(self, fail_on=""):
        self.fail_on, self.prompts = fail_on, []

    def post(self, url, timeout, headers, json):
        self.prompts.append(json["prompt"])
        assert json["model"] == "gpt-image-1-mini" and json["quality"] == "low"

        def check():
            if self.fail_on and self.fail_on in json["prompt"]:
                raise RuntimeError("openai down")

        return SimpleNamespace(raise_for_status=check, json=lambda: {"data": [{"b64_json": base64.b64encode(b"JPG").decode()}]})


def fake_db():
    files = {}
    store = SimpleNamespace(upload=lambda path, data, opts: files.__setitem__(path, data))
    return SimpleNamespace(storage=SimpleNamespace(from_=lambda bucket: store)), files


TOPICS = [{"id": f"t{i}", "user_id": "u1", "title": f"Tema {i}", "summary": "resumen"} for i in (1, 2, 3)]


def test_one_cover_per_topic_in_the_paper_style(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    db, files = fake_db()
    http = FakeHTTP()
    assert make_covers(db, FakeLLM(["a cart", "a robot", "a castle"]), http, TOPICS) == 3
    assert sorted(files) == [cover_path("u1", t) for t in ("t1", "t2", "t3")]
    assert all("paper-cut collage" in p and "No text" in p for p in http.prompts)


def test_a_failed_cover_is_skipped_and_missing_subjects_fall_back_to_the_title(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    db, files = fake_db()
    http = FakeHTTP(fail_on="a robot")
    assert make_covers(db, FakeLLM(["a cart", "a robot"]), http, TOPICS) == 2  # robot failed; t3 used its title
    assert cover_path("u1", "t2") not in files
    assert any(p.startswith("Tema 3.") for p in http.prompts)


def test_no_topics_no_calls():
    assert make_covers(None, None, None, []) == 0
