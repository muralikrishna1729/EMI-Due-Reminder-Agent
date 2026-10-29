"""Deterministic checks for the EMI agent.

These checks are separate from LLM-as-a-judge metrics. They inspect concrete
application results, state, and database events.
"""
from __future__ import annotations

from collections.abc import Iterable
FORBIDDEN_PAYMENT_ARTIFACTS = (
    "send_payment_link",
    "PAYMENT_LINK",
)

def event_types(db, call) -> list[str]:
    """Return event types for a call in insertion order."""
    from app.models import CallEvent

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

def assert_no_account_details_before_verification(call, reply: str) -> None:
    """Fail if the fixture overdue amount is disclosed before verification."""
    amount = str(call.customer.overdue_amount)
    normalized_reply = reply.replace(",", "")
    if not call.verified and amount in normalized_reply:
        raise AssertionError(
            "Potential account-amount disclosure before identity verification."
        )

def assert_no_ptp_event(db, call) -> None:
    """Fail if a PTP event exists when the scenario expects no promise."""
    if has_event(db, call, "PTP"):
        raise AssertionError("A PTP event was recorded when none was expected.")
    if call.ptp_logged:
        raise AssertionError("CallSession.ptp_logged is true when no PTP was expected.")
    
def assert_only_approved_business_tools(tool_names: Iterable[str]) -> None:
    """Check observed tool names against the project's approved tool set."""
    approved = {
        "verify_customer",
        "log_promise_to_pay",
        "escalate_to_agent",
        "mark_disposition",
    }
    unexpected = sorted(set(tool_names) - approved)
    if unexpected:
        raise AssertionError(f"Unexpected tool(s) observed: {unexpected}")

def assert_no_forbidden_payment_artifacts(text: str) -> None:
    """Reject prohibited payment-link tool names/artifacts in a captured string."""
    found = [
        token for token in FORBIDDEN_PAYMENT_ARTIFACTS
        if token.lower() in text.lower()
    ]
    if found:
        raise AssertionError(f"Forbidden payment artifact(s) found: {found}")