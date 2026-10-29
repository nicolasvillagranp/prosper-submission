"""The worker's briefing queue and morning schedule, with a fake Supabase."""

from datetime import date, datetime
from types import SimpleNamespace

from pipeline.briefing import Briefing
from worker import jobs


class FakeQuery:
    def __init__(self, rows):
        self.rows, self.filters, self.op, self.values = rows, [], "select", None

    def select(self, *_):
        return self

    def update(self, values):
        self.op, self.values = "update", values
        return self

    def eq(self, col, val):
        self.filters.append((col, val))
        return self

    def order(self, *_):
        return self

    def limit(self, _):
        return self

    def execute(self):
        match = [r for r in self.rows if all(r.get(c) == v for c, v in self.filters)]
        if self.op == "update":
            for r in match:
                r.update(self.values)
        return SimpleNamespace(data=match)


class FakeDB:
    def __init__(self, rows):
        self.rows = rows

    def table(self, name):
        assert name == "briefings"
        return FakeQuery(self.rows)


def request(topic, status="requested"):
    return {"topic_id": topic, "user_id": "u1", "status": status}


def test_a_request_is_made_and_marked_ready(monkeypatch):
    calls = []

    def fake_get(db, llm, http, topic_id, user_id):
        calls.append((topic_id, user_id))
        return Briefing(f"u1/briefings/{topic_id}.mp3", "Hola.", created=True)

    monkeypatch.setattr(jobs, "get_briefing", fake_get)
    db = FakeDB([request("t1"), request("t2", "ready")])
    assert jobs.process_briefings(db, None, None) == 1
    row = db.rows[0]
    assert row["status"] == "ready" and row["audio_path"] == "u1/briefings/t1.mp3" and row["script"] == "Hola."
    assert row["ready_at"]
    assert calls == [("t1", "u1")]


def test_a_failure_is_recorded_and_the_queue_goes_on(monkeypatch):
    def fake_get(db, llm, http, topic_id, user_id):
        if topic_id == "t1":
            raise RuntimeError("cartesia down")
        return Briefing("p", "s", created=True)

    monkeypatch.setattr(jobs, "get_briefing", fake_get)
    db = FakeDB([request("t1"), request("t2")])
    jobs.process_briefings(db, None, None)
    assert db.rows[0]["status"] == "failed" and "cartesia down" in db.rows[0]["error"]
    assert db.rows[1]["status"] == "ready"


def test_stuck_requests_go_back_in_the_queue():
    db = FakeDB([request("t1", "working"), request("t2", "ready")])
    jobs.reset_stuck(db)
    assert [r["status"] for r in db.rows] == ["requested", "ready"]


def test_morning_job_runs_once_a_day_from_the_hour():
    assert not jobs.morning_due(datetime(2026, 10, 28, 5, 59), None, 6)
    assert jobs.morning_due(datetime(2026, 10, 28, 6, 0), None, 6)
    assert jobs.morning_due(datetime(2026, 10, 28, 14, 0), date(2026, 10, 27), 6)  # started late: catch up
    assert not jobs.morning_due(datetime(2026, 10, 28, 14, 0), date(2026, 10, 28), 6)


def test_new_users_are_those_with_a_profile_and_no_topics_yet():
    class Q:
        def __init__(self, rows):
            self.rows, self.f = rows, {}

        def select(self, *_):
            return self

        def eq(self, c, v):
            self.f[c] = v
            return self

        def limit(self, _):
            return self

        def execute(self):
            return SimpleNamespace(data=[r for r in self.rows if all(r.get(c) == v for c, v in self.f.items())])

    tables = {"profiles": [{"user_id": "old"}, {"user_id": "new"}], "topics": [{"id": "t", "user_id": "old"}]}
    db = SimpleNamespace(table=lambda name: Q(tables[name]))
    assert jobs.users_without_topics(db) == ["new"]
