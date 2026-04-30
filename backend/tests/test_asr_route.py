"""Contract tests for POST /v1/asr/transcribe.

The Wiro client is mocked via monkeypatch — these tests assert the
route's contract (gating, validation, error mapping), not the
upstream provider behavior. The asr_client itself is exercised in
test_asr_client.py.
"""
from __future__ import annotations

import io

import httpx
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    """Build a TestClient with ASR enabled by default.

    Settings is loaded at import time, so we monkey-patch the attr on
    the singleton rather than relying on env mutation. Tests that
    need ASR disabled override LLM_ASR_ENABLED via the same shim.
    """
    from app.core.config import settings as _settings
    from app.api.routes import asr as asr_mod

    monkeypatch.setattr(_settings, "LLM_ASR_ENABLED", True, raising=False)
    monkeypatch.setattr(_settings, "LLM_ASR_MAX_BYTES", 10 * 1024 * 1024, raising=False)
    monkeypatch.setattr(
        _settings, "LLM_ASR_DAILY_LIMIT_PER_DEVICE", 50, raising=False
    )
    # Reset the per-device counter so prior tests don't bleed through.
    asr_mod._DEVICE_CALLS.clear()

    from app.main import app  # noqa: F401
    return TestClient(app)


def _wav_bytes(n: int = 1024) -> bytes:
    """Cheap fake audio payload — content is irrelevant to the route,
    only size + MIME matter (Wiro is mocked)."""
    return b"RIFF" + b"\0" * (n - 4)


def test_transcribe_returns_text_on_happy_path(client, monkeypatch):
    """Real client is replaced with a stub returning a fixed transcript."""
    captured = {}

    class _Stub:
        def transcribe(self, audio_bytes, filename, mime, language):
            captured["bytes_len"] = len(audio_bytes)
            captured["language"] = language
            return "karın ağrım var sabahtan beri"

    monkeypatch.setattr(
        "app.services.asr_client.get_asr_client", lambda: _Stub()
    )

    files = {"audio": ("clip.m4a", _wav_bytes(2048), "audio/m4a")}
    data = {"device_id": "dev-1", "language": "Turkish"}
    r = client.post("/v1/asr/transcribe", files=files, data=data)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["transcript"] == "karın ağrım var sabahtan beri"
    assert body["remaining_today"] >= 0
    assert captured["bytes_len"] == 2048
    assert captured["language"] == "Turkish"


def test_disabled_returns_403(client, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "LLM_ASR_ENABLED", False, raising=False)
    files = {"audio": ("clip.m4a", _wav_bytes(), "audio/m4a")}
    r = client.post(
        "/v1/asr/transcribe", files=files, data={"device_id": "dev-1"}
    )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "ASR_DISABLED"


def test_unsupported_media_returns_415(client):
    """A text/plain upload should be rejected before any provider call."""
    files = {"audio": ("clip.txt", b"not audio", "text/plain")}
    r = client.post(
        "/v1/asr/transcribe", files=files, data={"device_id": "dev-1"}
    )
    assert r.status_code == 415
    assert r.json()["detail"]["code"] == "UNSUPPORTED_MEDIA"


def test_oversize_returns_413(client, monkeypatch):
    """Cap is configurable; lower it for the test so we don't move
    multi-megabyte payloads through the test client."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "LLM_ASR_MAX_BYTES", 1024, raising=False)
    files = {"audio": ("clip.m4a", _wav_bytes(2048), "audio/m4a")}
    r = client.post(
        "/v1/asr/transcribe", files=files, data={"device_id": "dev-1"}
    )
    assert r.status_code == 413
    assert r.json()["detail"]["code"] == "AUDIO_TOO_LARGE"


def test_empty_audio_returns_400(client):
    files = {"audio": ("clip.m4a", b"", "audio/m4a")}
    r = client.post(
        "/v1/asr/transcribe", files=files, data={"device_id": "dev-1"}
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "EMPTY_AUDIO"


def test_provider_timeout_returns_504(client, monkeypatch):
    class _Stub:
        def transcribe(self, *a, **kw):
            raise TimeoutError("Wiro ASR task timed out after 30s")

    monkeypatch.setattr(
        "app.services.asr_client.get_asr_client", lambda: _Stub()
    )
    files = {"audio": ("clip.m4a", _wav_bytes(), "audio/m4a")}
    r = client.post(
        "/v1/asr/transcribe", files=files, data={"device_id": "dev-1"}
    )
    assert r.status_code == 504
    assert r.json()["detail"]["code"] == "ASR_TIMEOUT"


def test_provider_http_error_returns_502(client, monkeypatch):
    class _Stub:
        def transcribe(self, *a, **kw):
            req = httpx.Request("POST", "https://api.wiro.ai/x")
            resp = httpx.Response(401, text="unauthorized", request=req)
            raise httpx.HTTPStatusError("401", request=req, response=resp)

    monkeypatch.setattr(
        "app.services.asr_client.get_asr_client", lambda: _Stub()
    )
    files = {"audio": ("clip.m4a", _wav_bytes(), "audio/m4a")}
    r = client.post(
        "/v1/asr/transcribe", files=files, data={"device_id": "dev-1"}
    )
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "ASR_PROVIDER_ERROR"


def test_per_device_daily_limit(client, monkeypatch):
    """Set the cap to 2 calls/day; the 3rd call from the same
    device should 429, while a different device still passes."""
    from app.core.config import settings
    monkeypatch.setattr(
        settings, "LLM_ASR_DAILY_LIMIT_PER_DEVICE", 2, raising=False
    )

    class _Stub:
        def transcribe(self, *a, **kw):
            return "ok"

    monkeypatch.setattr(
        "app.services.asr_client.get_asr_client", lambda: _Stub()
    )
    # Reset the module-level counter so prior tests don't leak into
    # this assertion.
    from app.api.routes import asr as asr_mod
    asr_mod._DEVICE_CALLS.clear()

    files = lambda: {"audio": ("c.m4a", _wav_bytes(), "audio/m4a")}
    data_a = {"device_id": "dev-A"}
    data_b = {"device_id": "dev-B"}

    assert client.post("/v1/asr/transcribe", files=files(), data=data_a).status_code == 200
    assert client.post("/v1/asr/transcribe", files=files(), data=data_a).status_code == 200
    r3 = client.post("/v1/asr/transcribe", files=files(), data=data_a)
    assert r3.status_code == 429
    assert r3.json()["detail"]["code"] == "ASR_DAILY_LIMIT"
    # Different device still has its own quota
    assert client.post("/v1/asr/transcribe", files=files(), data=data_b).status_code == 200
