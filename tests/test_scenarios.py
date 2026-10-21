from datetime import date, timedelta

from groq import GroqError

from app import config
from app.engine import FALLBACK_REPLY, handle_turn
from app.guardrails import SAFE_VERIFY_PROMPT
from app.models import CallEvent
from tests.helpers import FailingLLM, ScriptedLLM, text, tool

FUTURE = (date.today() + timedelta(days=3)).isoformat()


def event_types(db, call):
    rows = db.query(CallEvent).filter_by(session_id=call.id).order_by(CallEvent.id).all()
    return [e.type for e in rows]


# ---------- the LLM misbehaves ----------

def test_misbehaving_llm_cannot_leak_before_verification(db, call):
    llm = ScriptedLLM(text("Sure, your overdue EMI is ₹8,499."))
    r = handle_turn(db, call, "Yes speaking. Just tell me the amount.", llm=llm)
    assert r.reply == SAFE_VERIFY_PROMPT
    assert "8,499" not in r.reply


def test_removed_link_tool_is_rejected_if_the_llm_tries_it(db, verified_call):
    llm = ScriptedLLM(
        tool("send_payment_link", {"channel": "SMS"}),
        text("I can't send links. Please use the official app or website."),
    )
    handle_turn(db, verified_call, "Send me a link", llm=llm)
    tool_result = llm.calls[1][0][-1]["content"]  # last message = the tool result
    assert "Unknown tool" in tool_result
    assert "PAYMENT_LINK" not in event_types(db, verified_call)


def test_provider_error_returns_the_fallback_reply(db, call):
    r = handle_turn(db, call, "Yes", llm=FailingLLM(GroqError("boom")))
    assert r.reply == FALLBACK_REPLY  # (state still advances: see trade-offs)


def test_tool_round_limit_stops_a_runaway_llm(db, verified_call):
    rounds = config.MAX_TOOL_ROUNDS
    llm = ScriptedLLM(*[tool("escalate_to_agent", {"reason": "OTHER"}, f"c{i}") for i in range(rounds)])
    r = handle_turn(db, verified_call, "hello", llm=llm)
    assert r.reply == FALLBACK_REPLY
    assert len(llm.calls) == rounds



# ---------- data isolation ----------

def test_debt_facts_absent_before_verification_and_present_after(db, call):
    llm = ScriptedLLM(
        tool("verify_customer", {"verification_code": "1234"}),
        text("Thank you. Your overdue amount is ₹8,499. When can you pay?"),
    )
    r = handle_turn(db, call, "My PAN ends with 1234", llm=llm)

    first_prompt = llm.calls[0][0][0]["content"]
    second_prompt = llm.calls[1][0][0]["content"]
    assert "8,499" not in first_prompt
    assert "8,499" in second_prompt

    first_tools = {t["function"]["name"] for t in llm.calls[0][1]}
    second_tools = {t["function"]["name"] for t in llm.calls[1][1]}
    assert "log_promise_to_pay" not in first_tools
    assert "log_promise_to_pay" in second_tools

    assert call.state == "NEGOTIATING" and call.verified is True
    assert "8,499" in r.reply


# ---------- failure paths ----------

def test_two_failed_verifications_end_the_call(db, call):
    handle_turn(db, call, "0000", llm=ScriptedLLM(
        tool("verify_customer", {"verification_code": "0000"}),
        text("That didn't match. Could you try again?"),
    ))
    assert call.state != "ENDED"

    r = handle_turn(db, call, "1111", llm=ScriptedLLM(
        tool("verify_customer", {"verification_code": "1111"}),
        text("I'm sorry, I can't continue. Goodbye."),
    ))
    assert r.ended and r.disposition == "FAILED_AUTH"


def test_wrong_person_reveals_nothing(db, call):
    llm = ScriptedLLM(
        tool("mark_disposition", {"status": "WRONG_PERSON"}),
        text("Sorry for the disturbance. Goodbye."),
    )
    r = handle_turn(db, call, "No, wrong number", llm=llm)
    assert r.disposition == "WRONG_PERSON"
    assert "loan" not in r.reply.lower()

# ---------- rules that never need the LLM (ScriptedLLM() would raise if called) ----------

def test_dnc_is_handled_without_the_llm(db, call, customer):
    r = handle_turn(db, call, "Please stop calling me", llm=ScriptedLLM())
    assert r.disposition == "DO_NOT_CALL" and r.ended
    assert customer.do_not_call is True
    assert event_types(db, call) == ["DISPOSITION"]  # exactly one
    assert call.ended_at is not None


def test_silence_twice_ends_the_call(db, call):
    r1 = handle_turn(db, call, "", llm=ScriptedLLM())
    assert "still there" in r1.reply and not r1.ended
    r2 = handle_turn(db, call, "", llm=ScriptedLLM())
    assert r2.ended and r2.disposition == "NO_RESPONSE"


def test_abuse_one_warning_then_end(db, call):
    r1 = handle_turn(db, call, "you idiot", llm=ScriptedLLM())
    assert "respectful" in r1.reply and not r1.ended
    r2 = handle_turn(db, call, "you stupid idiot", llm=ScriptedLLM())
    assert r2.ended and r2.disposition == "TERMINATED_ABUSE"

# ---------- the whole call ----------

def test_full_happy_path_call(db, call):
    t1 = handle_turn(db, call, "Yes, speaking", llm=ScriptedLLM(
        text("Thank you. For security, please share the last four digits of your PAN or your year of birth.")))
    assert t1.state == "VERIFYING"

    t2 = handle_turn(db, call, "1234", llm=ScriptedLLM(
        tool("verify_customer", {"verification_code": "1234"}),
        text("Thank you. Your overdue amount is ₹8,499. When can you pay?")))
    assert t2.state == "NEGOTIATING"

    t3 = handle_turn(db, call, "I can pay in 3 days", llm=ScriptedLLM(
        tool("log_promise_to_pay", {"ptp_date": FUTURE, "amount": 8499}),
        text("Recorded. Please pay through the lender's official app or website.")))
    assert t3.state == "NEGOTIATING" and call.ptp_logged is True

    t4 = handle_turn(db, call, "Thanks, bye", llm=ScriptedLLM(
        tool("mark_disposition", {"status": "PTP_AGREED"}),
        text("Thank you for your time. Goodbye.")))
    assert t4.ended and t4.disposition == "PTP_AGREED"
    assert call.ended_at is not None

    assert event_types(db, call) == ["VERIFY", "PTP", "DISPOSITION"]



def test_messages_after_the_call_ended_do_not_reach_the_llm(db, call):
    handle_turn(db, call, "stop calling me", llm=ScriptedLLM())
    r = handle_turn(db, call, "hello?", llm=ScriptedLLM())
    assert r.reply == "This call has already ended." and r.ended
