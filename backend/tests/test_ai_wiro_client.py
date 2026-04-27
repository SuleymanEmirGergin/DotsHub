"""Tests for the generic Wiro task runner.

Covers submit, poll (success / error / timeout), run, and
fetch_output_text. All HTTP egress is mocked via httpx.MockTransport
so we never hit api.wiro.ai during CI.

The auth helpers are imported from llm_nlu_client and tested there;
this file focuses on the new client's correctness.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

from app.services.ai import wiro_client


# ─── Mock transport helpers ─────────────────────────────────────────


def _ok(status_code: int = 200, body: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status_code,
        content=json.dumps(body or {}).encode("utf-8"),
        headers={"content-type": "application/json"},
    )


def _text(status_code: int = 200, body: str = "") -> httpx.Response:
    return httpx.Response(
        status_code, content=body.encode("utf-8"), headers={"content-type": "text/plain"}
    )


def _make_client(handler) -> httpx.Client:
    """Build an httpx.Client whose every request goes through ``handler``.

    The handler receives the raw httpx.Request and returns an
    httpx.Response. Lets each test specify exactly how submit / poll /
    fetch should answer without monkey-patching internals.
    """
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


# ─── submit ──────────────────────────────────────────────────────────


def test_submit_returns_taskid_and_token():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/v1/Run/test/model" in str(request.url)
        return _ok(body={"result": True, "taskid": "T1", "socketaccesstoken": "TKN"})

    with _make_client(handler) as c:
        task_id, token = wiro_client.submit(
            "test/model", fields={"prompt": "hi"}, client=c
        )
    assert task_id == "T1"
    assert token == "TKN"


def test_submit_raises_when_result_false():
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok(body={"result": False, "errors": [{"code": 1, "message": "bad"}]})

    with _make_client(handler) as c, pytest.raises(wiro_client.WiroTaskError):
        wiro_client.submit("test/model", fields={"prompt": "x"}, client=c)


def test_submit_raises_when_taskid_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok(body={"result": True})  # no taskid

    with _make_client(handler) as c, pytest.raises(wiro_client.WiroTaskError):
        wiro_client.submit("test/model", fields={}, client=c)


def test_submit_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok(401, body={"error": "unauthorized"})

    with _make_client(handler) as c, pytest.raises(httpx.HTTPStatusError):
        wiro_client.submit("test/model", fields={}, client=c)


# ─── poll ────────────────────────────────────────────────────────────


def test_poll_returns_result_on_terminal_success():
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok(body={
            "tasklist": [{
                "id": "T1",
                "socketaccesstoken": "TKN",
                "status": "task_postprocess_end",
                "parameters": {"output": "hello"},
                "outputs": [],
                "elapsedseconds": "1.5",
                "totalcost": "0.001",
            }],
            "result": True,
        })

    with _make_client(handler) as c:
        result = wiro_client.poll("T1", timeout=5.0, client=c)
    assert result.task_id == "T1"
    assert result.status == "task_postprocess_end"
    assert result.parameters["output"] == "hello"
    assert result.elapsed_seconds == 1.5


def test_poll_raises_on_terminal_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok(body={
            "tasklist": [{
                "id": "T1",
                "status": "task_cancel",
                "debugerror": "user cancelled",
            }],
            "result": True,
        })

    with _make_client(handler) as c, pytest.raises(wiro_client.WiroTaskError) as exc:
        wiro_client.poll("T1", timeout=5.0, client=c)
    assert "task_cancel" in str(exc.value)


def test_poll_raises_timeout_when_status_stays_running():
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok(body={
            "tasklist": [{"id": "T1", "status": "task_queue"}],
            "result": True,
        })

    with _make_client(handler) as c, pytest.raises(wiro_client.WiroTimeout):
        # Sub-second timeout so the test runs fast — interval defaults
        # to 0.5s, so 0.2s is enough to expire on the first iteration.
        wiro_client.poll("T1", timeout=0.2, interval=0.05, client=c)


def test_poll_raises_when_tasklist_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok(body={"tasklist": [], "result": True})

    with _make_client(handler) as c, pytest.raises(wiro_client.WiroTaskError):
        wiro_client.poll("missing", timeout=5.0, client=c)


def test_poll_normalises_string_numeric_fields():
    """Wiro returns elapsedseconds/totalcost as strings — the result
    must expose them as floats so callers can do arithmetic."""
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok(body={
            "tasklist": [{
                "id": "T1",
                "status": "task_postprocess_end",
                "elapsedseconds": "0.046841600000",
                "totalcost": "0.046841600000",
            }],
            "result": True,
        })

    with _make_client(handler) as c:
        result = wiro_client.poll("T1", timeout=5.0, client=c)
    assert isinstance(result.elapsed_seconds, float)
    assert isinstance(result.total_cost, float)


def test_poll_safe_floats_handle_garbage():
    """A malformed totalcost shouldn't crash the result builder."""
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok(body={
            "tasklist": [{
                "id": "T1",
                "status": "task_postprocess_end",
                "elapsedseconds": None,
                "totalcost": "not-a-number",
            }],
            "result": True,
        })

    with _make_client(handler) as c:
        result = wiro_client.poll("T1", timeout=5.0, client=c)
    assert result.elapsed_seconds == 0.0
    assert result.total_cost == 0.0


