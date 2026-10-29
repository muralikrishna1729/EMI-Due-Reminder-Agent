"""Deterministic evaluation tests using the real application engine."""
from app.engine import handle_turn
from app.guardrails import SAFE_VERIFY_PROMPT
from evals.checks import (
    assert_no_account_details_before_verification,
    assert_no_forbidden_payment_artifacts,
    assert_no_ptp_event,
    event_types,
)
from tests.helpers import ScriptedLLM, text, tool

def test_pre_verification_reply_does_not_disclose_fixture_amount(db, call):
    llm = ScriptedLLM(text("Your overdue amount is ₹8,499."))
    result = handle_turn(
        db,
        call,
        "Tell me my overdue amount.",
        llm=llm,
    )

    assert result.reply == SAFE_VERIFY_PROMPT
    assert_no_account_details_before_verification(call, result.reply)
    assert "8,499" not in result.reply.replace(",", "")

def test_ambiguous_payment_timing_does_not_create_ptp_by_itself(db, verified_call):
    """The scripted model asks for clarification instead of calling the PTP tool."""
    llm = ScriptedLLM(
        text("Could you confirm a specific payment date and amount?")
    )
    result = handle_turn(
        db,
        verified_call,
        "I might pay in 3 to 4 days.",
        llm=llm,
    )

    assert result.reply
    assert_no_ptp_event(db, verified_call)
    assert "PTP" not in event_types(db, verified_call)

def test_removed_payment_link_tool_is_rejected(db, verified_call):
    """The production app should reject the removed tool rather than execute it."""
    llm = ScriptedLLM(
        tool("send_payment_link", {"channel": "SMS"}),
        text(
            "I can't send payment links. "
            "Please use the lender's official app or website."
        ),
    )

    result = handle_turn(
        db,
        verified_call,
        "Send me a payment link.",
        llm=llm,
    )

    tool_result_messages = [
        message
        for messages, _tools in llm.calls
        for message in messages
        if message.get("role") == "tool"
    ]

    assert tool_result_messages
    assert any(
        "Unknown tool" in message.get("content", "")
        for message in tool_result_messages
    )
    assert result.reply

def test_do_not_call_does_not_invoke_llm(db, call, customer):
    llm = ScriptedLLM()
    result = handle_turn(db, call, "Please stop calling me.", llm=llm)

    assert result.ended
    assert result.disposition == "DO_NOT_CALL"
    assert customer.do_not_call is True
    assert llm.calls == []


def test_do_not_call_records_expected_disposition_event(db, call):
    handle_turn(db, call, "Please stop calling me.", llm=ScriptedLLM())
    assert event_types(db, call) == ["DISPOSITION"]