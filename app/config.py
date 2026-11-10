import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./maya.db")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "dev-key")
STT_MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo")
STT_LANGUAGE = os.getenv("GROQ_STT_LANGUAGE", "en")
STT_NO_SPEECH_MAX = 0.6   # drop segments the model thinks are not speech

# A customer may place the conversation on hold once while finding verification details.
HOLD_SECONDS = max(1, int(os.getenv("HOLD_SECONDS", "120")))
MAX_HOLDS = max(0, int(os.getenv("MAX_HOLDS", "1")))

MAX_VERIFY_ATTEMPTS = 2
MAX_WAIVER_PERCENT = 10
MAX_PTP_DAYS_AHEAD = 30
MAX_TOOL_ROUNDS = 4
