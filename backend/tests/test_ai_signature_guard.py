"""require_signature_auth() — fail-loud guard for app.services.ai.*.

The legacy llm_nlu_client integration tolerates an API-key-only auth
mode for older Wiro projects. The new AI services (qwen/whisper/
cogvlm/gemini/moondream) all run on Wiro's signature-auth model
surface; submitting without WIRO_API_SECRET returns a confusing 401
buried in retry logs. This guard turns that into a clear local
WiroAuthError at the top of submit().
"""
from __future__ import annotations

import pytest

from app.services.ai import wiro_client


def test_require_signature_auth_passes_with_secret(monkeypatch):
    monkeypatch.setenv("WIRO_API_SECRET", "any-non-empty")
    # Reload settings so the new env value is picked up.
    from app.core import config as cfg
    cfg.settings.WIRO_API_SECRET = "any-non-empty"
    # Should not raise.
    wiro_client.require_signature_auth()


def test_require_signature_auth_raises_when_secret_blank(monkeypatch):
    from app.core import config as cfg
    monkeypatch.setattr(cfg.settings, "WIRO_API_SECRET", "")
    with pytest.raises(wiro_client.WiroAuthError) as exc:
        wiro_client.require_signature_auth()
    # Error message should hint at the fix (set WIRO_API_SECRET).
    assert "WIRO_API_SECRET" in str(exc.value)


def test_submit_raises_wiro_auth_error_when_secret_blank(monkeypatch):
    """End-to-end: submit() inherits the guard. A test caller with no
    secret hits the auth error immediately, before any HTTP traffic."""
    from app.core import config as cfg
    monkeypatch.setattr(cfg.settings, "WIRO_API_SECRET", "")
    with pytest.raises(wiro_client.WiroAuthError):
        wiro_client.submit("test/model", fields={"prompt": "x"})


def test_qwen_returns_none_when_secret_blank(monkeypatch):
    """Service wrappers MUST surface auth errors as None — the same
    shape as feature-flag-off — so caller's branching stays simple."""
    from app.core import config as cfg
    from app.services.ai import qwen_llm

    monkeypatch.setattr(cfg.settings, "WIRO_API_SECRET", "")
    monkeypatch.setattr(cfg.settings, "WIRO_QWEN_LLM_ENABLED", True)

    out = qwen_llm.generate(prompt="hello world")
    assert out is None


def test_whisper_returns_none_when_secret_blank(monkeypatch):
    from app.core import config as cfg
    from app.services.ai import whisper_stt

    monkeypatch.setattr(cfg.settings, "WIRO_API_SECRET", "")
    monkeypatch.setattr(cfg.settings, "WIRO_WHISPER_STT_ENABLED", True)

    out = whisper_stt.transcribe(
        audio_bytes=b"\x00\x01", language="Turkish"
    )
    assert out is None


def test_cogvlm_returns_none_when_secret_blank(monkeypatch):
    from app.core import config as cfg
    from app.services.ai import cogvlm_caption

    monkeypatch.setattr(cfg.settings, "WIRO_API_SECRET", "")
    monkeypatch.setattr(cfg.settings, "WIRO_COGVLM_CAPTION_ENABLED", True)

    out = cogvlm_caption.caption(video_bytes=b"\x00")
    assert out is None
