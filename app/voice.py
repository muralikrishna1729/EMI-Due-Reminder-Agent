import logging
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import config
from app.db import get_db
from app.engine import handle_turn
from app.models import CallSession
from app.speech_text import normalize_transcript
from app.stt import transcribe

logger = logging.getLogger("emi_agent")
router = APIRouter()
MAX_AUDIO_BYTES = 5 * 1024 * 1024


def _mark_interrupted_reply(session: CallSession, interrupt_at: int) -> None:
    """Keep only the portion of the latest assistant reply the customer could have heard."""
    if interrupt_at <= 0:
        return
    history = list(session.history or [])
    if not history or history[-1].get("role") != "assistant":
        return

    last = dict(history[-1])
    content = str(last.get("content") or "")
    if not content:
        return

    cut_at = min(max(int(interrupt_at), 0), len(content))
    heard = content[:cut_at].rsplit(" ", 1)[0].strip()
    if not heard:
        heard = content[:cut_at].strip()
    last["content"] = f"{heard} [interrupted by customer]".strip()
    session.history = history[:-1] + [last]


@router.post("/calls/{session_id}/voice")
def voice_turn(
    session_id: str,
    audio: UploadFile = File(...),
    interrupt_at: int = Form(0),
    db: Session = Depends(get_db),
):
    # STT and LLM calls block, so FastAPI runs this route in its thread pool.
    session = db.get(CallSession, session_id)
    if not session:
        raise HTTPException(404, "Unknown session")
    data = audio.file.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Audio too large")

    t0 = time.perf_counter()
    try:
        heard = transcribe(
            data,
            audio.filename or "audio.webm",
            language=config.STT_LANGUAGE,
            prompt=f"{session.customer.full_name}. EMI, PAN, overdue, penalty, interest, birth year.",
        )
    except Exception as exc:  # provider or network failure
        logger.warning("speech-to-text failed: %r", exc)
        raise HTTPException(502, "Speech-to-text failed")
    t1 = time.perf_counter()

    # Barge-in must not leave unheard words (especially a proposed payment date)
    # in the transcript later used by the PTP agreement checks.
    _mark_interrupted_reply(session, interrupt_at)
    if interrupt_at > 0:
        db.commit()

    result = handle_turn(db, session, normalize_transcript(heard))
    t2 = time.perf_counter()
    return {
        "heard": heard,
        "reply": result.reply,
        "state": result.state,
        "ended": result.ended,
        "disposition": result.disposition,
        "hold_seconds": result.hold_seconds,
        "timings_ms": {"stt": round((t1 - t0) * 1000), "agent": round((t2 - t1) * 1000)},
    }
