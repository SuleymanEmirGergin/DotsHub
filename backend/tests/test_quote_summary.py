"""Tests for the LLM-generated quote summary service.

Covers two layers:

1. ``quote_summary`` module unit tests — provider chain, cache,
   disabled gates, PII redaction, observability hooks. Each provider's
   ``generate`` is mocked at the wrapper boundary so no Wiro traffic.

2. /v1/quote integration — the route handler should:
   a. Return ``summary_tr=None`` when the feature flag is off.
   b. Return ``summary_tr=None`` on cache miss (with the flag on),
      AND schedule a background task to populate the cache.
   c. Return the cached value on cache hit.
"""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.services import quote_summary


# ─── Unit tests ─────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_cache():
    """Module-level cache is process-global; clear before each test."""
    quote_summary._cache_clear()
    yield
    quote_summary._cache_clear()


def _enable(monkeypatch, *, providers: str = "qwen,gpt5_mini"):
    """Tiny helper — flip the feature flag + provider chain."""
    monkeypatch.setattr(
        quote_summary.settings, "QUOTE_SUMMARY_LLM_ENABLED", True
    )
    monkeypatch.setattr(
        quote_summary.settings, "QUOTE_SUMMARY_LLM_PROVIDERS", providers
    )


_FIXED_INPUTS = dict(
    procedure_id="fue_hair_transplant",
    procedure_name_tr="Saç Ekimi",
    complexity="medium",
    duration_days=2,
    top_clinic_id="ist_clinic_001",
    clinic_name="Test Clinic",
    clinic_city="Istanbul",
    price_amount=2500,
    price_currency="EUR",
    locale="tr",
)

_LOOKUP_INPUTS = dict(
    procedure_id="fue_hair_transplant",
    top_clinic_id="ist_clinic_001",
    locale="tr",
)


def test_disabled_lookup_returns_none(monkeypatch):
    monkeypatch.setattr(
        quote_summary.settings, "QUOTE_SUMMARY_LLM_ENABLED", False
    )
    assert quote_summary.lookup_cached(**_LOOKUP_INPUTS) is None


def test_disabled_generate_returns_none(monkeypatch):
    monkeypatch.setattr(
        quote_summary.settings, "QUOTE_SUMMARY_LLM_ENABLED", False
    )
    # If the chain is even traversed, this would fire — assert not called.
    with patch.object(
        quote_summary.qwen_llm, "generate",
        side_effect=AssertionError("must not be called when disabled"),
    ):
        assert quote_summary.generate_and_cache(**_FIXED_INPUTS) is None


def test_lookup_cache_miss(monkeypatch):
    _enable(monkeypatch)
    assert quote_summary.lookup_cached(**_LOOKUP_INPUTS) is None


def test_generate_caches_and_lookup_hits_after(monkeypatch):
    _enable(monkeypatch)
    with patch.object(
        quote_summary.qwen_llm, "is_enabled", return_value=True,
    ), patch.object(
        quote_summary.qwen_llm, "generate", return_value="generated blurb",
    ):
        out = quote_summary.generate_and_cache(**_FIXED_INPUTS)
    assert out == "generated blurb"
    assert quote_summary.lookup_cached(**_LOOKUP_INPUTS) == "generated blurb"


def test_qwen_fail_fallback_gpt5_mini(monkeypatch):
    _enable(monkeypatch)
    with patch.object(
        quote_summary.qwen_llm, "is_enabled", return_value=True,
    ), patch.object(
        quote_summary.qwen_llm, "generate", return_value=None,
    ), patch.object(
        quote_summary.gpt5_mini_llm, "is_enabled", return_value=True,
    ), patch.object(
        quote_summary.gpt5_mini_llm, "generate", return_value="from gpt5",
    ):
        out = quote_summary.generate_and_cache(**_FIXED_INPUTS)
    assert out == "from gpt5"


