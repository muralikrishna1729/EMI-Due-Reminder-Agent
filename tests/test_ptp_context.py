from datetime import date, timedelta

from app.models import CallEvent
from app.prompts import build_system_prompt
from app.tools import execute_tool


def test_prompt_includes_the_recorded_ptp_date_and_amount(db, verified_call):
    promised_date = (date.today() + timedelta(days=3)).isoformat()
    execute_tool(
        db,
        verified_call,
        "log_promise_to_pay",
        {"ptp_date": promised_date, "amount": 8499},
    )

    prompt = build_system_prompt(verified_call)

    assert promised_date in prompt
    assert "8,499" in prompt
    assert "Do not negotiate another date" in prompt


def test_prompt_uses_the_newest_ptp_event_by_id(db, verified_call):
    verified_call.ptp_logged = True
    db.add_all(
        [
            CallEvent(
                session_id=verified_call.id,
                type="PTP",
                payload={"ptp_date": "2026-12-06", "amount": 8499},
            ),
            CallEvent(
                session_id=verified_call.id,
                type="PTP",
                payload={"ptp_date": "2026-12-09", "amount": 8000},
            ),
        ]
    )
    db.commit()

    prompt = build_system_prompt(verified_call)

    assert "2026-12-09" in prompt
    assert "8,000" in prompt
    assert "2026-12-06" not in prompt


def test_prompt_fails_safely_when_ptp_flag_has_no_event(db, verified_call):
    verified_call.ptp_logged = True
    db.commit()

    prompt = build_system_prompt(verified_call)

    assert "No promise has been recorded" not in prompt
    assert "may already be recorded" in prompt
    assert "Do not negotiate another date or amount" in prompt
