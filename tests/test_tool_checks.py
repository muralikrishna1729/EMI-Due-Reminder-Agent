from datetime import date

from app.tool_checks import (
    check_tool_request, dates_customer_agreed_to, dates_in_text, ptp_logged_this_turn,
)

TODAY = date(2026, 10, 21)  # a Wednesday


def user(t):
    return {"role": "user", "content": t}


def agent(t):
    return {"role": "assistant", "content": t}


def dates(*texts, today=TODAY):
    return dates_in_text(list(texts), today)


def d(y, m, day):
    return date(y, m, day)


def ptp(s):
    return {"ptp_date": s, "amount": 8499}


def ptp_check(date_str, msgs):
    return check_tool_request("log_promise_to_pay", ptp(date_str), msgs, TODAY)


# ---------- words to dates ----------
def test_tomorrow():
    assert dates("I will pay tomorrow") == {d(2026, 10, 22)}


def test_day_after_tomorrow_is_not_also_tomorrow():
    assert dates("day after tomorrow") == {d(2026, 10, 23)}
    assert dates("parso kar dunga") == {d(2026, 10, 23)}


def test_friday_is_the_coming_friday_not_the_28th():
    assert dates("I will pay on Friday") == {d(2026, 10, 23)}


def test_next_friday():
    assert dates("next friday") == {d(2026, 10, 23), d(2026, 10, 30)}


def test_friday_on_a_friday():
    assert dates("friday", today=d(2026, 10, 23)) == {d(2026, 10, 23), d(2026, 10, 30)}


def test_in_n_days():
    assert dates("I can pay in 3 days") == {d(2026, 10, 24)}


def test_ordinals_and_months():
    assert dates("on the 25th") == {d(2026, 10, 25)}
    assert dates("on the 5th") == {d(2026, 11, 5)}
    assert dates("25 october") == {d(2026, 10, 25)}
    assert dates("october 25th") == {d(2026, 10, 25)}
    assert dates("5 october") == {d(2027, 10, 5)}
    assert dates("2026-10-25") == {d(2026, 10, 25)}


def test_no_date_in_these_chat_lines():
    for t in ["okay, i will pay.", "12 days over dues means ??", "how many days left for me to pay this ??",
              "Yes.", "yeah, sure. it was 2345", "it was 2000.", "maybe I will pay",
              "yeah, okay. i will within 3 to 4 days, was it possible ?", "it was month-end.",
              "can i pay middle of next month ?"]:
        assert dates(t) == set(), t


# ---------- checks before a tool ----------
def test_ptp_blocked_when_no_date_was_said():
    err = ptp_check("2026-10-21", [agent("When will you pay?"), user("okay, i will pay.")])
    assert err and "not stated or clearly accepted" in err


def test_ptp_blocked_when_friday_became_the_28th():
    err = ptp_check("2026-10-28", [user("I will pay on Friday")])
    assert err and "2026-10-23" in err


def test_ptp_allowed_when_the_date_matches():
    assert ptp_check("2026-10-23", [user("I will pay on Friday")]) is None


def test_assistant_words_alone_never_count():
    # the agent proposed Friday, but the customer did not answer with a clear yes
    assert ptp_check("2026-10-23", [agent("Will you pay on Friday?"), user("what is this about")])


def test_latest_date_wins():
    msgs = [user("friday"), user("no, make it the 28th")]
    assert ptp_check("2026-10-23", msgs)
    assert ptp_check("2026-10-28", msgs) is None


# ---- proposed by the agent, accepted by the customer (the real chats) ----
def test_a_clear_yes_accepts_the_date_the_agent_proposed():
    msgs = [agent("Would Saturday, 24 October work for you?"), user("yes")]
    assert ptp_check("2026-10-24", msgs) is None


def test_iso_proposal_and_yes():
    msgs = [agent("Would 2026-11-15 work for you to clear the ₹12,500 EMI?"), user("Yeah, okay")]
    assert ptp_check("2026-11-15", msgs) is None


def test_might_be_does_not_accept_a_proposed_date():
    msgs = [agent("Would 24 October 2026 work for you to clear the ₹12,500 overdue EMI?"), user("might be.")]
    assert ptp_check("2026-10-24", msgs)


def test_doubt_or_a_question_is_not_acceptance():
    for reply in ["yes, but i'm not completly sure about that.",
                  "yeah, okay. may i know, your name ??",
                  "okay i think so",
                  "i think, we already fixed on this disucssion, it was already done, isn't it ?"]:
        msgs = [agent("Would 24 October work for you?"), user(reply)]
        assert ptp_check("2026-10-24", msgs), reply


def test_yes_does_not_accept_a_different_date_than_the_one_proposed():
    msgs = [agent("Would 24 October work for you?"), user("yes")]
    err = ptp_check("2026-10-28", msgs)
    assert err and "2026-10-24" in err


def test_yes_to_a_message_with_no_date_accepts_nothing():
    msgs = [agent("When will you pay?"), user("yes")]
    assert dates_customer_agreed_to(msgs, TODAY) == set()


# ---- verification code ----
def test_123456_cannot_verify_as_1234():
    err = check_tool_request("verify_customer", {"verification_code": "1234"},
                             [user("My PAN number is 123456")], TODAY)
    assert err and "has not said that 4-digit code" in err


def test_standalone_four_digits_can_verify():
    assert check_tool_request("verify_customer", {"verification_code": "2345"},
                              [user("yeah, sure. it was 2345")], TODAY) is None


# ---- confirm before ending ----
def test_ptp_agreed_blocked_in_the_same_turn_as_the_ptp():
    msgs = [user("I will pay Friday"), agent(""),
            {"role": "tool", "tool_call_id": "c1", "content": '{"ok": true, "ptp_id": "PTP-1234"}'}]
    assert ptp_logged_this_turn(msgs)
    assert check_tool_request("mark_disposition", {"status": "PTP_AGREED"}, msgs, TODAY)


def test_ptp_agreed_allowed_in_a_later_turn():
    msgs = [{"role": "tool", "content": '{"ok": true, "ptp_id": "PTP-1234"}'}, user("yes, thanks")]
    assert check_tool_request("mark_disposition", {"status": "PTP_AGREED"}, msgs, TODAY) is None


def test_other_tools_are_not_affected():
    assert check_tool_request("escalate_to_agent", {"reason": "DISPUTE"}, [], TODAY) is None
    assert check_tool_request("mark_disposition", {"status": "WRONG_PERSON"}, [], TODAY) is None