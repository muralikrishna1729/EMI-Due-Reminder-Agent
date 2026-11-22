import asyncio
import contextlib
import urllib.parse
import json
import pytest
import httpx
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app import config
from app.db import get_db
from app.core import ingest_pcm, clear_utterance_buffer, get_history_buffer, get_utterance_buffer

# ----------------------------------------------------------------------
# Helper to build a binary PCM frame: 4-byte little-endian frame index + Int16 PCM data
# ----------------------------------------------------------------------
def pack_frame(frame_idx: int, pcm_samples: list[int]) -> bytes:
    """Create a binary frame: 4-byte frame index + 2-byte per sample Int16 little-endian."""
    frame_bytes = frame_idx.to_bytes(4, byteorder='little')
    for sample in pcm_samples:
        # Convert sample to signed 16-bit little-endian
        val = int.from_bytes(sample.to_bytes(2, 'little'), signed=True)
        frame_bytes += val.to_bytes(2, 'little')
    return frame_bytes

# ----------------------------------------------------------------------
# Fixture: patch config.API_TOKEN to a known value for tests
# ----------------------------------------------------------------------
@pytest.fixture(autouse=True)
def patch_api_token(monkeypatch):
    monkeypatch.setattr(config, "API_TOKEN", "test_token")
    yield
    # No cleanup needed

# ----------------------------------------------------------------------
# WebSocket test wrappers for async test client
# ----------------------------------------------------------------------
class ClosedWebSocketSession:
    def __init__(self, code: int = 1008, reason: str = ""):
        self.code = code
        self.reason = reason

    async def send_bytes(self, data: bytes):
        raise WebSocketDisconnect(code=self.code, reason=self.reason)

    async def send_text(self, data: str):
        raise WebSocketDisconnect(code=self.code, reason=self.reason)

    async def send_json(self, data):
        raise WebSocketDisconnect(code=self.code, reason=self.reason)

    async def receive_bytes(self):
        raise asyncio.TimeoutError("WebSocket is closed")

    async def receive_text(self):
        raise asyncio.TimeoutError("WebSocket is closed")

    async def receive_json(self):
        raise asyncio.TimeoutError("WebSocket is closed")

    async def close(self, code: int = 1000):
        pass

class AsyncWebSocketSession:
    def __init__(self, ws):
        self._ws = ws

    async def send_bytes(self, data: bytes):
        return self._ws.send_bytes(data)

    async def send_text(self, data: str):
        return self._ws.send_text(data)

    async def send_json(self, data):
        return self._ws.send_json(data)

    async def receive_bytes(self):
        try:
            return self._ws.receive_bytes()
        except WebSocketDisconnect:
            raise asyncio.TimeoutError("WebSocket disconnected")

    async def receive_text(self):
        try:
            return self._ws.receive_text()
        except WebSocketDisconnect:
            raise asyncio.TimeoutError("WebSocket disconnected")

    async def receive_json(self):
        try:
            return self._ws.receive_json()
        except WebSocketDisconnect:
            raise asyncio.TimeoutError("WebSocket disconnected")

    async def close(self, code: int = 1000):
        try:
            return self._ws.close(code)
        except Exception:
            pass

class WebSocketTestHttpClient(httpx.AsyncClient):
    @contextlib.asynccontextmanager
    async def websocket_connect(self, url: str):
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        if parsed.query:
            path += f"?{parsed.query}"
        tc = TestClient(app)
        ws_session = None
        entered = False
        try:
            ws_ctx = tc.websocket_connect(path)
            raw_ws = ws_ctx.__enter__()
            entered = True
            ws_session = AsyncWebSocketSession(raw_ws)
        except WebSocketDisconnect as exc:
            ws_session = ClosedWebSocketSession(code=exc.code, reason=exc.reason)

        try:
            yield ws_session
        finally:
            if entered:
                try:
                    ws_ctx.__exit__(None, None, None)
                except Exception:
                    pass

# ----------------------------------------------------------------------
# Fixture: provide a test FastAPI client with websocket support
# ----------------------------------------------------------------------
@pytest.fixture
def async_client(db, customer):
    app.dependency_overrides[get_db] = lambda: db
    client = WebSocketTestHttpClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    yield client
    asyncio.run(client.aclose())
    app.dependency_overrides.clear()

# ----------------------------------------------------------------------
# Helper: create a dummy session via the /calls endpoint
# ----------------------------------------------------------------------
async def create_dummy_session(client: httpx.AsyncClient):
    response = await client.post("/calls", json={"account_id": "ACC-88392"})
    assert response.status_code == 200
    data = response.json()
    return data["session_id"]

