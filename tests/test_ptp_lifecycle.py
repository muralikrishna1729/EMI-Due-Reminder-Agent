from datetime import date, timedelta

from app.engine import handle_turn
from app.models import CallEvent
from tests.helpers import ScriptedLLM, text, tool


def test_confirmed_ptp_ends_once_with_the_recorded_commitment(db, verified_call):
    promised_date = (date.today() + timedelta(days=3)).isoformat()

    record_result = handle_turn(
        db,
        verified_call,
        f"I will pay on {promised_date}",
        llm=ScriptedLLM(
            tool("log_promise_to_pay", {"ptp_date": promised_date, "amount": 8499}),
            text(f"I recorded {promised_date} for ₹8,499. Is that correct?"),
        ),
    )
    complete_result = handle_turn(
        db,
        verified_call,
        "Yes, that is correct.",
        llm=ScriptedLLM(
            tool("mark_disposition", {"status": "PTP_AGREED"}),
            text(f"Thank you. Your payment of ₹8,499 on {promised_date} is confirmed. Goodbye."),
        ),
    )

    ptp_events = db.query(CallEvent).filter_by(session_id=verified_call.id, type="PTP").all()
    assert record_result.ended is False
    assert len(ptp_events) == 1
    assert ptp_events[0].payload["ptp_date"] == promised_date
    assert ptp_events[0].payload["amount"] == 8499
    assert complete_result.ended is True
    assert complete_result.disposition == "PTP_AGREED"
    assert verified_call.state == "ENDED"
    assert promised_date in complete_result.reply
