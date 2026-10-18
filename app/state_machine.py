from enum import Enum


class State(str, Enum):
    GREETING = "GREETING"
    VERIFYING = "VERIFYING"
    NEGOTIATING = "NEGOTIATING"  # only reachable through successful verification
    ENDED = "ENDED"


class Tool(str, Enum):
    VERIFY_CUSTOMER = "verify_customer"
    LOG_PTP = "log_promise_to_pay"
    SEND_LINK = "send_payment_link"
    ESCALATE = "escalate_to_agent"
    MARK_DISPOSITION = "mark_disposition"


# The LLM is only shown (and only allowed to call) these tools in each state.
ALLOWED_TOOLS: dict[State, set[Tool]] = {
    State.GREETING: {Tool.VERIFY_CUSTOMER, Tool.MARK_DISPOSITION},
    State.VERIFYING: {Tool.VERIFY_CUSTOMER, Tool.MARK_DISPOSITION},
    State.NEGOTIATING: {
        Tool.LOG_PTP,
        Tool.SEND_LINK,
        Tool.ESCALATE,
        Tool.MARK_DISPOSITION,
    },
    State.ENDED: set(),
}

TRANSITIONS: dict[tuple[State, str], State] = {
    (State.GREETING, "turn_done"): State.VERIFYING,
    (State.GREETING, "verified"): State.NEGOTIATING,
    (State.VERIFYING, "verified"): State.NEGOTIATING,
    (State.GREETING, "ended"): State.ENDED,
    (State.VERIFYING, "ended"): State.ENDED,
    (State.NEGOTIATING, "ended"): State.ENDED,
}


def next_state(state: State, event: str) -> State:
    """Unknown (state, event) pairs leave the state unchanged."""
    return TRANSITIONS.get((state, event), state)