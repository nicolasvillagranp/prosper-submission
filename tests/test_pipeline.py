"""The morning job with fake Claude, Tavily and Supabase: no network, no cost."""

import itertools
from datetime import date
from types import SimpleNamespace

import pytest

from pipeline import research
from pipeline.generate import Picks, SearchPlan, TopicDraft, pick_topics
from pipeline.research import Article, iso_date, search_news
from pipeline.run_daily import run
from schema.models import VOICES, Profile

DAY = date(2026, 10, 26)
LONG = "Texto del artículo con muchos detalles sobre el tema. " * 20
NURIA = VOICES["es"][0]["id"]
BLANCA, REGINA, XIMENA = (next(v["id"] for v in VOICES["es"] if v["name"] == n) for n in ("Blanca", "Regina", "Ximena"))


# Fakes ------------------------------------------------------------------------------------

class FakeTavily:
    def __init__(self, fail=False):
        self.fail, self.queries = fail, []

    def search(self, query, **_):
        if self.fail:
            raise RuntimeError("tavily down")
        self.queries.append(query)
        return {"results": [
            {"title": f"{query} noticia {i}", "url": f"https://news{i}.example.com/{query.replace(' ', '-')}",
             "content": "resumen", "raw_content": LONG, "published_date": "2026-10-25T08:00:00Z"}
            for i in range(1, 5)
        ]}


def draft(**changes) -> TopicDraft:
    data = {
        "title": "Robots que imaginan antes de moverse",
        "summary": "Los modelos del mundo llegan a la robótica. ¿Avance real o demo bonita?",
        "persona": {
            "name": "Marta Quiroga",
            "background": "Ingeniera ficticia con doce años entrenando robots en simulación.",
            "expertise": "simulación para robótica",
            "default_stance": "Entusiasta de la simulación, escéptica con las promesas.",
            "speaking_style": "Directa, con ejemplos cotidianos.",
        },
        "config": {
            "stance": "La simulación ya sirve, pero no sustituye al mundo real.",
            "answer_length": "medium", "sensitivity": "medium",
            "voices": [{"voice_id": BLANCA, "score": 70, "why": "cálida"},
                       {"voice_id": NURIA, "score": 92, "why": "serena y precisa"},
                       {"voice_id": VOICES["en"][0]["id"], "score": 99, "why": "wrong language"},
                       {"voice_id": XIMENA, "score": 55, "why": "acento mexicano"},
                       {"voice_id": REGINA, "score": 40, "why": "demasiado alegre"}],
            "pronunciations": [{"written": "DeepMind", "spoken": "Dip Maind"}],
        },
        "brief": "# Brief\n- Un hecho importante sobre el tema [1].\n- Otro hecho con cifras [2].\n" + "Más contexto. " * 20,
        "study_dialogue": "# Guion\n## Preguntas\n1. ¿Qué cambia esto [1]?\n2. ¿Y las cifras [2]?\n" + "Más preguntas. " * 20,
    }
    data.update(changes)
    return TopicDraft.model_validate(data)


class FakeLLM:
    """Answers each structured call by its schema; `drafts` are handed out in order."""

    def __init__(self, drafts=None, picks=5, bad_name=False):
        self.drafts, self.picks, self.bad_name, self.calls = list(drafts or []), picks, bad_name, []
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self.parse))

    def parse(self, *, output_format, messages, **kwargs):
        self.calls.append((output_format, messages[0]["content"], kwargs))
        if output_format is SearchPlan:
            out = SearchPlan(queries=["robots", "modelos del mundo"])
        elif output_format is Picks:
            out = Picks.model_validate({"topics": [
                {"title": f"Tema {i}", "angle": "¿Qué cambia?", "article_ids": [f"a{i}", f"a{i + 1}", "a999"],
                 "expert_name": "Texto Del" if self.bad_name else f"Experta Inventada {i}",
                 "expert_gender": "feminine"}
                for i in range(1, self.picks + 1)
            ]})
        else:
            out = self.drafts.pop(0) if self.drafts else draft()
        return SimpleNamespace(parsed_output=out, stop_reason="end_turn")


