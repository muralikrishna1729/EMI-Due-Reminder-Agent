"""Core utilities for per‑session audio state and pre‑roll recovery."""
from typing import List, Dict
from .history_buffer import HistoryBuffer

# Per‑session storage
_history_buffers: Dict[str, HistoryBuffer] = {}
_session_last_frame: Dict[str, int] = {}
_session_utterance_buffers: Dict[str, List[bytes]] = {}

def ingest_pcm(session_id: str, start_frame: int, pcm_bytes: bytes) -> None:
    """
    Validate and store a PCM frame range.

    Args:
        session_id: Identifier for the call session.
        start_frame: Absolute frame index where the PCM range starts (inclusive).
        pcm_bytes: Raw Int16 PCM bytes (2 bytes per sample).

    Raises:
        ValueError: If the range is invalid or out‑of‑order.
    """
    buffer = _history_buffers.get(session_id)
    if buffer is None:
        raise ValueError(f"HistoryBuffer not initialized for session {session_id}")

    # Validate frame indices
    if start_frame < 0 or start_frame >= buffer.total_samples:
        raise ValueError(f"start_frame {start_frame} out of range for session {session_id}")

    # Ensure we have enough frames in the buffer
    if start_frame + len(pcm_bytes) // 2 > buffer.total_samples:
        raise ValueError(f"PCM bytes span beyond buffer capacity for session {session_id}")

    # Validate frame order (no gaps, no duplicates, no out‑of‑order)
    expected_next = _session_last_frame.get(session_id, 0)
    if start_frame != expected_next:
        raise ValueError(
            f"Frame order violation: expected {expected_next}, got {start_frame} for session {session_id}"
        )

    # Store the frames
    buffer.add_frame(pcm_bytes)
    _session_last_frame[session_id] = start_frame + len(pcm_bytes) // 2

def get_history_buffer(session_id: str) -> HistoryBuffer:
    """Return the HistoryBuffer for the given session, creating it if necessary."""
    if session_id not in _history_buffers:
        _history_buffers[session_id] = HistoryBuffer(duration_ms=1300, sample_rate=24000)
    return _history_buffers[session_id]

def get_last_frame(session_id: str) -> int:
    """Return the last frame index that was successfully ingested for the session."""
    return _session_last_frame.get(session_id, 0)

def get_utterance_buffer(session_id: str) -> List[bytes]:
    """Return the active utterance buffer for the session (creates if missing)."""
    if session_id not in _session_utterance_buffers:
        _session_utterance_buffers[session_id] = []
    return _session_utterance_buffers[session_id]

def clear_utterance_buffer(session_id: str) -> None:
    """Clear the active utterance buffer for the session."""
    if session_id in _session_utterance_buffers:
        _session_utterance_buffers[session_id].clear()
    else:
        # Remove any stale reference to avoid memory leaks
        _session_utterance_buffers.pop(session_id, None)