def test_disabled_provider_in_chain_skipped(monkeypatch):
    """Qwen disabled → chain advances to gpt5_mini without crashing."""
    _enable(monkeypatch)
    qwen_called = []
    with patch.object(
        quote_summary.qwen_llm, "is_enabled", return_value=False,
    ), patch.object(
        quote_summary.qwen_llm,
        "generate",
        side_effect=lambda **_: qwen_called.append(1),
    ), patch.object(
        quote_summary.gpt5_mini_llm, "is_enabled", return_value=True,
    ), patch.object(
        quote_summary.gpt5_mini_llm, "generate", return_value="from gpt5",
    ):
        out = quote_summary.generate_and_cache(**_FIXED_INPUTS)
    assert out == "from gpt5"
    assert qwen_called == []  # disabled provider must not be called


def test_all_fail_returns_none_no_cache_write(monkeypatch):
    _enable(monkeypatch)
    with patch.object(
        quote_summary.qwen_llm, "is_enabled", return_value=True,
    ), patch.object(
        quote_summary.qwen_llm, "generate", return_value=None,
    ), patch.object(
        quote_summary.gpt5_mini_llm, "is_enabled", return_value=True,
    ), patch.object(
        quote_summary.gpt5_mini_llm, "generate", return_value=None,
    ):
        assert quote_summary.generate_and_cache(**_FIXED_INPUTS) is None
    # Cache must NOT contain a sentinel for failure — next request retries.
    assert quote_summary.lookup_cached(**_LOOKUP_INPUTS) is None


def test_provider_exception_advances_chain(monkeypatch):
    """An exception in one provider must not prevent the next from running."""
    _enable(monkeypatch)
    with patch.object(
        quote_summary.qwen_llm, "is_enabled", return_value=True,
    ), patch.object(
        quote_summary.qwen_llm, "generate", side_effect=RuntimeError("boom"),
    ), patch.object(
        quote_summary.gpt5_mini_llm, "is_enabled", return_value=True,
    ), patch.object(
        quote_summary.gpt5_mini_llm, "generate", return_value="recovered",
    ):
        out = quote_summary.generate_and_cache(**_FIXED_INPUTS)
    assert out == "recovered"


def test_default_provider_chain_includes_gemini():
    """Tripwire: production default chain MUST include gemini between
    qwen and gpt5_mini. If someone reorders or drops gemini without
    thinking, this test fails — surfacing it in code review.

    Reads from settings without monkeypatching, so it observes the
    real default. The conftest stub doesn't override
    QUOTE_SUMMARY_LLM_PROVIDERS, so settings.X here is the
    production default."""
    chain = quote_summary._provider_chain()
    assert chain == ["qwen", "gemini", "gpt5_mini"], (
        f"default chain drift: got {chain}; "
        "expected ['qwen', 'gemini', 'gpt5_mini']"
    )


def test_gemini_dispatched_when_qwen_disabled_in_default_chain(monkeypatch):
    """End-to-end: with the real default chain, qwen disabled but
    gemini enabled → gemini dispatched, gpt5_mini NOT touched."""
    monkeypatch.setattr(
        quote_summary.settings, "QUOTE_SUMMARY_LLM_ENABLED", True
    )
    # Don't override QUOTE_SUMMARY_LLM_PROVIDERS — use the prod default.
    gpt5_called = []
    with patch.object(
        quote_summary.qwen_llm, "is_enabled", return_value=False,
    ), patch.object(
        quote_summary.gemini_llm, "is_enabled", return_value=True,
    ), patch.object(
        quote_summary.gemini_llm, "generate", return_value="from gemini",
    ), patch.object(
        quote_summary.gpt5_mini_llm, "is_enabled", return_value=True,
    ), patch.object(
        quote_summary.gpt5_mini_llm,
        "generate",
        side_effect=lambda **_: gpt5_called.append(1) or "ignored",
    ):
        out = quote_summary.generate_and_cache(**_FIXED_INPUTS)
    assert out == "from gemini"
    assert gpt5_called == []  # default chain stops at gemini


