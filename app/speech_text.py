"""Clean up a speech transcript before it reaches the agent (voice only; typed text is untouched)."""
import re

_WORD = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
         "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"}

_TOKEN = r"(?:\d|zero|one|two|three|four|five|six|seven|eight|nine)"

# four or more single digits in a row, separated by spaces, commas, dots or hyphens

_RUN = re.compile(rf"(?<![\w])({_TOKEN}(?:[\s,.\-]+{_TOKEN}){{3,}})(?![\w])", re.IGNORECASE)


def _collapse(match: re.Match) -> str:
    parts = re.split(r"[\s,.\-]+", match.group(1).lower())
    return "".join(_WORD.get(p, p) for p in parts)


def normalize_transcript(text: str) -> str:
    return _RUN.sub(_collapse, text or "")