class FakeQuery:
    def __init__(self, db, table):
        self.db, self.table, self.filters, self.op, self.payload = db, table, [], "select", None

    def select(self, *_):
        return self

    def eq(self, col, val):
        self.filters.append(lambda r: r.get(col) == val)
        return self

    def gte(self, col, val):
        self.filters.append(lambda r: r.get(col) >= val)
        return self

    def lt(self, col, val):
        self.filters.append(lambda r: r.get(col) < val)
        return self

    def gt(self, col, val):
        self.filters.append(lambda r: r.get(col) > val)
        return self

    def insert(self, rows):
        self.op, self.payload = "insert", rows
        return self

    def delete(self):
        self.op = "delete"
        return self

    def execute(self):
        rows = self.db.tables.setdefault(self.table, [])
        if self.op == "insert":
            new = [{"id": f"id-{next(self.db.ids)}", **r} for r in self.payload]  # like Postgres: never reused
            rows.extend(new)
            return SimpleNamespace(data=new)
        match = [r for r in rows if all(f(r) for f in self.filters)]
        if self.op == "delete":
            rows[:] = [r for r in rows if r not in match]
        return SimpleNamespace(data=match)


class FakeDB:
    def __init__(self, profiles):
        self.tables = {"profiles": profiles, "topics": []}
        self.ids = itertools.count()

    def table(self, name):
        return FakeQuery(self, name)


def profile(uid="u1", **changes):
    return {"user_id": uid, "interests": "robótica e IA", "language": "es", "depth": "beginner",
            "tone": "sparring", **changes}


# Tests ------------------------------------------------------------------------------------

def test_a_user_gets_five_validated_topics():
    db, llm = FakeDB([profile()]), FakeLLM()
    assert run(db, llm, FakeTavily(), DAY) == {"u1": 5}

    rows = sorted(db.tables["topics"], key=lambda r: r["rank"])
    assert [r["rank"] for r in rows] == [1, 2, 3, 4, 5]
    first = rows[0]
    assert first["date"] == "2026-10-26"
    # sources come from the picked articles, numbered by the code; unknown id a999 dropped
    assert [s["n"] for s in first["sources"]] == [1, 2]
    assert first["sources"][0]["url"].startswith("https://news1.example.com")
    assert first["sources"][0]["publisher"] == "news1.example.com"
    assert first["persona"]["name"] == "Experta Inventada 1"  # the editor's name, not the writer's
    # the profile decides language and depth; plain voice settings
    assert first["config"]["language"] == "es"
    assert first["config"]["audience_level"] == "beginner"
    assert first["config"]["tts"] == {"voice_id": NURIA, "speed": 1.0, "emotion": []}
    # Claude's scores: best first, top 3, voices of another language dropped; accent from the best voice
    assert [(o["voice_id"], o["score"]) for o in first["config"]["voice_options"]] == [(NURIA, 92), (BLANCA, 70), (XIMENA, 55)]
    assert first["config"]["accent"] == "es-ES"
    assert first["config"]["pronunciations"] == {"DeepMind": "Dip Maind"}


def test_the_writer_sees_tone_depth_voices_and_numbered_articles():
    llm = FakeLLM()
    run(FakeDB([profile()]), llm, FakeTavily(), DAY)
    write_prompt = next(content for schema, content, _ in llm.calls if schema is TopicDraft)
    assert "sparring partner" in write_prompt
    assert "Listener's depth: beginner" in write_prompt
    assert "Expert's name: Experta Inventada" in write_prompt
    feminine_es = {v["id"] for v in VOICES["es"] if v["gender"] == "feminine"}
    offered = {v["id"] for v in VOICES["es"] + VOICES["en"] if v["id"] in write_prompt}
    assert offered == feminine_es  # only the editor's gender, only the listener's language
    assert "### [1] " in write_prompt and "### [2] " in write_prompt


def test_calls_use_sonnet_with_structured_output_and_fallback():
    llm = FakeLLM()
    run(FakeDB([profile()]), llm, FakeTavily(), DAY)
    _, _, kwargs = llm.calls[0]
    assert kwargs["model"] == "claude-sonnet-5-5"
    assert kwargs["fallbacks"] == "default"
    assert "temperature" not in kwargs


def test_an_invalid_draft_is_retried_once_with_the_error():
    bad = draft(brief=draft().brief + "\n- Un dato sin fuente [9].")
    llm = FakeLLM(drafts=[bad])
    assert run(FakeDB([profile()]), llm, FakeTavily(), DAY) == {"u1": 5}
    retries = [c for s, c, _ in llm.calls if s is TopicDraft and "previous answer was rejected" in c]
    assert len(retries) == 1 and "[9]" in retries[0]


def test_a_topic_that_fails_twice_is_skipped_and_the_rest_saved():
    bad = draft(config={**draft().config.model_dump(), "voices": [{"voice_id": VOICES["en"][0]["id"], "score": 90, "why": "x"}]})
    db = FakeDB([profile()])
    assert run(db, FakeLLM(drafts=[bad, bad]), FakeTavily(), DAY) == {"u1": 4}
    assert sorted(r["rank"] for r in db.tables["topics"]) == [1, 2, 3, 4]


