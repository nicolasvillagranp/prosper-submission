"""The audio briefing with fake Claude, Cartesia and Supabase Storage."""

import json
from types import SimpleNamespace

import pytest

from common.config import CONFIG, ROOT
from pipeline.briefing import BriefingScript, chunks, get_briefing, spoken

SAMPLE = json.loads((ROOT / "samples" / "world-models.json").read_text(encoding="utf-8"))
SCRIPT = "Hoy hablamos de Genie, el modelo de DeepMind.\n\nSegundo párrafo.\n\nPuedes entrevistar a Lucía Arenas."


class FakeLLM:
    def __init__(self):
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self.parse))

    def parse(self, *, output_format, system, messages, **kwargs):
        assert output_format is BriefingScript
        self.calls.append((system[0]["text"], messages[0]["content"], kwargs))
        return SimpleNamespace(parsed_output=BriefingScript(script=SCRIPT), stop_reason="end_turn")


class FakeHTTP:
    def __init__(self):
        self.posts = []

    def post(self, url, headers, json, timeout):
        self.posts.append(json)
        return SimpleNamespace(content=b"MP3" + str(len(self.posts)).encode(), raise_for_status=lambda: None)


class FakeStore:
    def __init__(self, files):
        self.files = files

    def list(self, folder, options):
        return [{"name": p.rsplit("/", 1)[1]} for p in self.files
                if p.startswith(folder + "/") and options["search"] in p]

    def download(self, path):
        return self.files[path]

    def upload(self, path, data, options):
        self.files[path] = data


class FakeQuery:
    def __init__(self, rows):
        self.rows, self.filters = rows, []

    def select(self, *_):
        return self

    def eq(self, col, val):
        self.filters.append((col, val))
        return self

    def limit(self, _):
        return self

    def execute(self):
        return SimpleNamespace(data=[r for r in self.rows if all(r[c] == v for c, v in self.filters)])


class FakeDB:
    def __init__(self, rows):
        self.rows, self.files = rows, {}
        self.storage = SimpleNamespace(from_=lambda bucket: FakeStore(self.files))

    def table(self, name):
        assert name == "topics"
        return FakeQuery(self.rows)


def topic_row(**changes):
    return {"id": "t1", "user_id": "u1", "date": "2026-10-27", "rank": 1, **SAMPLE, **changes}


def test_first_listen_writes_the_script_reads_it_and_caches_both():
    db, llm, http = FakeDB([topic_row()]), FakeLLM(), FakeHTTP()
    b = get_briefing(db, llm, http, "t1", "u1")

    assert b.created and b.script == SCRIPT
    assert b.audio_path == "u1/briefings/t1.mp3"
    assert db.files["u1/briefings/t1.txt"] == SCRIPT.encode("utf-8")
    assert db.files["u1/briefings/t1.mp3"] == b"MP31"  # one chunk: the script is short

    request = http.posts[0]
    assert request["voice"]["id"] == CONFIG["briefing"]["narrator"]["es"]
    assert request["language"] == "es"
    assert request["output_format"]["container"] == "mp3"
    # the voice reads the pronunciations; the saved script keeps the real names
    assert "Yíni" in request["transcript"] and "Dip Maind" in request["transcript"]
    assert "Genie" in b.script


def test_second_listen_is_free():
    db, llm, http = FakeDB([topic_row()]), FakeLLM(), FakeHTTP()
    get_briefing(db, llm, http, "t1", "u1")
    again = get_briefing(db, llm, http, "t1", "u1")
    assert not again.created and again.script == SCRIPT
    assert len(llm.calls) == 1 and len(http.posts) == 1


def test_someone_elses_topic_is_not_found():
    with pytest.raises(LookupError):
        get_briefing(FakeDB([topic_row()]), FakeLLM(), FakeHTTP(), "t1", "u2")


def test_the_script_prompt_has_the_brief_the_expert_and_the_length():
    llm = FakeLLM()
    get_briefing(FakeDB([topic_row()]), llm, FakeHTTP(), "t1", "u1")
    system, user, kwargs = llm.calls[0]
    assert f"About {CONFIG['briefing']['words']} words" in system
    assert "Today's expert: Lucía Arenas" in user
    assert SAMPLE["brief"] in user and "Language: Spanish" in user
    assert kwargs["model"] == "claude-sonnet-5-5"


def test_english_topics_get_the_english_narrator():
    data = {**SAMPLE, "config": {**SAMPLE["config"], "language": "en", "accent": "en",
                                 "tts": {"voice_id": "26403c37-80c1-4a1a-8692-540551ca2ae5"}}}
    http = FakeHTTP()
    get_briefing(FakeDB([topic_row(**data)]), FakeLLM(), http, "t1", "u1")
    assert http.posts[0]["voice"]["id"] == CONFIG["briefing"]["narrator"]["en"]
    assert http.posts[0]["language"] == "en"


def test_long_scripts_are_read_in_paragraph_chunks():
    paras = [f"Párrafo {i}. " + "palabra " * 60 for i in range(6)]  # ~490 chars each
    pieces = chunks("\n\n".join(paras), limit=1200)
    assert len(pieces) == 3 and all(len(p) <= 1200 for p in pieces)
    assert "\n\n".join(pieces) == "\n\n".join(p.strip() for p in paras)


def test_pronunciations_match_whole_words_longest_first():
    said = spoken("El AI Act y la IA; Gemini no es Geminis.", {"AI Act": "Ei Ai Akt", "AI": "Ei Ai", "Gemini": "Yémini"})
    assert said == "El Ei Ai Akt y la IA; Yémini no es Geminis."


def test_narrator_voices_are_never_given_to_experts():
    from pipeline.generate import NARRATORS
    from schema.models import VOICES
    assert NARRATORS == set(CONFIG["briefing"]["narrator"].values())
    assert all(any(v["id"] == n for v in VOICES[lang]) for lang, n in CONFIG["briefing"]["narrator"].items())
