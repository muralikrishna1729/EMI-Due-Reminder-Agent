"""Checks that run BEFORE a tool executes: did the customer actually say it?

Pure functions (no database, no LLM), so they are easy to test.
Each check returns None when the request is fine, or an error message
that is sent back to the LLM as the tool result.
"""

import re 
from datetime import date, timedelta
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_MONTHS = "|".join(sorted(MONTHS, key=len, reverse=True))
_WEEKDAYS = "|".join(WEEKDAYS)

FOUR_DIGITS_RE = re.compile(r"(?<!\d)\d{4}(?!\d)")
ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
IN_DAYS_RE = re.compile(r"\bin\s+(\d{1,3})\s+days?\b")
DAY_MONTH_RE = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTHS})\b")
MONTH_DAY_RE = re.compile(rf"\b({_MONTHS})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b")
ORDINAL_RE = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\b")
WEEKDAY_RE = re.compile(rf"\b(next\s+)?({_WEEKDAYS})\b")
TOMORROW_RE = re.compile(r"\b(tomorrow|kal)\b")
TODAY_RE = re.compile(r"\b(today|tonight|aaj)\b")

# A clear "yes" to a date the agent proposed ...
AFFIRM_RE = re.compile(
    r"^\W*(yes|yeah|yep|yup|okay|ok|sure|fine|correct|right|agreed|done|haan|han|"
    r"theek hai|thik hai|that works|works for me|sounds good)\b"
)
# ... unless it comes with doubt or a question.
UNSURE_RE = re.compile(
    r"\b(not (completely |totally |really )?sure|might|maybe|perhaps|i think|i guess|"
    r"don'?t know|but|however|if|can i|could i|is it possible)\b|\?"
)

def customer_texts(messages: list[dict]) -> list[str]:
    """Only what the CUSTOMER said (role 'user'), never the assistant's words."""
    return [m.get("content") or "" for m in messages if m.get("role") == "user"]

def _add_day_month(found: set, today: date, day: int, month: int) -> None:
    for year in (today.year, today.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if candidate >= today:
            found.add(candidate)
            return

def _add_day_of_month(found: set, today: date, day: int) -> None:
    year, month = today.year, today.month
    for _ in range(2):  # this month, then next month
        try:
            candidate = date(year, month, day)
        except ValueError:
            candidate = None
        if candidate and candidate >= today:
            found.add(candidate)
            return
        month += 1
        if month == 13:
            month, year = 1, year + 1

def dates_in_text(texts: list[str], today: date) -> set[date]:
    """Every date these words can mean. Empty set = no date we understand."""
    found: set[date] = set()
    for raw in texts:
        t = raw.lower()

        for m in ISO_RE.finditer(t):
            try:
                found.add(date(int(m[1]), int(m[2]), int(m[3])))
            except ValueError:
                pass
        t = ISO_RE.sub(" ", t)

        for m in IN_DAYS_RE.finditer(t):
            found.add(today + timedelta(days=int(m[1])))
        t = IN_DAYS_RE.sub(" ", t)

        for m in DAY_MONTH_RE.finditer(t):
            _add_day_month(found, today, int(m[1]), MONTHS[m[2]])
        t = DAY_MONTH_RE.sub(" ", t)

        for m in MONTH_DAY_RE.finditer(t):
            _add_day_month(found, today, int(m[2]), MONTHS[m[1]])
        t = MONTH_DAY_RE.sub(" ", t)

        for m in ORDINAL_RE.finditer(t):
            _add_day_of_month(found, today, int(m[1]))
        t = ORDINAL_RE.sub(" ", t)

        if "day after tomorrow" in t or "parso" in t:
            found.add(today + timedelta(days=2))
        t = t.replace("day after tomorrow", " ")
        if TOMORROW_RE.search(t):
            found.add(today + timedelta(days=1))
        if TODAY_RE.search(t):
            found.add(today)

        for m in WEEKDAY_RE.finditer(t):
            weekday = WEEKDAYS.index(m[2])
            ahead = (weekday - today.weekday()) % 7
            if m[1]:  # "next friday": the coming one or the one after
                first = today + timedelta(days=ahead or 7)
                found.update({first, first + timedelta(days=7)})
            elif ahead == 0:  # "friday" said on a Friday: today or next week
                found.update({today, today + timedelta(days=7)})
            else:
                found.add(today + timedelta(days=ahead))
    return found

def _last_user_index(messages: list[dict]) -> int:
    return max((i for i, m in enumerate(messages) if m.get("role") == "user"), default=-1)

def dates_customer_accepted(messages: list[dict], today: date) -> set[date]:
    """Dates the agent proposed that the customer's LATEST message clearly accepted."""
    last_user = _last_user_index(messages)
    if last_user <= 0:
        return set()
    reply = (messages[last_user].get("content") or "").strip().lower()
    if not AFFIRM_RE.match(reply) or UNSURE_RE.search(reply):
        return set()
    for m in reversed(messages[:last_user]):
        if m.get("role") == "assistant":
            return dates_in_text([m.get("content") or ""], today)
    return set()

def dates_customer_agreed_to(messages: list[dict], today: date) -> set[date]:
    """A clear yes to a proposed date wins; otherwise the latest date the customer stated."""
    accepted = dates_customer_accepted(messages, today)
    if accepted:
        return accepted
    for text in reversed(customer_texts(messages)):
        found = dates_in_text([text], today)
        if found:
            return found
    return set()

def check_ptp_date(args: dict, messages: list[dict], today: date) -> str | None:
    agreed = dates_customer_agreed_to(messages, today)
    if not agreed:
        return (
            "The customer has not stated or clearly accepted a payment date. "
            "Ask on which day they will pay, or propose one specific day and wait "
            "for a clear yes. Do not choose a date yourself."
        )
    try:
        chosen = date.fromisoformat(str(args.get("ptp_date", "")))
    except ValueError:
        return None  # a bad format is reported by Pydantic, not here
    if chosen not in agreed:
        options = ", ".join(f"{d.isoformat()} ({d.strftime('%A')})" for d in sorted(agreed))
        return (
            "The date does not match what the customer said. "
            f"The customer's words match: {options}. "
            "Use one of these dates, or ask the customer again."
        )
    return None

def check_verification_code(args: dict, messages: list[dict]) -> str | None:
    code = str(args.get("verification_code", "")).strip()
    if not code:
        return None  # a missing code is reported by Pydantic, not here
    for text in customer_texts(messages):
        if code in FOUR_DIGITS_RE.findall(text):
            return None
    return (
        "The customer has not said that 4-digit code. Ask for the last four digits "
        "of their PAN or their birth year. Never guess, and never cut digits from a longer number."
    )

def ptp_logged_this_turn(messages: list[dict]) -> bool:
    """True if a promise was logged AFTER the customer's latest message."""
    last_user = _last_user_index(messages)
    return any(
        m.get("role") == "tool" and '"ptp_id"' in (m.get("content") or "")
        for m in messages[last_user + 1:]
    )


def check_tool_request(name: str, args: dict, messages: list[dict], today: date) -> str | None:
    if name == "verify_customer":
        return check_verification_code(args, messages)
    if name == "log_promise_to_pay":
        return check_ptp_date(args, messages, today)
    if (
        name == "mark_disposition"
        and args.get("status") == "PTP_AGREED"
        and ptp_logged_this_turn(messages)
    ):
        return (
            "Read the recorded date and amount back to the customer first, "
            "then wait for their reply before ending the call."
        )
    return None