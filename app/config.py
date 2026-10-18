import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./maya.db")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "dev-key")

MAX_VERIFY_ATTEMPTS = 2
MAX_WAIVER_PERCENT = 10
MAX_PTP_DAYS_AHEAD = 30
MAX_TOOL_ROUNDS = 4