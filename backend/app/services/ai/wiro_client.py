"""Generic Wiro.ai task runner — submit + poll + output fetch.

Wraps the lower-level HMAC auth helpers from ``llm_nlu_client`` so the
existing NLU integration's auth path is reused 1:1. Each AI service
(Qwen LLM, Whisper STT, CogVLM caption) calls ``run()`` with its own
multipart fields/files; this module handles submit/poll/output uniformly.

Why a separate module
    ``llm_nlu_client.NLUDirectClient`` is hard-coded for the legacy
    text-only NLU prompt shape (single ``prompt`` field, fixed
    extraction). The new AI services need:
      - arbitrary multipart fields (Whisper takes language/chunkLength/…)
      - file uploads (audio, video bytes)
      - polling-first design (no fallback HTTP providers, just Wiro)
      - output fetched from CDN URLs (transcripts, captions live in
        ``outputs[].url`` not in ``parameters``)
    Refactoring the existing NLU client to fit was higher risk than
    a parallel runner; both call the same ``_wiro_*`` HMAC helpers.

Public API
    submit(model, fields, files=None, *, client=None) -> (task_id, token)
    poll(task_id, timeout=30.0, *, client=None) -> WiroTaskResult
    run(model, fields, files=None, *, timeout=30.0) -> WiroTaskResult
    fetch_output_text(url, *, timeout=10.0) -> str
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

# Re-use the existing auth + status enums. They're prefixed with
# underscore in llm_nlu_client by convention, but the helpers are
# pure-functional and stable; treating them as semi-public here
# avoids duplicating the HMAC code path. Future cleanup: promote
# them to ``app.services.ai._wiro_auth`` and import from there.
from app.services.llm_nlu_client import (  # noqa: F401 — re-export
    _WIRO_ERROR,
    _WIRO_SUCCESS,
    _wiro_auth_headers,
    _wiro_base,
)

logger = logging.getLogger(__name__)


# ─── Result + error types ───────────────────────────────────────────


@dataclass
class WiroTaskResult:
    """Normalised view of a /Task/Detail tasklist[0] entry.

    ``raw`` keeps the full dict for debugging / cost analytics; the
    flat fields are convenience accessors for the common path.
    """

    task_id: str
    socket_token: str
    status: str
    parameters: dict[str, Any]
    outputs: list[dict[str, Any]]
    elapsed_seconds: float
    total_cost: float
    raw: dict[str, Any] = field(repr=False)


class WiroTaskError(Exception):
    """Raised when a Wiro task ends in a terminal error state
    (task_cancel / task_kill / task_error*) or when submit fails."""


class WiroTimeout(Exception):
    """Raised when polling exceeds the deadline without a terminal
    state. The task may still be running on Wiro's side — caller
    decides whether to cancel via /Task/Cancel."""


# ─── submit ──────────────────────────────────────────────────────────


def submit(
    model: str,
    fields: Optional[dict[str, Any]] = None,
    files: Optional[dict[str, tuple[str, bytes, str]]] = None,
    *,
    client: Optional[httpx.Client] = None,
) -> tuple[str, str]:
    """Submit a task. Returns ``(task_id, socket_token)``.

    Args:
        model: ``vendor/model-slug`` (e.g. ``"qwen/qwen3-6-27b"``)
        fields: multipart text fields. Values are cast to str.
        files: ``{name: (filename, content_bytes, content_type)}``.
            Use a real filename + MIME type — Wiro inspects them on
            the worker side for media-format detection.
        client: optional shared httpx client; one is created+closed
            per call when omitted.

    Raises:
        WiroTaskError when the response indicates submit failure.
        httpx.HTTPStatusError on non-2xx HTTP status.
    """
    url = f"{_wiro_base()}/v1/Run/{model}"
    headers = _wiro_auth_headers()
    multipart_files = files or {}
    # httpx multipart wants `data=` for plain fields and `files=` for
    # file uploads. Cast all field values to str so booleans / floats
    # don't blow up at the urllib3 layer.
    multipart_data = {
        k: ("" if v is None else str(v)) for k, v in (fields or {}).items()
    }

    own_client = client is None
    c = client or httpx.Client(timeout=httpx.Timeout(30.0), trust_env=False)
    try:
        resp = c.post(url, headers=headers, data=multipart_data, files=multipart_files)
        resp.raise_for_status()
        body = resp.json()
        if not body.get("result", False):
            raise WiroTaskError(
                f"submit returned result=false: errors={body.get('errors')!r}"
            )
        task_id = body.get("taskid")
        token = body.get("socketaccesstoken", "")
        if not task_id:
            raise WiroTaskError(f"submit missing taskid: {body}")
        return str(task_id), str(token)
    finally:
        if own_client:
            c.close()


# ─── poll ────────────────────────────────────────────────────────────


def poll(
    task_id: str,
    timeout: float = 30.0,
    interval: float = 0.5,
    *,
    client: Optional[httpx.Client] = None,
) -> WiroTaskResult:
    """Poll /Task/Detail until terminal state or timeout.

    Terminal states (per Wiro docs):
        success: task_postprocess_end / task_end
        error:   task_cancel / task_kill / task_error*

    Raises:
        WiroTimeout when ``timeout`` elapses without a terminal state.
        WiroTaskError on terminal error state.
        httpx.HTTPStatusError on non-2xx HTTP status from /Task/Detail.
    """
    url = f"{_wiro_base()}/v1/Task/Detail"
    deadline = time.monotonic() + timeout

    own_client = client is None
    c = client or httpx.Client(
        timeout=httpx.Timeout(min(timeout, 5.0)), trust_env=False
    )
    try:
        while True:
            resp = c.post(
                url,
                headers={
                    "Content-Type": "application/json",
                    **_wiro_auth_headers(),
                },
                json={"taskid": task_id},
            )
            resp.raise_for_status()
            body = resp.json()
            tasks = body.get("tasklist") or []
            if not tasks:
                raise WiroTaskError(
                    f"/Task/Detail returned empty tasklist for taskid={task_id}"
                )
            task = tasks[0]
            status = str(task.get("status", "")).lower()
            if status in _WIRO_SUCCESS:
                return _build_result(task)
            if status in _WIRO_ERROR:
                raise WiroTaskError(
                    f"task ended in error state: status={status}, "
                    f"debugerror={(task.get('debugerror') or '')[:200]!r}"
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise WiroTimeout(
                    f"poll timeout for taskid={task_id} (last status={status!r})"
                )
            time.sleep(min(interval, remaining))
    finally:
        if own_client:
            c.close()


# ─── run ─────────────────────────────────────────────────────────────


def run(
    model: str,
    fields: Optional[dict[str, Any]] = None,
    files: Optional[dict[str, tuple[str, bytes, str]]] = None,
    *,
    timeout: float = 30.0,
) -> WiroTaskResult:
    """Submit + poll in one call. Returns the terminal task result.

    Single shared httpx client across submit + poll keeps the TCP
    connection warm and saves the ~50-200 ms TLS handshake on the
    second request.
    """
    with httpx.Client(
        timeout=httpx.Timeout(min(timeout, 5.0)), trust_env=False
    ) as c:
        task_id, _token = submit(model, fields, files, client=c)
        return poll(task_id, timeout=timeout, client=c)


# ─── output fetch ────────────────────────────────────────────────────


def fetch_output_text(url: str, *, timeout: float = 10.0) -> str:
    """Download an output file's content as text.

    Used when the model's result lives in ``outputs[].url`` (e.g.
    Whisper transcript, CogVLM caption file) instead of inline in
    ``parameters``. Caller must already know the content is text —
    binary outputs (audio/video) won't decode cleanly.
    """
    with httpx.Client(
        timeout=httpx.Timeout(timeout), trust_env=False
    ) as c:
        resp = c.get(url)
        resp.raise_for_status()
        return resp.text


# ─── private helpers ─────────────────────────────────────────────────


def _build_result(task: dict[str, Any]) -> WiroTaskResult:
    """Normalise /Task/Detail tasklist[0] into a WiroTaskResult."""
    return WiroTaskResult(
        task_id=str(task.get("id", "")),
        socket_token=str(task.get("socketaccesstoken", "")),
        status=str(task.get("status", "")),
        parameters=task.get("parameters") or {},
        outputs=task.get("outputs") or [],
        elapsed_seconds=_safe_float(task.get("elapsedseconds")),
        total_cost=_safe_float(task.get("totalcost")),
        raw=task,
    )


def _safe_float(value: Any) -> float:
    """Wiro returns numeric fields as strings ("0.046841600000"); cast
    safely so consumers can do arithmetic on cost / elapsed time."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