def test_a_persona_named_like_someone_in_the_articles_is_rejected():
    llm = FakeLLM(bad_name=True)
    assert run(FakeDB([profile()]), llm, FakeTavily(), DAY) == {"u1": 0}
    assert any("appears in the articles" in c for s, c, _ in llm.calls if s is TopicDraft)


def test_a_failing_user_does_not_stop_the_others():
    db = FakeDB([profile("u1"), profile("u2")])

    class Flaky(FakeTavily):
        failures = 2  # both of the first user's queries

        def search(self, query, **kw):
            if self.failures:
                self.failures -= 1
                raise RuntimeError("down for the first user")
            return super().search(query, **kw)

    assert run(db, FakeLLM(), Flaky(), DAY) == {"u1": 0, "u2": 5}


def test_users_with_a_full_day_are_skipped_unless_forced():
    db, llm = FakeDB([profile()]), FakeLLM()
    run(db, llm, FakeTavily(), DAY)
    calls = len(llm.calls)
    assert run(db, llm, FakeTavily(), DAY) == {}
    assert len(llm.calls) == calls
    assert run(db, llm, FakeTavily(), DAY, force=True) == {"u1": 5}


def test_a_shorter_rerun_removes_leftover_ranks():
    db = FakeDB([profile()])
    run(db, FakeLLM(), FakeTavily(), DAY)
    run(db, FakeLLM(picks=3), FakeTavily(), DAY, force=True)
    assert sorted(r["rank"] for r in db.tables["topics"]) == [1, 2, 3]


def test_recent_topics_are_passed_to_the_editor():
    db = FakeDB([profile()])
    db.tables["topics"].append({"user_id": "u1", "date": "2026-10-24", "rank": 1, "title": "Tema de anteayer"})
    llm = FakeLLM()
    run(db, llm, FakeTavily(), DAY)
    pick_prompt = next(c for s, c, _ in llm.calls if s is Picks)
    assert "Tema de anteayer" in pick_prompt


def test_unknown_user_is_an_error():
    with pytest.raises(SystemExit):
        run(FakeDB([profile()]), FakeLLM(), FakeTavily(), DAY, user_id="nobody")


def test_pick_keeps_only_known_articles():
    articles = [Article(id="a1", title="t", url="https://x.com/1", snippet="", text=LONG)]
    picks = pick_topics(FakeLLM(picks=2), Profile.model_validate(profile()), articles, 5, [])
    assert [p.article_ids for p in picks] == [["a1"]]  # a2/a3/a999 don't exist; the second pick is empty


def test_search_dedupes_drops_thin_pages_and_fetches_missing_text(monkeypatch):
    class Tavily:
        def search(self, query, **_):
            return {"results": [
                {"title": "Same", "url": "https://a.com/1", "content": "s", "raw_content": LONG},
                {"title": "No text", "url": "https://b.com/2", "content": "s", "raw_content": None},
                {"title": "Thin", "url": "https://c.com/3", "content": "s", "raw_content": "short"},
            ]}

    monkeypatch.setattr(research, "fetch_text", lambda url: LONG if "b.com" in url else "")
    found = search_news(Tavily(), ["q1", "q2"], per_query=5)
    assert [(a.id, a.url) for a in found] == [("a1", "https://a.com/1"), ("a2", "https://b.com/2")]
    assert found[0].publisher == "a.com"


def test_dates_from_tavily_in_either_format():
    assert iso_date("2026-10-19T08:00:00Z") == "2026-10-19"
    assert iso_date("Mon, 19 Oct 2026 08:00:00 GMT") == "2026-10-19"
    assert iso_date("yesterday") is None and iso_date(None) is None


def test_a_rerun_gives_the_day_new_topic_ids():
    db = FakeDB([profile()])
    run(db, FakeLLM(), FakeTavily(), DAY)
    first_ids = {r["id"] for r in db.tables["topics"]}
    run(db, FakeLLM(), FakeTavily(), DAY, force=True)
    assert len(db.tables["topics"]) == 5 and not first_ids & {r["id"] for r in db.tables["topics"]}


def test_saved_topics_get_covers_and_cover_failures_dont_undo_them():
    db = FakeDB([profile()])
    seen = []
    assert run(db, FakeLLM(), FakeTavily(), DAY, covers=lambda rows: seen.extend(r["id"] for r in rows)) == {"u1": 5}
    assert len(seen) == 5

    def broken(rows):
        raise RuntimeError("openai down")

    db2 = FakeDB([profile()])
    assert run(db2, FakeLLM(), FakeTavily(), DAY, covers=broken) == {"u1": 5}
    assert len(db2.tables["topics"]) == 5
