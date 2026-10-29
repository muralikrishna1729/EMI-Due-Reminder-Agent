import json
from datetime import date, timedelta

from app import config
from app.models import CallEvent
from app.tools import execute_tool

FUTURE = (date.today() + timedelta(days=3)).isoformat()


def events(db, call, type_=None):
    query = db.query(CallEvent).filter_by(session_id=call.id)
    if type_:
        query = query.filter_by(type=type_)
    return query.order_by(CallEvent.id).all()


# ---------- the gatekeeper ----------

def test_unknown_tool_is_rejected(db, call):
    r = execute_tool(db, call, "send_payment_link", {"channel": "SMS"})
    assert r["ok"] is False and "Unknown tool" in r["error"]


def test_tool_in_wrong_state_is_blocked_and_logged(db, call):
    r = execute_tool(db, call, "log_promise_to_pay", {"ptp_date": FUTURE, "amount": 8499})
    assert r["ok"] is False and "not allowed" in r["error"]
    assert len(events(db, call, "BLOCKED_TOOL")) == 1
    assert call.ptp_logged is False


def test_invalid_arguments_return_an_error_not_a_crash(db, call):
    r = execute_tool(db, call, "verify_customer", {"verification_code": "abc"})
    assert r["ok"] is False and "Invalid arguments" in r["error"]


# ---------- verification ----------

def test_correct_pan_digits_verify(db, call):
    r = execute_tool(db, call, "verify_customer", {"verification_code": "1234"})
    assert r["verified"] is True
    assert r["customer_name"] == "Rahul S*****"
    assert call.verified is True and call.state == "NEGOTIATING"


def test_birth_year_also_verifies(db, call):
    r = execute_tool(db, call, "verify_customer", {"verification_code": "1995"})
    assert r["verified"] is True


def test_wrong_code_allows_one_retry(db, call):
    r = execute_tool(db, call, "verify_customer", {"verification_code": "0000"})
    assert r["verified"] is False and r["attempts_left"] == 1
    assert call.verified is False and call.state != "ENDED"


def test_second_wrong_code_ends_the_call_as_failed_auth(db, call):
    execute_tool(db, call, "verify_customer", {"verification_code": "0000"})
    r = execute_tool(db, call, "verify_customer", {"verification_code": "1111"})
    assert r["call_ended"] is True
    assert call.state == "ENDED" and call.disposition == "FAILED_AUTH"


def test_verify_events_never_contain_the_code(db, call):
    execute_tool(db, call, "verify_customer", {"verification_code": "0000"})
    execute_tool(db, call, "verify_customer", {"verification_code": "1234"})
    for e in events(db, call, "VERIFY"):
        dumped = json.dumps(e.payload)
        assert "0000" not in dumped and "1234" not in dumped


# Optional: keep only if you added the _to_str validator to VerifyArgs.
def test_code_sent_as_a_number_is_accepted(db, call):
    r = execute_tool(db, call, "verify_customer", {"verification_code": 1234})
    assert r["verified"] is True


# ---------- promise to pay ----------
# overdue = 8499, waiver ceiling 10% -> minimum = 7649.1

def test_waiver_boundary(db, verified_call):
    low = execute_tool(db, verified_call, "log_promise_to_pay", {"ptp_date": FUTURE, "amount": 7649})
    assert low["ok"] is False and low["must_escalate"] is True
    ok = execute_tool(db, verified_call, "log_promise_to_pay", {"ptp_date": FUTURE, "amount": 7650})
    assert ok["ok"] is True


def test_amount_above_overdue_is_rejected(db, verified_call):
    r = execute_tool(db, verified_call, "log_promise_to_pay", {"ptp_date": FUTURE, "amount": 9000})
    assert r["ok"] is False


def test_past_date_is_rejected(db, verified_call):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    r = execute_tool(db, verified_call, "log_promise_to_pay", {"ptp_date": yesterday, "amount": 8499})
    assert r["ok"] is False


