from datetime import date
import re

from app.tool_checks import MONTHS, WEEKDAYS

# Words that must never appear in a reply before the customer is verified.
FORBIDDEN_PRE_AUTH = re.compile(
    r"\b(overdue|loans?|emis?|outstanding|dues?|owes?|owed|dpd|payments?|amount|rupees?)\b"
    r"|₹|\brs\.?\s*\d|\d{4,}",
    re.IGNORECASE,
)

DNC_RE = re.compile(
    r"\b(stop calling|do not call|don[’']?t call|never call|remove my number|call mat kar\w*)\b",
    re.IGNORECASE,
)

ABUSE_TERMS = (
    "idiot", "stupid", "shut up", "fool", "rascal", "ruining your life",
    "fuck", "shit", "bastard", "bitch", "asshole", "moron", "useless", "get lost"
)
ABUSE_RE = re.compile(r"\b(?:" + "|".join(re.escape(t) for t in ABUSE_TERMS) + ")", re.IGNORECASE)

THIRD_PARTY_RE = re.compile(
    r"(?:her|his|their)\s+"
    r"(?:father|mother|dad|mom|mum|brother|sister|cousin|husband|wife|son|daughter|"
    r"friend|uncle|aunt|relative|neighbou?r)\b"
    r"|\b(?:she|he)(?:['’]s|\s+is|\s+was)\s+"
    r"(?:not\s+(?:here|available|home|at home|around)|busy|out|outside|eating|sleeping|unavailable|away)\b"
    r"|\bwrong number\b",
    re.IGNORECASE,
)

# Requests to pause briefly while the customer finds verification details.
# Kept separate from date/payment parsing: "pay in 3 days" is not a hold.
_HOLD_PATTERNS = [
    r"\b(?:hold on|hang on|hold the line|one moment|just a (?:moment|minute|second)|wait a (?:moment|minute|second))\b",
    r"\b(?:wait|give me|need|take)\b[^.?!]{0,25}\b(?:\d+|one|two|three|four|five|few|couple of|some|a)\b[^.?!]{0,12}\b(?:minutes?|mins?|moments?|seconds?)\b",
    r"\blet me (?:check|find|look|see|search|think)\b",
    r"\b(?:ek minute|thoda ruko|ruko)\b",
]
HOLD_RE = re.compile("|".join(_HOLD_PATTERNS), re.IGNORECASE)

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s*(?=[A-Z₹])")
STAGE_DIRECTION_RE = re.compile(r"\s*[\(\[][^)\]]*[\)\]]")
ELLIPSIS_RE = re.compile(r"(?:\s*(?:\.{2,}|…))+\s*")

_MON = "|".join(sorted(MONTHS, key=len, reverse=True))
WEEKDAY_DATE_RE = re.compile(
    rf"\b(?P<wd>{'|'.join(WEEKDAYS)}),?\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?(?P<mon>{_MON})\b",
    re.IGNORECASE,
)


def _ellipsis(m: re.Match) -> str:
    before = m.string[:m.start()].rstrip()
    return " " if before.endswith((".", "?", "!")) else ". "


def clean_reply(text: str) -> str:
    """Spoken replies never contain bracketed notes or runs of dots."""
    text = STAGE_DIRECTION_RE.sub("", text)
    text = ELLIPSIS_RE.sub(_ellipsis, text)
    return re.sub(r"\s{2,}", " ", text).strip()


def fix_weekdays(text: str, today: date) -> str:
    """Make 'Friday, 15 November' agree with the real calendar (the LLM often uses the wrong year)."""
    def repl(m):
        day, month = int(m["day"]), MONTHS[m["mon"].lower()]
        for year in (today.year, today.year + 1):
            try:
                d = date(year, month, day)
            except ValueError:
                continue
            if d >= today:
                return d.strftime("%A") + m.group(0)[len(m["wd"]):]
        return m.group(0)
    return WEEKDAY_DATE_RE.sub(repl, text)


SAFE_VERIFY_PROMPT = (
    "For your security I need to verify your identity first. "
    "Could you please share the last four digits of your PAN or your year of birth?"
)

SAFE_GOODBYE = "Sorry for the interruption. Have a good day. Goodbye."


def is_abusive(text: str) -> bool:
    return bool(ABUSE_RE.search(text))


def leaks_debt_info(text: str) -> bool:
    return bool(FORBIDDEN_PRE_AUTH.search(text))


# Backwards-compatible alias (older code used the singular form).
leak_debt_info = leaks_debt_info


def sanitize_pre_auth_reply(text: str, call_ended: bool) -> str:
    """Replace replies containing forbidden pre-authentication debt information."""
    if not leak_debt_info(text):
        return text
    return SAFE_GOODBYE if call_ended else SAFE_VERIFY_PROMPT


def tidy_reply(text: str, max_sentences: int = 3, max_chars: int = 350) -> str:
    """Drop repeated sentences and cap the length: replies are spoken on a phone call."""
    parts = [p.strip() for p in SENTENCE_SPLIT_RE.split(text.strip()) if p.strip()]
    seen: set[str] = set()
    kept: list[str] = []
    for part in parts:
        key = re.sub(r"[^a-z0-9₹]+", " ", part.lower()).strip()
        if key in seen:
            continue
        seen.add(key)
        kept.append(part)
        if len(kept) == max_sentences:
            break
    out = " ".join(kept)
    if len(out) > max_chars:
        out = out[:max_chars].rsplit(" ", 1)[0]
    return out
