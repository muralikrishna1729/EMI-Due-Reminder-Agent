import pytest

from app import config
from app.engine import handle_turn
from app.guardrails import HOLD_RE, leaks_debt_info
from app.models import CallEvent
from tests.helpers import ScriptedLLM


HOLD_YES = [
    "could you please give me 2 or 3 minutes",
    "can you wait for 2-3 minutes",
    "I currently not remember my password. Could you give me 2 or 3 minutes so that I can see my notes",
    "hold on",
    "hang on a sec",
    "let me check my notes",
    "give me a minute",
    "just a minute please",
    "i need two minutes to find it",
    "ek minute",
    "thoda ruko",
]

HOLD_NO = [
    "I will pay on Friday",
    "it was 1995",
    "I'm not sure",
    "call me tomorrow",
    "how many days are left",
    "wait, what is the amount",
    "I'll pay in 3 minutes",
    "can I pay after two or three months",
    "my pan ends with one two three four",
    "take your time",
]


@pytest.mark.parametrize("text", HOLD_YES)
def test_hold_requests_are_recognized(text):
    assert HOLD_RE.search(text)


@pytest.mark.parametrize("text", HOLD_NO)
def test_other_sentences_are_not_hold_requests(text):
    assert not HOLD_RE.search(text)


def test_a_hold_request_is_answered_without_the_llm(db, call):
    result = handle_turn(
        db,
        call,
        "could you give me 2 or 3 minutes to find my PAN",
        llm=ScriptedLLM(),
    )
    assert "take your time" in result.reply
    assert result.hold_seconds == config.HOLD_SECONDS
    assert result.ended is False
    events = db.query(CallEvent).filter_by(session_id=call.id).all()
    assert [event.type for event in events] == ["HOLD"]


def test_only_one_hold_is_allowed_per_call(db, call):
    first = handle_turn(db, call, "give me a minute", llm=ScriptedLLM())
    second = handle_turn(db, call, "give me a minute again", llm=ScriptedLLM())

    assert first.hold_seconds == config.HOLD_SECONDS
    assert second.hold_seconds == 0
    assert "only wait once" in second.reply.lower()
    events = db.query(CallEvent).filter_by(session_id=call.id, type="HOLD").all()
    assert len(events) == 1


def test_hold_reply_does_not_disclose_debt_before_verification(db, call):
    result = handle_turn(db, call, "hold on", llm=ScriptedLLM())
    assert not leaks_debt_info(result.reply)


def test_do_not_call_closing_is_warm(db, call):
    result = handle_turn(db, call, "stop calling me", llm=ScriptedLLM())
    assert result.ended
    assert "won't call you again" in result.reply
    assert "take care" in result.reply


def test_no_response_closing_is_warm(db, call):
    handle_turn(db, call, "", llm=ScriptedLLM())
    result = handle_turn(db, call, "", llm=ScriptedLLM())
    assert result.ended
    assert "thank you" in result.reply.lower()
    assert "take care" in result.reply.lower()


def test_repeated_abuse_closing_is_polite(db, call):
    handle_turn(db, call, "you idiot", llm=ScriptedLLM())
    result = handle_turn(db, call, "you stupid idiot", llm=ScriptedLLM())
    assert result.ended
    assert "thank you for your time" in result.reply.lower()
