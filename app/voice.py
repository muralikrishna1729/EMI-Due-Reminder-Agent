import logging
import time

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
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


@router.post("/calls/{session_id}/voice")
def voice_turn(session_id: str, audio: UploadFile = File(...), db: Session = Depends(get_db)):
    # plain `def` on purpose: the STT and LLM calls block, and FastAPI runs `def` routes in a thread pool
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
    except Exception as exc:                       # provider or network failure
        logger.warning("speech-to-text failed: %r", exc)
        raise HTTPException(502, "Speech-to-text failed")
    t1 = time.perf_counter()

    result = handle_turn(db, session, normalize_transcript(heard))   # "" counts as silence
    t2 = time.perf_counter()
    return {
        "heard": heard,
        "reply": result.reply,
        "state": result.state,
        "ended": result.ended,
        "disposition": result.disposition,
        "timings_ms": {"stt": round((t1 - t0) * 1000), "agent": round((t2 - t1) * 1000)},
    }
