import pytest

from app.guardrails import (
    DNC_RE,
    SAFE_GOODBYE,
    SAFE_VERIFY_PROMPT,
    is_abusive,
    leaks_debt_info,
    sanitize_pre_auth_reply,
)


@pytest.mark.parametrize(
    "text",
    [
        "Your overdue amount is Rs. 8499",
        "You owe us ₹8,499",
        "Your EMI is pending",
        "You are 12 days past due",
        "Call me on 9876543210",  # false positive on purpose: fail closed
    ],
)
def test_leaks_are_detected(text):
    assert leaks_debt_info(text)


@pytest.mark.parametrize(
    "text",
    [
        "Could you please share the last four digits of your PAN?",
        "Sorry for the interruption. Goodbye.",
        "premium plan",  # \b stops a match inside a word
    ],
)
def test_clean_text_passes(text):
    assert not leaks_debt_info(text)


@pytest.mark.parametrize(
    "text",
    ["Please stop calling me", "do not call me again", "don't call me", "don’t call me",
     "never call again", "remove my number", "call mat karo"],
)
def test_dnc_phrases_match(text):
    assert DNC_RE.search(text)


@pytest.mark.parametrize("text", ["Can you call me tomorrow?", "I am calling about my bill"])
def test_normal_text_is_not_dnc(text):
    assert not DNC_RE.search(text)


def test_abuse_detection():
    assert is_abusive("you idiot")
    assert not is_abusive("I will pay on Friday")


def test_sanitizer_replaces_leaks_only():
    assert sanitize_pre_auth_reply("Your overdue EMI is pending", call_ended=False) == SAFE_VERIFY_PROMPT
    assert sanitize_pre_auth_reply("Your overdue EMI is pending", call_ended=True) == SAFE_GOODBYE
    assert sanitize_pre_auth_reply("Hello there", call_ended=False) == "Hello there"

