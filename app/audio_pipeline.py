"""Audio pipeline utilities for per-session pre-roll recovery and utterance buffer management."""

from typing import List
from app.constants import START_FRAME_COUNT, BARGE_FRAME_COUNT
from app.core import get_history_buffer, get_utterance_buffer, clear_utterance_buffer

__all__ = [
    "START_FRAME_COUNT",
    "BARGE_FRAME_COUNT",
    "recover_pre_roll",
    "get_active_utterance_frames",
    "clear_active_utterance_buffer",
]


def recover_pre_roll(session_id: str, start_frame: int, end_frame: int) -> None:
    """
    Recover PCM frames from the per-session HistoryBuffer and append them to the
    active utterance buffer for the given session.

    Args:
        session_id: Identifier for the call session.
        start_frame: Absolute frame index where the pre-roll window starts (inclusive).
        end_frame: Absolute frame index where the pre-roll window ends (exclusive).
    """
    history_buf = get_history_buffer(session_id)
    utterance_buf = get_utterance_buffer(session_id)
    try:
        concatenated = history_buf.copy_range(start_frame, end_frame)
    except ValueError:
        return
    # Split into 2-byte frames and extend
    for i in range(0, len(concatenated), 2):
        frame = concatenated[i:i+2]
        utterance_buf.append(frame)


def get_active_utterance_frames(session_id: str) -> List[bytes]:
    """Return a copy of the current active utterance buffer for the given session."""
    return list(get_utterance_buffer(session_id))


def clear_active_utterance_buffer(session_id: str) -> None:
    """Clear the active utterance buffer for the given session (e.g., after call ends)."""
    clear_utterance_buffer(session_id)
