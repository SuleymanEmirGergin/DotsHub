"""Synchronous LLM client for NLU extraction.

Default provider: Wiro.ai  →  google/gemini-2-5-flash
  Submit:  POST https://api.wiro.ai/v1/Run/google/gemini-2-5-flash  (multipart)
  Poll:    POST https://api.wiro.ai/v1/Task/Detail                   (JSON)
  Auth:    HMAC-SHA256 signature — x-api-key + x-nonce + x-signature
           (signature = HMAC(key=API_KEY, msg=API_SECRET+NONCE) hex)

Design constraints (different from the async Wiro client in core/llm_client.py):
  - Fully synchronous  — triage_engine.py is sync
  - 3s hard deadline   — real-time NLU path
  - 0.3s poll interval — ~10 polls before timeout
  - thinkingBudget=0   — no extended thinking; faster for structured NLU
  - temperature=0      — deterministic extraction

Fallback providers (direct REST, no polling):
  - "google"    → Google Gemini OpenAI-compat endpoint
  - "openai"    → OpenAI Chat Completions
  - "anthropic" → Anthropic Messages API

PII is redacted from user text before any network call.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import time
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Terminal task statuses (mirrors core/llm_client.py)
# ---------------------------------------------------------------------------

_WIRO_SUCCESS = {"task_postprocess_end", "task_end"}
_WIRO_ERROR = {"task_error", "task_error_full", "task_cancel", "task_kill"}

# ---------------------------------------------------------------------------
# PII redaction — delegate to the canonical app.pii module so regexes
# can't drift between this client and the database / email / PDF paths.
# Retained as a local name so existing call sites (redact_pii(user))
# don't need to change.
# ---------------------------------------------------------------------------

from app.pii import redact_pii  # noqa: F401  (re-exported for module users)


# ---------------------------------------------------------------------------
# Wiro provider helpers
# ---------------------------------------------------------------------------

def _wiro_api_key() -> str:
    """Return the effective API key: LLM_API_KEY if set, else WIRO_API_KEY."""
    return settings.LLM_API_KEY or settings.WIRO_API_KEY


def _wiro_auth_headers() -> dict:
    """Build Wiro HMAC-signed auth headers per Wiro API docs.

    Signature scheme (https://wiro.ai/docs/introduction):
        signature = HMAC-SHA256(key=API_KEY, message=API_SECRET + NONCE)
        Headers: x-api-key, x-nonce (unix timestamp), x-signature (hex)

    The API_SECRET never travels over the wire — only the HMAC output does.
    Nonce gives replay-attack protection (Wiro rejects stale nonces).

    Falls back to the legacy x-api-secret header when no secret is
    configured (some Wiro projects still accept static auth); if
    signature auth is enforced on the project, this path returns 401.
    """
    key = _wiro_api_key()
    secret = getattr(settings, "WIRO_API_SECRET", "") or ""
    if not secret:
        # Legacy / single-credential mode (dev sandboxes).
        return {"x-api-key": key}

    nonce = str(int(time.time()))
    signature = hmac.new(
        key.encode("utf-8"),
        (secret + nonce).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        "x-api-key": key,
        "x-nonce": nonce,
        "x-signature": signature,
    }


def _wiro_base() -> str:
    return settings.WIRO_BASE_URL.rstrip("/")


def _build_wiro_prompt(system: str, user: str) -> str:
    """Merge system + user into Wiro's single prompt field."""
    return (
        f"System instructions:\n{system}\n\n"
        f"User input:\n{user}\n\n"
        "Return only a valid JSON object. Do not add markdown code fences."
    )


def _wiro_submit(client: httpx.Client, model: str, prompt: str) -> str:
    """Submit a task to Wiro. Returns socketaccesstoken."""
    url = f"{_wiro_base()}/v1/Run/{model}"
    fields = {
        "prompt":           (None, prompt),
        "thinkingBudget":   (None, "0"),      # disabled — faster for NLU
        "temperature":      (None, "0"),       # deterministic
        "topP":             (None, "0.95"),
        "maxOutputTokens":  (None, "512"),
    }
    resp = client.post(url, headers=_wiro_auth_headers(), files=fields)
    resp.raise_for_status()
    body = resp.json()
    if not body.get("result"):
        raise RuntimeError(f"Wiro submit failed: {body.get('errors')}")
    token = body.get("socketaccesstoken")
    if not token:
        raise RuntimeError(f"Wiro submit missing socketaccesstoken: {body}")
    return token


def _wiro_poll(client: httpx.Client, token: str, deadline: float) -> dict:
    """Poll until task is done or deadline exceeded. Returns task dict."""
    url = f"{_wiro_base()}/v1/Task/Detail"
    interval = settings.LLM_NLU_POLL_INTERVAL_SECONDS

    while True:
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Wiro task timed out after {settings.LLM_NLU_TIMEOUT_SECONDS}s"
            )

        resp = client.post(
            url,
            headers={"Content-Type": "application/json", **_wiro_auth_headers()},
            json={"tasktoken": token},
        )
        resp.raise_for_status()
        body = resp.json()

        tasks = body.get("tasklist") or []
        if not tasks:
            raise RuntimeError(f"Wiro task detail returned empty tasklist: {body}")

        task = tasks[0]
        status = str(task.get("status", "")).lower()

        if status in _WIRO_SUCCESS:
            return task
        if status in _WIRO_ERROR:
            raise RuntimeError(
                f"Wiro task failed: status={status}, "
                f"error={task.get('debugerror', '')[:200]}"
            )

        # Still running — wait and retry
        remaining = deadline - time.monotonic()
        sleep_for = min(interval, max(remaining, 0))
        if sleep_for > 0:
            time.sleep(sleep_for)


