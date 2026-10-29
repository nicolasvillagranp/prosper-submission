"""Saving an interview: transcript, stereo ogg -> mono mp3, the session row and the upload."""

import io
from types import SimpleNamespace

import av
import numpy as np

from agent.episodes import ogg_to_mp3, save_episode, transcript_from


def stereo_ogg(path, seconds=1.0, rate=48000):
    """A stereo opus ogg like LiveKit's recorder: a tone on the left (host), silence on the right."""
    with av.open(str(path), mode="w", format="ogg") as out:
        stream = out.add_stream("libopus", rate=rate, layout="stereo")
        t = np.arange(int(rate * seconds)) / rate
        left = (np.sin(2 * np.pi * 440 * t) * 8000).astype(np.int16)
        pcm = np.stack([left, np.zeros_like(left)])  # planar: [channels, samples]
        for start in range(0, pcm.shape[1], 960):
            frame = av.AudioFrame.from_ndarray(np.ascontiguousarray(pcm[:, start:start + 960]), format="s16p", layout="stereo")
            frame.sample_rate = rate
            for packet in stream.encode(frame):
                out.mux(packet)
        for packet in stream.encode(None):
            out.mux(packet)


def test_transcript_keeps_host_and_expert_lines_only():
    items = [
        SimpleNamespace(role="system", text_content="instructions"),
        SimpleNamespace(role="assistant", text_content="Hola, encantada."),
        SimpleNamespace(role="user", text_content="  ¿Qué es un agente?  "),
        SimpleNamespace(role="user", text_content=""),
        SimpleNamespace(type="function_call"),
    ]
    assert transcript_from(items) == [
        {"speaker": "expert", "text": "Hola, encantada."},
        {"speaker": "host", "text": "¿Qué es un agente?"},
    ]


def test_the_recording_becomes_a_mono_mp3(tmp_path):
    ogg = tmp_path / "audio.ogg"
    stereo_ogg(ogg)
    mp3 = ogg_to_mp3(ogg)
    with av.open(io.BytesIO(mp3)) as f:
        stream = f.streams.audio[0]
        assert f.format.name == "mp3"
        assert stream.layout.name == "mono"
        assert 0.8 < float(f.duration / av.time_base) < 1.4


class FakeDB:
    def __init__(self, sessions):
        self.sessions, self.files = sessions, {}
        store = SimpleNamespace(upload=lambda path, data, opts: self.files.__setitem__(path, data))
        self.storage = SimpleNamespace(from_=lambda bucket: store)

    def table(self, name):
        assert name == "sessions"
        db = self

        class Q:
            filters, values = {}, None

            def select(self, *_):
                return self

            def update(self, values):
                self.values = values
                return self

            def eq(self, c, v):
                self.filters = {**self.filters, c: v}
                return self

            def limit(self, _):
                return self

            def execute(self):
                rows = [r for r in db.sessions if all(r.get(c) == v for c, v in self.filters.items())]
                if self.values:
                    for r in rows:
                        r.update(self.values)
                return SimpleNamespace(data=rows)

        return Q()


LINES = [{"speaker": "host", "text": "Hola"}]


def test_a_recorded_session_saves_transcript_and_mp3(tmp_path):
    ogg = tmp_path / "audio.ogg"
    stereo_ogg(ogg)
    db = FakeDB([{"id": "s1", "user_id": "u1"}])
    assert save_episode(db, "s1", LINES, ogg) == "u1/sessions/s1.mp3"
    row = db.sessions[0]
    assert row["transcript"] == LINES and row["recording_path"] == "u1/sessions/s1.mp3" and row["ended_at"]
    assert db.files["u1/sessions/s1.mp3"][:3] in (b"ID3", b"\xff\xfb", b"\xff\xf3")


def test_an_unrecorded_session_saves_the_transcript_only(tmp_path):
    db = FakeDB([{"id": "s1", "user_id": "u1"}])
    assert save_episode(db, "s1", LINES, None) is None
    assert db.sessions[0]["transcript"] == LINES and db.sessions[0]["recording_path"] is None
    assert db.files == {}


def test_a_broken_recording_still_saves_the_transcript(tmp_path):
    bad = tmp_path / "audio.ogg"
    bad.write_bytes(b"not audio")
    db = FakeDB([{"id": "s1", "user_id": "u1"}])
    assert save_episode(db, "s1", LINES, bad) is None
    assert db.sessions[0]["transcript"] == LINES


def test_unknown_session_saves_nothing():
    db = FakeDB([])
    assert save_episode(db, "nope", LINES, None) is None
