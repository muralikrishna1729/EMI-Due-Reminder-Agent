from app.state_machine import ALLOWED_TOOLS, State, Tool, next_state
from app.tools import HANDLERS, TOOL_SPECS


def test_negotiating_only_reachable_via_verified():
    for state in (State.GREETING, State.VERIFYING):
        for event in ("turn_done", "ended", "negotiate", "skip", "disclose"):
            assert next_state(state, event) != State.NEGOTIATING


def test_verified_unlocks_negotiating():
    assert next_state(State.VERIFYING, "verified") == State.NEGOTIATING


def test_ended_is_terminal():
    for event in ("verified", "turn_done", "ended"):
        assert next_state(State.ENDED, event) == State.ENDED


def test_ended_exposes_no_tools():
    assert ALLOWED_TOOLS[State.ENDED] == set()


def test_negotiating_tools_are_exactly_three():
    assert ALLOWED_TOOLS[State.NEGOTIATING] == {
        Tool.LOG_PTP,
        Tool.ESCALATE,
        Tool.MARK_DISPOSITION,
    }


def test_payment_link_tool_does_not_exist():
    assert "send_payment_link" not in {t.value for t in Tool}


def test_every_state_has_an_allowed_tools_entry():
    for state in State:
        assert state in ALLOWED_TOOLS


def test_every_tool_has_a_handler_and_a_spec():
    # catches "added a tool but forgot one of the three tables"
    for tool in Tool:
        assert tool in HANDLERS
        assert tool in TOOL_SPECS