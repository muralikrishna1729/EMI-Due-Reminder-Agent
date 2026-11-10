import pytest

from app.speech_text import normalize_transcript


@pytest.mark.parametrize("raw,expected", [
    ("1 2 3 4", "1234"),
    ("1, 2, 3, 4.", "1234."),
    ("my pan ends with one two three four", "my pan ends with 1234"),
    ("nine nine nine nine", "9999"),
    ("it was 1995", "it was 1995"),
    ("pay in 3 4 days", "pay in 3 4 days"),
    ("on 2026-10-24", "on 2026-10-24"),
])
def test_normalize(raw, expected):
    assert normalize_transcript(raw) == expected