# ----------------------------------------------------------------------
# Test: valid WebSocket connection and successful frame ingestion
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_websocket_valid_connection(async_client):
    session_id = await create_dummy_session(async_client)
    url = f"ws://test/ws/pcm/{session_id}?token=test_token"

    async with async_client.websocket_connect(url) as websocket:
        # Send a valid frame: index 0, 1 sample (value 1)
        frame = pack_frame(0, [1])
        await websocket.send_bytes(frame)

        # Receive acknowledgment
        response = await websocket.receive_json()
        assert response["frame_index"] == 0
        assert response["status"] == "ok"

# ----------------------------------------------------------------------
# Test: invalid token should close connection immediately
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_websocket_invalid_token(async_client):
    session_id = await create_dummy_session(async_client)
    url = f"ws://test/ws/pcm/{session_id}?token=wrong_token"

    async with async_client.websocket_connect(url) as websocket:
        # Connection should be closed immediately; receiving anything should raise
        with pytest.raises(asyncio.TimeoutError):
            await websocket.receive_text()

# ----------------------------------------------------------------------
# Test: binary too short (less than 4 bytes) should send error JSON and continue
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_websocket_invalid_binary_too_short(async_client):
    session_id = await create_dummy_session(async_client)
    url = f"ws://test/ws/pcm/{session_id}?token=test_token"

    async with async_client.websocket_connect(url) as websocket:
        # Send incomplete frame (only 3 bytes)
        await websocket.send_bytes(b'\x00\x00\x00')
        # Expect an error JSON message
        error_msg = await websocket.receive_json()
        assert error_msg["error"] == "Frame too short"

# ----------------------------------------------------------------------
# Test: invalid PCM length (odd number of bytes) should send error JSON
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_websocket_invalid_pcm_length(async_client):
    session_id = await create_dummy_session(async_client)
    url = f"ws://test/ws/pcm/{session_id}?token=test_token"

    async with async_client.websocket_connect(url) as websocket:
        # Send frame with 5 bytes (4 for index + 1 data byte) -> odd length
        await websocket.send_bytes(b'\x00\x00\x00\x00\x01')
        error_msg = await websocket.receive_json()
        assert error_msg["error"] == "Invalid PCM length"

# ----------------------------------------------------------------------
# Test: out-of-order frame index should be rejected
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_websocket_out_of_order(async_client):
    session_id = await create_dummy_session(async_client)
    url = f"ws://test/ws/pcm/{session_id}?token=test_token"

    async with async_client.websocket_connect(url) as websocket:
        # Send frame 0
        await websocket.send_bytes(pack_frame(0, [1]))
        # Expect ack
        ack = await websocket.receive_json()
        assert ack["frame_index"] == 0

        # Send frame 2 (out of order)
        await websocket.send_bytes(pack_frame(2, [2]))
        # Expect error JSON
        error_msg = await websocket.receive_json()
        assert error_msg["error"] == "Frame order violation"

# ----------------------------------------------------------------------
# Test: duplicate frame index should be rejected
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_websocket_duplicate_frame(async_client):
    session_id = await create_dummy_session(async_client)
    url = f"ws://test/ws/pcm/{session_id}?token=test_token"

    async with async_client.websocket_connect(url) as websocket:
        # Send frame 0
        await websocket.send_bytes(pack_frame(0, [1]))
        ack = await websocket.receive_json()
        assert ack["frame_index"] == 0

        # Send same frame 0 again (duplicate)
        await websocket.send_bytes(pack_frame(0, [2]))
        error_msg = await websocket.receive_json()
        assert error_msg["error"] == "Frame order violation"

# ----------------------------------------------------------------------
# Test: per-session isolation – two sessions must not interfere
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_websocket_per_session_isolation(async_client):
    # Create two sessions
    session_a = await create_dummy_session(async_client)
    session_b = await create_dummy_session(async_client)

    url_a = f"ws://test/ws/pcm/{session_a}?token=test_token"
    url_b = f"ws://test/ws/pcm/{session_b}?token=test_token"

    # Session A
    async with async_client.websocket_connect(url_a) as ws_a:
        await ws_a.send_bytes(pack_frame(0, [1]))
        ack_a = await ws_a.receive_json()
        assert ack_a["frame_index"] == 0

    # Session B
    async with async_client.websocket_connect(url_b) as ws_b:
        await ws_b.send_bytes(pack_frame(0, [2]))
        ack_b = await ws_b.receive_json()
        assert ack_b["frame_index"] == 0

    # Verify that the history buffers are independent
    buf_a = get_history_buffer(session_a)
    buf_b = get_history_buffer(session_b)
    assert len(buf_a._buffer) == 2  # one frame (2 bytes) + header? actually frame size 2 bytes per sample
    assert len(buf_b._buffer) == 2

# ----------------------------------------------------------------------
# Test: disconnect cleanup calls clear_utterance_buffer (skip for now)
# ----------------------------------------------------------------------
# The WebSocket connection is closed by the client; clear_utterance_buffer is invoked
# in the disconnect handler, which is exercised manually in integration testing.