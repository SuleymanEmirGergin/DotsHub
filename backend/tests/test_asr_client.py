"""Unit tests for app/services/asr_client.py.

We mock httpx.Client at the boundary — these tests assert:
  - submit posts the right multipart fields and auth header
  - poll loops until terminal status, then returns the task
  - poll raises TimeoutError past the deadline
  - extract_transcript handles both inline + outputs[].url shapes
  - extract handles the JSON {"text": "..."} response shape
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import httpx
import pytest


def _stub_client_with_responses(*responses):
    """Build a MagicMock httpx.Client where successive .post() calls
    return the provided httpx.Response objects in order."""
    cli = MagicMock(spec=httpx.Client)
    cli.post.side_effect = list(responses)
    return cli


def _resp(status: int, json_body: dict) -> httpx.Response:
    return httpx.Response(
        status,
        json=json_body,
        request=httpx.Request("POST", "https://api.wiro.ai/v1/x"),
    )


def test_submit_sends_required_fields(monkeypatch):
    from app.services import asr_client as mod

    # Settings is import-time; patch the attribute directly so env
    # mutations don't need a re-import.
    monkeypatch.setattr(mod.settings, "WIRO_API_KEY", "k1", raising=False)
    monkeypatch.setattr(mod.settings, "LLM_API_KEY", "", raising=False)
    cli = _stub_client_with_responses(
        _resp(200, {"result": True, "socketaccesstoken": "tok-XYZ"})
    )

    token = mod._submit(
        cli, "openai/whisper-large-v3-turbo-turkish",
        b"FAKEAUDIO", "clip.m4a", "audio/m4a", "Turkish",
    )
    assert token == "tok-XYZ"

    # Inspect the multipart fields we sent.
    _, kwargs = cli.post.call_args
    files = kwargs["files"]
    assert files["language"] == (None, "Turkish")
    assert files["chunkLength"] == (None, "30")
    assert files["batchSize"] == (None, "1")
    assert files["numSpeakers"] == (None, "1")
    assert files["inputAudio"][0] == "clip.m4a"
    assert files["inputAudio"][1] == b"FAKEAUDIO"
    assert files["inputAudio"][2] == "audio/m4a"
    # Auth header
    assert kwargs["headers"]["x-api-key"] == "k1"


def test_submit_raises_on_result_false(monkeypatch):
    from app.services import asr_client as mod
    monkeypatch.setattr(mod.settings, "WIRO_API_KEY", "k1", raising=False)
    monkeypatch.setattr(mod.settings, "LLM_API_KEY", "", raising=False)

    cli = _stub_client_with_responses(
        _resp(200, {"result": False, "errors": [{"message": "quota"}]})
    )
    with pytest.raises(RuntimeError, match="submit failed"):
        mod._submit(cli, "m", b"x", "f.m4a", "audio/m4a")


def test_poll_returns_task_on_success(monkeypatch):
    from app.services import asr_client as mod
    monkeypatch.setattr(mod.settings, "WIRO_API_KEY", "k1", raising=False)
    monkeypatch.setattr(mod.settings, "LLM_API_KEY", "", raising=False)
    monkeypatch.setattr(
        mod.settings, "LLM_ASR_POLL_INTERVAL_SECONDS", 0.0
    )

    # First poll: still running. Second: done.
    cli = _stub_client_with_responses(
        _resp(200, {"tasklist": [{"status": "task_start"}]}),
        _resp(200, {"tasklist": [{"status": "task_postprocess_end",
                                  "outputs": [{"url": "https://cdn/x.txt",
                                               "contenttype": "text/plain"}]}]}),
    )

    deadline = time.monotonic() + 5.0
    task = mod._poll(cli, "tok", deadline)
    assert task["status"] == "task_postprocess_end"


def test_poll_raises_on_terminal_error(monkeypatch):
    from app.services import asr_client as mod
    monkeypatch.setattr(mod.settings, "WIRO_API_KEY", "k1", raising=False)
    monkeypatch.setattr(mod.settings, "LLM_API_KEY", "", raising=False)
    monkeypatch.setattr(mod.settings, "LLM_ASR_POLL_INTERVAL_SECONDS", 0.0)

    cli = _stub_client_with_responses(
        _resp(200, {"tasklist": [{"status": "task_error",
                                  "debugerror": "OOM"}]}),
    )
    with pytest.raises(RuntimeError, match="task failed"):
        mod._poll(cli, "tok", time.monotonic() + 5.0)


def test_poll_raises_on_deadline(monkeypatch):
    from app.services import asr_client as mod
    monkeypatch.setattr(mod.settings, "WIRO_API_KEY", "k1", raising=False)
    monkeypatch.setattr(mod.settings, "LLM_API_KEY", "", raising=False)

    cli = MagicMock(spec=httpx.Client)
    # Deadline already in the past — first iteration should raise.
    with pytest.raises(TimeoutError):
        mod._poll(cli, "tok", time.monotonic() - 1.0)


def test_extract_transcript_from_outputs_url_text():
    from app.services import asr_client as mod

    cli = MagicMock(spec=httpx.Client)
    cli.get.return_value = httpx.Response(
        200, text="merhaba dünya",
        request=httpx.Request("GET", "https://cdn/x.txt"),
    )
    task = {
        "outputs": [{"url": "https://cdn/x.txt", "contenttype": "text/plain"}],
    }
    text = mod._extract_transcript(cli, task)
    assert text == "merhaba dünya"


def test_extract_transcript_from_outputs_url_json():
    from app.services import asr_client as mod

    cli = MagicMock(spec=httpx.Client)
    cli.get.return_value = httpx.Response(
        200, json={"text": "karın ağrım var", "language": "tr"},
        request=httpx.Request("GET", "https://cdn/x.json"),
    )
    task = {
        "outputs": [{"url": "https://cdn/x.json", "contenttype": "application/json"}],
    }
    text = mod._extract_transcript(cli, task)
    assert text == "karın ağrım var"


def test_extract_transcript_raises_when_no_output():
    from app.services import asr_client as mod
    cli = MagicMock(spec=httpx.Client)
    with pytest.raises(RuntimeError, match="no transcript"):
        mod._extract_transcript(cli, {"outputs": []})