def test_unknown_provider_skipped(monkeypatch):
    """Typo in env (``QUOTE_SUMMARY_LLM_PROVIDERS=xxxx,qwen``) must
    skip the unknown name and proceed."""
    _enable(monkeypatch, providers="bogus_provider,qwen")
    with patch.object(
        quote_summary.qwen_llm, "is_enabled", return_value=True,
    ), patch.object(
        quote_summary.qwen_llm, "generate", return_value="ok",
    ):
        out = quote_summary.generate_and_cache(**_FIXED_INPUTS)
    assert out == "ok"


def test_cache_hit_skips_provider_call(monkeypatch):
    """Second call with same inputs must NOT re-invoke the provider."""
    _enable(monkeypatch)
    with patch.object(
        quote_summary.qwen_llm, "is_enabled", return_value=True,
    ), patch.object(
        quote_summary.qwen_llm, "generate", return_value="cached blurb",
    ) as mock_gen:
        quote_summary.generate_and_cache(**_FIXED_INPUTS)
        quote_summary.generate_and_cache(**_FIXED_INPUTS)
    assert mock_gen.call_count == 1


def test_cache_ttl_expires(monkeypatch):
    """Stale entry past TTL must be dropped, forcing regeneration."""
    _enable(monkeypatch)
    monkeypatch.setattr(
        quote_summary.settings, "QUOTE_SUMMARY_CACHE_TTL_SECONDS", 0.05
    )
    with patch.object(
        quote_summary.qwen_llm, "is_enabled", return_value=True,
    ), patch.object(
        quote_summary.qwen_llm, "generate", return_value="v1",
    ) as mock_gen:
        quote_summary.generate_and_cache(**_FIXED_INPUTS)
        time.sleep(0.06)
        # TTL expired; second call regenerates instead of hitting cache.
        quote_summary.generate_and_cache(**_FIXED_INPUTS)
    assert mock_gen.call_count == 2


def test_cache_lru_eviction_oldest(monkeypatch):
    """Cap at 2 entries; third insert evicts the oldest."""
    _enable(monkeypatch)
    monkeypatch.setattr(
        quote_summary.settings, "QUOTE_SUMMARY_CACHE_MAX_ENTRIES", 2
    )
    with patch.object(
        quote_summary.qwen_llm, "is_enabled", return_value=True,
    ), patch.object(
        quote_summary.qwen_llm, "generate",
        side_effect=lambda **kw: f"blurb-{kw['prompt'][-3:]}",
    ):
        quote_summary.generate_and_cache(
            **{**_FIXED_INPUTS, "top_clinic_id": "AAA"}
        )
        quote_summary.generate_and_cache(
            **{**_FIXED_INPUTS, "top_clinic_id": "BBB"}
        )
        quote_summary.generate_and_cache(
            **{**_FIXED_INPUTS, "top_clinic_id": "CCC"}
        )
    # AAA evicted (oldest); BBB + CCC retained.
    assert quote_summary.lookup_cached(
        **{**_LOOKUP_INPUTS, "top_clinic_id": "AAA"}
    ) is None
    assert quote_summary.lookup_cached(
        **{**_LOOKUP_INPUTS, "top_clinic_id": "BBB"}
    ) is not None
    assert quote_summary.lookup_cached(
        **{**_LOOKUP_INPUTS, "top_clinic_id": "CCC"}
    ) is not None


def test_pii_redacted_in_prompt(monkeypatch):
    """If a clinic name leaks contact info, it must not be sent verbatim."""
    _enable(monkeypatch)
    captured = {}

    def _capture(**kwargs):
        captured["prompt"] = kwargs.get("prompt", "")
        return "ok"

    with patch.object(
        quote_summary.qwen_llm, "is_enabled", return_value=True,
    ), patch.object(
        quote_summary.qwen_llm, "generate", side_effect=_capture,
    ):
        quote_summary.generate_and_cache(
            **{
                **_FIXED_INPUTS,
                "clinic_name": "Acme (info@example.com / +90 555 123 45 67)",
            }
        )

    assert "info@example.com" not in captured["prompt"]
    assert "+90 555 123 45 67" not in captured["prompt"]


