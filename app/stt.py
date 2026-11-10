"""Speech-to-text via Groq Whisper. 
Returns plain text ('' when nothing was said)."""
import logging
from groq import Groq
from app import config

logger = logging.getLogger("emi_agent")
_client: Groq | None = None

def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=config.GROQ_API_KEY)
    return _client

def transcribe(
    audio: bytes,
    filename: str = "audio.webm",
    language: str | None = None,
    prompt: str | None = None,
) -> str:
    kwargs = dict(
        file=(filename, audio),
        model=config.STT_MODEL,
        response_format="verbose_json",   # includes per-segment no_speech_prob
        temperature=0.0,
    )
    if language:                          # None = let the model detect the language
        kwargs["language"] = language
    if prompt:
        kwargs["prompt"] = prompt
    result = _get_client().audio.transcriptions.create(**kwargs)

    data = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    segments = data.get("segments") or []

    if segments:
        kept = [s.get("text", "") for s in segments
                if s.get("no_speech_prob", 0.0) < config.STT_NO_SPEECH_MAX]
        return " ".join(t.strip() for t in kept).strip()
    return (data.get("text") or "").strip()
