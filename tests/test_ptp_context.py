from datetime import date, timedelta

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