def test_locale_changes_cache_key(monkeypatch):
    """Same procedure + clinic but different locale → separate entry."""
    _enable(monkeypatch)
    with patch.object(
        quote_summary.qwen_llm, "is_enabled", return_value=True,
    ), patch.object(
        quote_summary.qwen_llm, "generate",
        side_effect=lambda prompt, **_: f"blurb for {prompt[-30:]}",
    ):
        quote_summary.generate_and_cache(**{**_FIXED_INPUTS, "locale": "tr"})
        quote_summary.generate_and_cache(**{**_FIXED_INPUTS, "locale": "en"})

    tr = quote_summary.lookup_cached(**{**_LOOKUP_INPUTS, "locale": "tr"})
    en = quote_summary.lookup_cached(**{**_LOOKUP_INPUTS, "locale": "en"})
    assert tr is not None and en is not None


# ─── /v1/quote integration ──────────────────────────────────────────


@pytest.fixture
def client():
    """Spin up a TestClient against the real app — same pattern as
    other route tests."""
    from app.main import app
    return TestClient(app)


def _quote_payload():
    """Minimal QuoteRequest body that produces a QUOTE envelope."""
    return {
        "procedure_id": "fue_hair_transplant",
        "locale": "tr",
        "profile": {"age": 30, "sex": "male"},
        "target_city": None,
        "top_n": 3,
    }


def test_quote_response_summary_tr_none_when_flag_off(client, monkeypatch):
    """Default config → flag off → summary_tr is None and no cache write."""
    monkeypatch.setattr(
        quote_summary.settings, "QUOTE_SUMMARY_LLM_ENABLED", False
    )
    resp = client.post("/v1/quote", json=_quote_payload())
    assert resp.status_code == 200
    payload = resp.json()["payload"]
    assert "summary_tr" in payload
    assert payload["summary_tr"] is None


def test_quote_response_summary_tr_none_on_first_call_then_cached(
    client, monkeypatch,
):
    """Flag on, cache empty → first call returns None and schedules a
    background task; the task populates the cache; second call returns
    the cached value.

    BackgroundTasks runs synchronously after the response in TestClient,
    so we can read the cache immediately after the first call returns.
    """
    monkeypatch.setattr(
        quote_summary.settings, "QUOTE_SUMMARY_LLM_ENABLED", True
    )
    monkeypatch.setattr(
        quote_summary.settings, "QUOTE_SUMMARY_LLM_PROVIDERS", "qwen",
    )
    with patch.object(
        quote_summary.qwen_llm, "is_enabled", return_value=True,
    ), patch.object(
        quote_summary.qwen_llm, "generate", return_value="özet metni",
    ):
        # First call — cache miss, BG task runs after response.
        r1 = client.post("/v1/quote", json=_quote_payload())
        assert r1.status_code == 200
        assert r1.json()["payload"]["summary_tr"] is None

        # Second call — different idempotency key, cache hit.
        r2 = client.post(
            "/v1/quote",
            json=_quote_payload(),
            headers={"Idempotency-Key": "fresh-key-2"},
        )
        assert r2.status_code == 200
        assert r2.json()["payload"]["summary_tr"] == "özet metni"


def test_no_background_task_when_flag_off(client, monkeypatch):
    """Flag off → background task must NOT be scheduled, even if a
    provider is mocked-enabled. Verified by asserting the cache stays
    empty after the request."""
    monkeypatch.setattr(
        quote_summary.settings, "QUOTE_SUMMARY_LLM_ENABLED", False
    )
    with patch.object(
        quote_summary.qwen_llm, "is_enabled", return_value=True,
    ), patch.object(
        quote_summary.qwen_llm, "generate",
        side_effect=AssertionError("must not be called"),
    ):
        resp = client.post("/v1/quote", json=_quote_payload())
    assert resp.status_code == 200
    # No cache entry was written.
    assert quote_summary.lookup_cached(
        procedure_id="fue_hair_transplant",
        top_clinic_id="*",  # any
        locale="tr",
    ) is None