def test_date_window_boundaries(db, verified_call):
    last_ok = (date.today() + timedelta(days=config.MAX_PTP_DAYS_AHEAD)).isoformat()
    too_far = (date.today() + timedelta(days=config.MAX_PTP_DAYS_AHEAD + 1)).isoformat()
    assert execute_tool(db, verified_call, "log_promise_to_pay", {"ptp_date": last_ok, "amount": 8499})["ok"]
    assert not execute_tool(db, verified_call, "log_promise_to_pay", {"ptp_date": too_far, "amount": 8499})["ok"]


def test_rejected_ptp_creates_no_event(db, verified_call):
    execute_tool(db, verified_call, "log_promise_to_pay", {"ptp_date": FUTURE, "amount": 100})
    assert events(db, verified_call, "PTP") == []
    assert verified_call.ptp_logged is False


def test_accepted_ptp_sets_flag_and_event(db, verified_call):
    r = execute_tool(db, verified_call, "log_promise_to_pay", {"ptp_date": FUTURE, "amount": 8499})
    assert r["ptp_id"].startswith("PTP-")
    assert verified_call.ptp_logged is True
    assert len(events(db, verified_call, "PTP")) == 1


# ---------- escalation ----------

def test_escalation_creates_ticket_and_event(db, verified_call):
    r = execute_tool(db, verified_call, "escalate_to_agent",
                     {"reason": "DISPUTE", "summary": "Says already paid"})
    assert r["ticket_id"].startswith("ESC-")
    assert len(events(db, verified_call, "ESCALATION")) == 1


def test_invalid_escalation_reason_is_rejected(db, verified_call):
    r = execute_tool(db, verified_call, "escalate_to_agent", {"reason": "ANGRY"})
    assert r["ok"] is False


# ---------- dispositions ----------

def test_ptp_agreed_requires_a_logged_ptp(db, verified_call):
    r = execute_tool(db, verified_call, "mark_disposition", {"status": "PTP_AGREED"})
    assert r["ok"] is False and verified_call.state == "NEGOTIATING"


def test_financial_status_not_allowed_before_verification(db, call):
    r = execute_tool(db, call, "mark_disposition", {"status": "DISPUTED"})
    assert r["ok"] is False


def test_wrong_person_allowed_before_verification(db, call):
    r = execute_tool(db, call, "mark_disposition", {"status": "WRONG_PERSON"})
    assert r["ok"] is True and call.state == "ENDED" and call.ended_at is not None


def test_happy_path_without_any_payment_link(db, verified_call):
    assert execute_tool(db, verified_call, "log_promise_to_pay", {"ptp_date": FUTURE, "amount": 8499})["ok"]
    r = execute_tool(db, verified_call, "mark_disposition", {"status": "PTP_AGREED"})
    assert r["call_ended"] is True and verified_call.state == "ENDED"
    assert [e.type for e in events(db, verified_call)] == ["PTP", "DISPOSITION"]


def test_disputed_requires_an_escalation_first(db, verified_call):
    r = execute_tool(db, verified_call, "mark_disposition", {"status": "DISPUTED"})
    assert r["ok"] is False and "escalate_to_agent" in r["error"]
    assert verified_call.state == "NEGOTIATING"
    execute_tool(db, verified_call, "escalate_to_agent", {"reason": "WAIVER_REQUEST"})
    r = execute_tool(db, verified_call, "mark_disposition", {"status": "HARDSHIP_ESCALATED"})
    assert r["ok"] is True and verified_call.state == "ENDED"


def test_llm_notes_are_labelled(db, verified_call):
    execute_tool(db, verified_call, "escalate_to_agent", {"reason": "OTHER"})
    execute_tool(db, verified_call, "mark_disposition", {"status": "DISPUTED", "notes": "hello"})
    ev = events(db, verified_call, "DISPOSITION")[0]
    assert ev.payload["notes"] == "[LLM-written] hello"