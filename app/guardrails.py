import re

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

# Starter list only. Extend it, and consider a classifier later.
ABUSE_TERMS = ("idiot", "stupid", "shut up", "fool", "rascal", "Ruining your life")

SAFE_VERIFY_PROMPT = (
    "For your security I need to verify your identity first. "
    "Could you please share the last four digits of your PAN or your year of birth?"
)

SAFE_GOODBYE = "Sorry for the interruption. Have a good day. Goodbye."

def is_abusive(text: str) -> bool:
    t = text.lower()
    return any(term in t for term in ABUSE_TERMS)

def leaks_debt_info(text:str)->bool:
    return bool(FORBIDDEN_PRE_AUTH.search(text))

# Backwards-compatible alias (older code used the singular form).
leak_debt_info = leaks_debt_info

def sanitize_pre_auth_reply(text: str, call_ended: bool) -> str:
    """Sanitize the reply before authentication.

    If the reply contains any forbidden pre‑authentication debt information, replace it with a safe
    verification prompt (when the call is ongoing) or a goodbye message (when the call has ended).
    """
    if not leak_debt_info(text):
        return text
    return SAFE_GOODBYE if call_ended else SAFE_VERIFY_PROMPT

