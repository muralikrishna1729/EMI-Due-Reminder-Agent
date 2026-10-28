import pytest

from app.engine import handle_turn, start_call
from app.graph import build_graph
from app.models import CallEvent
from tests.helpers import ScriptedLLM, text, tool

SCENARIOS = {
    "dnc": (lambda: ScriptedLLM(), "Please stop calling me"),
    "silence": (lambda: ScriptedLLM(), ""),
    "leak": (lambda: ScriptedLLM(text("Your overdue EMI is ₹8,499.")), "Tell me the amount"),
    "verify": (
        lambda: ScriptedLLM(
            tool("verify_customer", {"verification_code": "1234"}),
            text("Thank you. Your overdue amount is ₹8,499."),
        ),
        "1234",
    ),
}


def event_types(db, call):
    rows = db.query(CallEvent).filter_by(session_id=call.id).order_by(CallEvent.id).all()
    return [e.type for e in rows]


@pytest.mark.parametrize("name", SCENARIOS)
def test_graph_matches_handle_turn(db, customer, name):
    make_llm, user_text = SCENARIOS[name]
    s1, _ = start_call(db, customer)
    s2, _ = start_call(db, customer)

    r1 = handle_turn(db, s1, user_text, llm=make_llm())
    out = build_graph(db, s2, llm=make_llm()).invoke({"user_text": user_text})

    assert out["reply"] == r1.reply
    assert s2.state == s1.state
    assert s2.verified == s1.verified
    assert s2.disposition == s1.disposition
    assert event_types(db, s2) == event_types(db, s1)