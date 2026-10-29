from datetime import date, timedelta

from app.engine import handle_turn
from app.guardrails import SAFE_GOODBYE
from tests.helpers import ScriptedLLM, text, tool


def tomorrow_iso():
    return (date.today() + timedelta(days=1)).isoformat()


def test_engine_promise_to_pay_and_confirm(db, verified_call):
    llm = ScriptedLLM(
        tool("log_promise_to_pay", {"ptp_date": tomorrow_iso(), "amount": 8499}),
        text("Recorded for tomorrow. Is that correct?"),
    )
    handle_turn(db, verified_call, "I will pay tomorrow", llm=llm)
    assert verified_call.ptp_logged is True


def test_engine_makes_the_agent_confirm_before_ending(db, verified_call):
    llm = ScriptedLLM(
        tool("log_promise_to_pay", {"ptp_date": tomorrow_iso(), "amount": 8499}),
        tool("mark_disposition", {"status": "PTP_AGREED"}, "c2"),
        text("I recorded tomorrow for ₹8,499. Is that correct?"),
    )
    r = handle_turn(db, verified_call, "I will pay tomorrow", llm=llm)
    assert r.ended is False and verified_call.ptp_logged is True and len(llm.calls) == 3


def test_engine_does_not_verify_123456_as_1234(db, call):
    llm = ScriptedLLM(
        tool("verify_customer", {"verification_code": "1234"}),
        text("Please share just the last four digits of your PAN or your birth year."),
    )
    handle_turn(db, call, "My PAN number is 123456", llm=llm)
    assert call.verified is False and call.state != "NEGOTIATING"


def test_engine_accepts_a_clear_yes_to_a_proposed_date(db, verified_call):
    proposed = tomorrow_iso()
    verified_call.history = [{"role": "assistant", "content": f"Would {proposed} work for you?"}]
    db.commit()
    llm = ScriptedLLM(
        tool("log_promise_to_pay", {"ptp_date": proposed, "amount": 8499}),
        text("Recorded. Is that correct?"),
    )
    handle_turn(db, verified_call, "yes", llm=llm)
    assert verified_call.ptp_logged is True


def test_engine_blocks_a_proposed_date_when_the_customer_is_unsure(db, verified_call):
    proposed = tomorrow_iso()
    verified_call.history = [{"role": "assistant", "content": f"Would {proposed} work for you?"}]
    db.commit()
    llm = ScriptedLLM(
        tool("log_promise_to_pay", {"ptp_date": proposed, "amount": 8499}),
        text("Could you confirm that day with a clear yes?"),
    )
    handle_turn(db, verified_call, "might be.", llm=llm)
    assert verified_call.ptp_logged is False


def test_a_relative_answering_ends_the_call_without_the_llm(db, call):
    r = handle_turn(db, call, "Yes, But it was her father, she was eating, was it any urgent ?",
                    llm=ScriptedLLM())
    assert r.ended and r.disposition == "WRONG_PERSON" and r.reply == SAFE_GOODBYE


def test_repeated_sentences_are_removed_before_the_customer_sees_them(db, verified_call):
    messy = ("No problem. When do you think you'll be able to pay the ₹12,500 EMI?"
             "We understand things can slip. Could you let us know a date?"
             "Whenever you're ready, tell us a date.")
    r = handle_turn(db, verified_call, "i forgot", llm=ScriptedLLM(text(messy)))
    assert r.reply == ("No problem. When do you think you'll be able to pay the ₹12,500 EMI? "
                       "We understand things can slip.")


def test_a_rate_reduction_request_cannot_end_as_disputed_without_escalation(db, verified_call):
    llm = ScriptedLLM(
        tool("mark_disposition", {"status": "DISPUTED"}),
        tool("escalate_to_agent", {"reason": "WAIVER_REQUEST"}, "c2"),
        tool("mark_disposition", {"status": "HARDSHIP_ESCALATED"}, "c3"),
        text("I'll pass your request to a human agent who will follow up. Goodbye."),
    )
    r = handle_turn(db, verified_call, "i want to reduce the interest rate 1%", llm=llm)
    assert r.ended and r.disposition == "HARDSHIP_ESCALATED"