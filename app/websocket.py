"""WebSocket endpoint for PCM transport in the EMI audio pre‑roll feature.

Endpoints:
- GET /ws/pcm/{session_id} – establish a WebSocket connection for a given session.
  The client must authenticate via a token passed as a query parameter (same token used by other API routes).

The endpoint:
1. Validates that the session exists.
2. Checks that the connecting client is authorized by verifying a token passed in the URL query string.
3. Receives binary PCM frames from the client (4‑byte little‑endian frame index + Int16 mono PCM).
4. Parses the frame index and PCM data.
5. Calls `ingest_pcm` from `app.core` to store the frames in the per‑session HistoryBuffer.
6. Sends an acknowledgment if needed, then continues listening.
7. On disconnect, cleans up the session’s utterance buffer (optional).
"""

import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from app import config
from app.db import get_db
from app.models import CallSession
from app.core import ingest_pcm, get_history_buffer, get_last_frame, get_utterance_buffer, clear_utterance_buffer

router = APIRouter()
websocket_router = router

@router.websocket("/ws/pcm/{session_id}")
async def websocket_pcm(
    session_id: str,
    websocket: WebSocket,
    token: str | None = None,
    db: Session = Depends(get_db),
):
    # Extract token from query parameters
    if not token or token != config.API_TOKEN:
        await websocket.close(code=1008, reason="Invalid token")
        return

    # Verify session exists
    session = db.get(CallSession, session_id)
    if not session:
        await websocket.close(code=1008, reason="Session not found")
        return

    # Accept the WebSocket connection
    await websocket.accept()
    get_history_buffer(session_id)

    try:
        while True:
            # Receive binary PCM frame
            data = await websocket.receive_bytes()
            if not data:
                continue

            # Parse the 4‑byte little‑endian frame index
            if len(data) < 4:
                await websocket.send_json({"error": "Frame too short"})
                continue

            frame_index = int.from_bytes(data[:4], byteorder='little')
            pcm_bytes = data[4:]

            # Validate PCM length (must be even number of bytes)
            if len(pcm_bytes) % 2 != 0:
                await websocket.send_json({"error": "Invalid PCM length"})
                continue

            # Ingest PCM into per‑session HistoryBuffer
            try:
                ingest_pcm(session_id, frame_index, pcm_bytes)
            except ValueError as exc:
                # Send error back to client and close connection
                err_msg = "Frame order violation" if "Frame order violation" in str(exc) else str(exc)
                await websocket.send_json({"error": err_msg})
                await websocket.close(code=1011, reason="Invalid PCM data")
                return

            # Optionally send acknowledgment (e.g., echo frame index)
            await websocket.send_json({"frame_index": frame_index, "status": "ok"})

            # Update last frame for potential future validation
            # (already handled inside ingest_pcm)

    except WebSocketDisconnect:
        # Clean up utterance buffer on disconnect
        clear_utterance_buffer(session_id)
        logging.info(f"WebSocket disconnected for session {session_id}")
    except Exception as exc:
        logging.error(f"WebSocket error for session {session_id}: {exc}")
        try:
            await websocket.close(code=1011, reason=str(exc))
        except Exception:
            pass