import pytest
from fastapi.testclient import TestClient

from app import config
from app.db import get_db
from app.main import app

KEY = {"X-API-Key": config.ADMIN_API_KEY}


@pytest.fixture
def client(db, customer):
    app.dependency_overrides[get_db] = lambda: db  # use the test database
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_unknown_account_returns_404(client):
    assert client.post("/calls", json={"account_id": "NOPE"}).status_code == 404


def test_reports_require_the_api_key(client):
    assert client.get("/metrics").status_code == 401
    assert client.get("/dispositions").status_code == 401
    assert client.get("/metrics", headers={"X-API-Key": "wrong"}).status_code == 401


def test_dnc_flow_metrics_and_blocking(client):
    r = client.post("/calls", json={"account_id": "ACC-88392"})
    assert r.status_code == 200
    sid = r.json()["session_id"]

    body = client.post(f"/calls/{sid}/turn", json={"text": "Please stop calling me"}).json()
    assert body["ended"] is True and body["disposition"] == "DO_NOT_CALL"

    m = client.get("/metrics", headers=KEY).json()
    assert m["total_calls"] == 1
    assert m["by_disposition"] == {"DO_NOT_CALL": 1}
    assert m["ptp_rate"] == 0.0 and m["containment_rate"] == 1.0

    d = client.get("/dispositions", headers=KEY).json()
    assert len(d) == 1 and d[0]["status"] == "DO_NOT_CALL"

    # the customer is now on the do-not-call list
    assert client.post("/calls", json={"account_id": "ACC-88392"}).status_code == 403
