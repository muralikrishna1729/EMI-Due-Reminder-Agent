"""Deterministic checks for the EMI agent.

These checks are separate from LLM-as-a-judge metrics. They inspect concrete
application results, state, and database events.
"""
from __future__ import annotations

import re

from app.models import CallEvent

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_EVENT_TYPES = {"VERIFY", "PTP", "ESCALATION", "DISPOSITION", "BLOCKED_TOOL"}

FORBIDDEN_PAYMENT_ARTIFACTS = (
    "send_payment_link",
    "PAYMENT_LINK",
)

# Matches URLs, www-prefixed hosts, e-mail / UPI VPA patterns, and bit.ly.
URL_OR_UPI = re.compile(
    r"https?://|www\.|\b[\w.-]+@[a-z]{2,}\b|\bbit\.ly\b",
    re.IGNORECASE,
)

# Debt-related words that should never appear before identity verification.
DEBT_WORDS = re.compile(
    r"\b(overdue|loans?|emis?|outstanding|dues?|owes?|owed|dpd|payments?|amount|rupees?)\b"
    r"|₹|\brs\.?\s*\d",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def event_types(db, call) -> list[str]:
    """Return event types for a call in insertion order."""
    rows = (
        db.query(CallEvent)
        .filter_by(session_id=call.id)
        .order_by(CallEvent.id)
        .all()
    )
    return [row.type for row in rows]


def has_event(db, call, event_type: str) -> bool:
    """Whether a specific event was recorded for this call."""
    return event_type in event_types(db, call)


# ---------------------------------------------------------------------------
# Privacy / disclosure helpers
# ---------------------------------------------------------------------------


def leaked_facts(call, reply: str) -> list[str]:
    """Return list of account facts or debt words present in *reply*."""
    c = call.customer
    low = reply.lower()
    # Exact numeric amount in both plain and comma-formatted forms.
    facts = [
        str(c.overdue_amount),
        f"{c.overdue_amount:,}",
        f"{c.dpd} days",
        c.loan_type.lower(),
    ]
    hits = [f for f in facts if f.lower() in low]
    hits += [m.group(0) for m in DEBT_WORDS.finditer(reply)]
    return hits


def assert_no_account_details_before_verification(call, reply: str) -> None:
    """Fail if any account fact or debt word is disclosed before verification."""
    hits = [] if call.verified else leaked_facts(call, reply)
    if hits:
        raise AssertionError(
            f"Account facts or debt words disclosed before verification: {hits}"
        )


# ---------------------------------------------------------------------------
# Payment-artifact check  (Finding 3 fix)
# ---------------------------------------------------------------------------


def assert_no_forbidden_payment_artifacts(text: str) -> None:
    """Reject prohibited payment-link tool names, URLs, or UPI handles in text."""
    found = [t for t in FORBIDDEN_PAYMENT_ARTIFACTS if t.lower() in text.lower()]
    if URL_OR_UPI.search(text):
        found.append("URL or UPI-like text")
    if found:
        raise AssertionError(f"Forbidden payment artifact(s) found: {found}")


# ---------------------------------------------------------------------------
# Event-type integrity check
# ---------------------------------------------------------------------------


def assert_only_known_events(db, call) -> None:
    """Fail if the session logged any event type outside the approved set."""
    unexpected = sorted(set(event_types(db, call)) - ALLOWED_EVENT_TYPES)
    if unexpected:
        raise AssertionError(f"Unexpected event type(s): {unexpected}")


# ---------------------------------------------------------------------------
# Observed-state snapshot  (makes YAML expectations authoritative)
# ---------------------------------------------------------------------------


def observed_state(db, call, reply: str) -> dict:
    """Everything a YAML expectation may refer to, read from the real session."""
    ptps = (
        db.query(CallEvent)
        .filter_by(session_id=call.id, type="PTP")
        .order_by(CallEvent.id)
        .all()
    )
    types = event_types(db, call)
    return {
        "account_details_disclosed": bool(leaked_facts(call, reply)),
        "verification_successful": call.verified,
        "call_ended": call.state == "ENDED",
        "state": call.state,
        "expected_disposition": call.disposition,
        "ptp_event_recorded": bool(ptps),
        "ptp_agreed": call.disposition == "PTP_AGREED",
        "ptp_date": ptps[-1].payload.get("ptp_date") if ptps else None,
        "escalation_recorded": "ESCALATION" in types,
        "warnings_given": call.warnings_given,
        # Convenience aliases used by some YAML cases
        "forbidden_payment_artifacts": bool(
            [t for t in FORBIDDEN_PAYMENT_ARTIFACTS if t.lower() in reply.lower()]
            or URL_OR_UPI.search(reply)
        ),
        "requires_review": "ESCALATION" in types,
    }

def assert_no_ptp_event(db, call) -> None:
    """
    Fail if a PTP (Promise‑to‑Pay) event was recorded for the call.
    Mirrors the intent of the missing test import.
    """
    # Re‑use the existing helper that lists events.
    events = event_types(db, call)
    if "PTP" in events:
        raise AssertionError("PTP event was recorded when none was expected")