def _extract_wiro_text(task: dict) -> str:
    """Extract text output from completed Wiro task."""
    for field in ("debugoutput", "result", "response", "message"):
        value = task.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for output in task.get("outputs") or []:
        if not isinstance(output, dict):
            continue
        content_type = str(output.get("contenttype") or "").lower()
        if "text" in content_type or "json" in content_type:
            url = output.get("url")
            if url:
                try:
                    r = httpx.get(url, timeout=2.0)
                    r.raise_for_status()
                    text = r.text.strip()
                    if text:
                        return text
                except Exception as exc:
                    logger.warning("Failed to fetch Wiro output URL %s: %s", url, exc)

    raise RuntimeError(f"Wiro task completed but no text output found: {task}")


def _extract_wiro_usage(task: dict) -> tuple[int, int]:
    """
    Wiro doesn't expose token counts in the task detail response.
    Estimate from totalcost (cps = cost per second, not tokens).
    Returns (0, 0) — token tracking is best-effort for Wiro.
    """
    return 0, 0


# ---------------------------------------------------------------------------
# Direct REST provider helpers (google / openai / anthropic)
# ---------------------------------------------------------------------------

_GOOGLE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def _direct_call(
    client: httpx.Client,
    provider: str,
    model: str,
    system: str,
    user: str,
) -> tuple[str, int, int]:
    """Single-shot REST call for non-Wiro providers."""
    api_key = settings.LLM_API_KEY

    if provider == "anthropic":
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": model,
            "max_tokens": 512,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        resp = client.post(_ANTHROPIC_URL, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
        text = next(
            (b["text"] for b in (data.get("content") or []) if b.get("type") == "text"),
            "",
        )
        usage = data.get("usage") or {}
        return text, usage.get("input_tokens", 0), usage.get("output_tokens", 0)

    # google / openai — both use OpenAI-compat schema
    url = _GOOGLE_URL if provider == "google" else _OPENAI_URL
    headers = {"Authorization": f"Bearer {api_key}", "content-type": "application/json"}
    body = {
        "model": model,
        "max_tokens": 512,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    resp = client.post(url, headers=headers, json=body)
    resp.raise_for_status()
    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise ValueError(f"No choices in response: {data}")
    text = choices[0]["message"]["content"]
    usage = data.get("usage") or {}
    return text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


# ---------------------------------------------------------------------------
# NLUDirectClient
# ---------------------------------------------------------------------------


class NLUDirectClient:
    """Synchronous NLU client.

    Default: Wiro.ai → google/gemini-2-5-flash
      - submit task (multipart)
      - poll up to LLM_NLU_TIMEOUT_SECONDS at LLM_NLU_POLL_INTERVAL_SECONDS intervals
      - extract text from task output

    Fallback providers (LLM_PROVIDER=google|openai|anthropic):
      - single-shot REST call, same timeout

    PII redaction is applied to the user message before any call.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.provider = (provider or settings.LLM_PROVIDER).lower()
        self.model = model or settings.LLM_NLU_MODEL
        self.timeout = timeout if timeout is not None else settings.LLM_NLU_TIMEOUT_SECONDS
        # HTTP timeout per individual request (not the total deadline)
        self._client = httpx.Client(
            timeout=httpx.Timeout(min(self.timeout, 5.0)),
            trust_env=False,
        )

    def call(self, system: str, user: str) -> tuple[str, int, int]:
        """Run NLU call. Returns (response_text, input_tokens, output_tokens).

        PII redacted from `user` before transmission.
        Retries once on transient network errors (timeout / connect).
        """
        user_safe = redact_pii(user)
        last_exc: Optional[Exception] = None

        for attempt in range(2):
            try:
                return self._call_once(system, user_safe)
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exc = exc
                if attempt == 0:
                    logger.warning(
                        "NLU call attempt %d failed (%s), retrying once...",
                        attempt + 1, exc,
                    )
                    time.sleep(0.1)
            except httpx.HTTPStatusError:
                raise   # auth errors / 429 — don't retry
            except Exception:
                raise

        raise last_exc  # type: ignore[misc]

    def _call_once(self, system: str, user: str) -> tuple[str, int, int]:
        deadline = time.monotonic() + self.timeout

        if self.provider == "wiro":
            prompt = _build_wiro_prompt(system, user)
            token = _wiro_submit(self._client, self.model, prompt)
            task = _wiro_poll(self._client, token, deadline)
            text = _extract_wiro_text(task)
            in_tok, out_tok = _extract_wiro_usage(task)
        elif self.provider in ("google", "openai", "anthropic"):
            text, in_tok, out_tok = _direct_call(
                self._client, self.provider, self.model, system, user
            )
        else:
            raise ValueError(
                f"Unsupported LLM_PROVIDER: {self.provider!r}. "
                "Choose 'wiro', 'google', 'anthropic', or 'openai'."
            )

        return text, in_tok, out_tok

    def close(self) -> None:
        self._client.close()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_nlu_client: Optional[NLUDirectClient] = None


def get_nlu_client() -> NLUDirectClient:
    """Return the module-level NLUDirectClient singleton."""
    global _nlu_client
    if _nlu_client is None:
        _nlu_client = NLUDirectClient()
    return _nlu_client
