import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app


@pytest.fixture
def client(db, customer):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def start(client):
    return client.post("/calls", json={"account_id": "ACC-88392"}).json()["session_id"]


def send(client, sid):
    return client.post(f"/calls/{sid}/voice", files={"audio": ("a.webm", b"x" * 10, "audio/webm")})


def test_silence_is_handled_like_typed_silence(client, monkeypatch):
    monkeypatch.setattr("app.voice.transcribe", lambda data, filename="audio.webm", *args, **kwargs: "")
    r = send(client, start(client)).json()
    assert "still there" in r["reply"] and r["ended"] is False


def test_spoken_stop_calling_ends_the_call(client, monkeypatch):
    monkeypatch.setattr("app.voice.transcribe", lambda data, filename="audio.webm", *args, **kwargs: "please stop calling me")
    r = send(client, start(client)).json()
    assert r["ended"] is True and r["disposition"] == "DO_NOT_CALL"


def test_speech_to_text_failure_returns_502(client, monkeypatch):
    def boom(data, filename="audio.webm", *args, **kwargs):
        raise RuntimeError("provider down")
    monkeypatch.setattr("app.voice.transcribe", boom)
    assert send(client, start(client)).status_code == 502
