import pytest

from app.guardrails import (
    DNC_RE,
    SAFE_GOODBYE,
    SAFE_VERIFY_PROMPT,
    THIRD_PARTY_RE,
    is_abusive,
    leaks_debt_info,
    sanitize_pre_auth_reply,
    tidy_reply,
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


@pytest.mark.parametrize("text", [
    "Yes, But it was her father, she was eating, was it any urgent ?",
    "No. i'm her cousin. may i know who is speaking ?",
    "I'm his brother", "she's not here", "he is busy right now", "wrong number",
])
def test_third_party_detected(text):
    assert THIRD_PARTY_RE.search(text)


@pytest.mark.parametrize("text", [
    "Yes, Speaking.", "yeah, sure. it was 2345", "yes, i'm priya.", "yes, i'm nair.",
    "i will pay in 3 days", "my father has the same bank",
])
def test_third_party_not_detected_for_the_customer(text):
    assert not THIRD_PARTY_RE.search(text)


CHAT4 = (
    "No problem. When do you think you'll be able to pay the ₹12,500 EMI?"
    "We understand things can slip. Could you let us know a convenient date to settle the ₹12,500 overdue amount?"
    "Whenever you're ready, just let us know a date that works for you to clear the payment."
    "We're happy to work with you—please tell us a date you can make the ₹12,500 payment."
)


def test_tidy_keeps_three_sentences_and_fixes_glued_text():
    assert tidy_reply(CHAT4) == (
        "No problem. When do you think you'll be able to pay the ₹12,500 EMI? "
        "We understand things can slip."
    )


def test_tidy_drops_exact_repeats():
    assert tidy_reply("Hello there. Hello there. How are you?") == "Hello there. How are you?"


def test_tidy_leaves_short_replies_alone():
    s = "Thank you. Your overdue amount is ₹8,499. When can you pay?"
    assert tidy_reply(s) == s


def test_tidy_caps_a_very_long_sentence():
    assert len(tidy_reply("word " * 200)) <= 350