# ─── run (submit + poll combined) ───────────────────────────────────


def test_run_submits_then_polls_to_terminal_state():
    seq = iter([
        # 1. submit response
        _ok(body={"result": True, "taskid": "T9", "socketaccesstoken": "TK"}),
        # 2. first poll: still running
        _ok(body={
            "tasklist": [{"id": "T9", "status": "task_start"}],
            "result": True,
        }),
        # 3. second poll: terminal success
        _ok(body={
            "tasklist": [{
                "id": "T9",
                "status": "task_postprocess_end",
                "parameters": {"output": "done"},
                "outputs": [],
            }],
            "result": True,
        }),
    ])

    def handler(request: httpx.Request) -> httpx.Response:
        return next(seq)

    transport = httpx.MockTransport(handler)
    # wiro_client builds its own httpx.Client inside run(); we
    # short-circuit by patching the constructor to drop in our mock
    # transport. Strip kwargs that conflict with `transport=`.
    real_client_cls = httpx.Client

    def _patched_client(**kwargs):
        kwargs.pop("trust_env", None)
        kwargs.pop("transport", None)
        return real_client_cls(transport=transport, **kwargs)

    with patch.object(httpx, "Client", _patched_client):
        result = wiro_client.run(
            "test/model",
            fields={"prompt": "x"},
            timeout=5.0,
        )
    assert result.task_id == "T9"
    assert result.parameters["output"] == "done"


# ─── fetch_output_text ──────────────────────────────────────────────


def _client_factory(transport):
    """Build the patched httpx.Client constructor used in MockTransport
    tests. Captures the real Client class BEFORE the patch installs
    so the wrapper doesn't recurse into itself."""
    real_client_cls = httpx.Client

    def _wrap(**kwargs):
        kwargs.pop("trust_env", None)
        kwargs.pop("transport", None)
        return real_client_cls(transport=transport, **kwargs)
    return _wrap


def test_fetch_output_text_returns_response_body():
    def handler(request: httpx.Request) -> httpx.Response:
        return _text(200, body="transcript text\nline two")

    transport = httpx.MockTransport(handler)
    with patch.object(httpx, "Client", _client_factory(transport)):
        out = wiro_client.fetch_output_text("https://cdn.wiro.ai/some/file.txt")
    assert out == "transcript text\nline two"


def test_fetch_output_text_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return _text(404, body="not found")

    transport = httpx.MockTransport(handler)
    with patch.object(httpx, "Client", _client_factory(transport)), pytest.raises(
        httpx.HTTPStatusError
    ):
        wiro_client.fetch_output_text("https://cdn.wiro.ai/missing.txt")
