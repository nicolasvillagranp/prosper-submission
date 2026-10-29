"""Saving an interview when it ends: the transcript always, the audio if the host ticked "record".

LiveKit's own recorder (AgentSession.start(record={"audio": True})) writes an ogg with the host
on one channel and the expert on the other. We mix it down to a mono mp3, the file people
download from My episodes, and store it next to the user's other files:

    recordings/<user_id>/sessions/<session_id>.mp3
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from pathlib import Path

import av

logger = logging.getLogger("expert")

BUCKET = "recordings"


def transcript_from(items) -> list[dict]:
    """The conversation as [{"speaker": "host" | "expert", "text": ...}], from the chat history."""
    lines = []
    for item in items:
        role = getattr(item, "role", None)
        text = (getattr(item, "text_content", None) or "").strip()
        if role in ("user", "assistant") and text:
            lines.append({"speaker": "host" if role == "user" else "expert", "text": text})
    return lines


def ogg_to_mp3(path: Path) -> bytes:
    """The recorder's stereo ogg (host left, expert right) as a mono 128 kbps mp3."""
    out = io.BytesIO()
    with av.open(str(path)) as src, av.open(out, mode="w", format="mp3") as dst:
        stream = dst.add_stream("libmp3lame", rate=44100, layout="mono")
        stream.bit_rate = 128_000
        resampler = av.AudioResampler(format="s16p", layout="mono", rate=44100)
        for frame in src.decode(audio=0):
            for resampled in resampler.resample(frame):
                for packet in stream.encode(resampled):
                    dst.mux(packet)
        for resampled in resampler.resample(None):
            for packet in stream.encode(resampled):
                dst.mux(packet)
        for packet in stream.encode(None):
            dst.mux(packet)
    return out.getvalue()


def save_episode(db, session_id: str, transcript: list[dict], recording: Path | None) -> str | None:
    """Writes the session row (end time, transcript) and uploads the mp3. Returns its path, if any."""
    row = db.table("sessions").select("user_id").eq("id", session_id).limit(1).execute().data
    if not row:
        logger.warning("session %s not found: nothing saved", session_id)
        return None
    path = None
    if recording and recording.exists() and recording.stat().st_size > 0:
        try:
            path = f"{row[0]['user_id']}/sessions/{session_id}.mp3"
            db.storage.from_(BUCKET).upload(path, ogg_to_mp3(recording), {"content-type": "audio/mpeg", "upsert": "true"})
        except Exception:
            logger.exception("recording of session %s could not be saved", session_id)
            path = None
    db.table("sessions").update({
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "transcript": transcript,
        "recording_path": path,
    }).eq("id", session_id).execute()
    logger.info("session %s saved: %d lines, recording %s", session_id, len(transcript), path or "none")
    return path
