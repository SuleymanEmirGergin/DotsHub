"""Tests for the operator image-gen endpoint.

Auth, provider validation, dispatch, and error-path coverage. The
underlying Wiro wrappers (``nano_banana_image.generate`` /
``gpt_image.generate``) are mocked at the module boundary so no Wiro
traffic and no signature-auth concerns in tests.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.services.ai import gpt_image, nano_banana_image


_ADMIN_KEY = "test-admin-key"  # matches conftest._STUB_ENV


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _enable_nano_banana(monkeypatch):
    monkeypatch.setattr(
        nano_banana_image.settings, "WIRO_NANO_BANANA_IMAGE_ENABLED", True
    )


def _enable_gpt_image(monkeypatch):
    monkeypatch.setattr(gpt_image.settings, "WIRO_GPT_IMAGE_ENABLED", True)


# ─── Auth ────────────────────────────────────────────────────────────


def test_missing_admin_key_returns_401(client):
    resp = client.post(
        "/v1/admin/image/generate",
        json={"provider": "nano_banana", "prompt": "test"},
    )
    assert resp.status_code == 401


def test_wrong_admin_key_returns_401(client):
    resp = client.post(
        "/v1/admin/image/generate",
        json={"provider": "nano_banana", "prompt": "test"},
        headers={"x-admin-key": "wrong-key"},
    )
    assert resp.status_code == 401


# ─── Validation ──────────────────────────────────────────────────────


def test_unknown_provider_returns_422(client):
    resp = client.post(
        "/v1/admin/image/generate",
        json={"provider": "midjourney_v9", "prompt": "test"},
        headers={"x-admin-key": _ADMIN_KEY},
    )
    assert resp.status_code == 422


def test_empty_prompt_returns_422(client):
    resp = client.post(
        "/v1/admin/image/generate",
        json={"provider": "nano_banana", "prompt": ""},
        headers={"x-admin-key": _ADMIN_KEY},
    )
    assert resp.status_code == 422


def test_samples_out_of_range_returns_422(client):
    resp = client.post(
        "/v1/admin/image/generate",
        json={"provider": "gpt_image", "prompt": "test", "samples": 100},
        headers={"x-admin-key": _ADMIN_KEY},
    )
    assert resp.status_code == 422


def test_unsupported_aspect_ratio_returns_422(client):
    resp = client.post(
        "/v1/admin/image/generate",
        json={
            "provider": "nano_banana",
            "prompt": "test",
            "aspect_ratio": "9999:1",
        },
        headers={"x-admin-key": _ADMIN_KEY},
    )
    assert resp.status_code == 422


# ─── Provider gate ───────────────────────────────────────────────────


def test_nano_banana_disabled_returns_503(client, monkeypatch):
    monkeypatch.setattr(
        nano_banana_image.settings, "WIRO_NANO_BANANA_IMAGE_ENABLED", False
    )
    resp = client.post(
        "/v1/admin/image/generate",
        json={"provider": "nano_banana", "prompt": "test"},
        headers={"x-admin-key": _ADMIN_KEY},
    )
    assert resp.status_code == 503
    assert "WIRO_NANO_BANANA_IMAGE_ENABLED" in resp.json()["detail"]


def test_gpt_image_disabled_returns_503(client, monkeypatch):
    monkeypatch.setattr(gpt_image.settings, "WIRO_GPT_IMAGE_ENABLED", False)
    resp = client.post(
        "/v1/admin/image/generate",
        json={"provider": "gpt_image", "prompt": "test"},
        headers={"x-admin-key": _ADMIN_KEY},
    )
    assert resp.status_code == 503
    assert "WIRO_GPT_IMAGE_ENABLED" in resp.json()["detail"]


# ─── Happy paths ─────────────────────────────────────────────────────


def test_nano_banana_dispatched_returns_urls(client, monkeypatch):
    _enable_nano_banana(monkeypatch)
    with patch.object(
        nano_banana_image, "generate",
        return_value=["https://cdn/a.png", "https://cdn/b.png"],
    ):
        resp = client.post(
            "/v1/admin/image/generate",
            json={
                "provider": "nano_banana",
                "prompt": "modern dental clinic interior",
                "aspect_ratio": "16:9",
                "resolution": "2K",
            },
            headers={"x-admin-key": _ADMIN_KEY},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["urls"] == ["https://cdn/a.png", "https://cdn/b.png"]
    assert body["provider_used"] == "nano_banana"
    assert body["elapsed_ms"] >= 0


def test_gpt_image_dispatched_returns_urls(client, monkeypatch):
    _enable_gpt_image(monkeypatch)
    with patch.object(
        gpt_image, "generate", return_value=["https://cdn/g.png"],
    ):
        resp = client.post(
            "/v1/admin/image/generate",
            json={
                "provider": "gpt_image",
                "prompt": "professional clinic illustration",
                "size": "1:1",
                "quality": "high",
                "samples": 1,
            },
            headers={"x-admin-key": _ADMIN_KEY},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["urls"] == ["https://cdn/g.png"]
    assert body["provider_used"] == "gpt_image"


def test_reference_image_url_forwarded_to_nano_banana(client, monkeypatch):
    """The dashboard passes a reference_image_url for image-edit mode;
    the route must forward it to the wrapper's reference_image_url
    parameter (NOT input_image_url — that's the gpt_image kwarg)."""
    _enable_nano_banana(monkeypatch)
    captured = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        return ["https://cdn/x.png"]

    with patch.object(nano_banana_image, "generate", side_effect=_capture):
        resp = client.post(
            "/v1/admin/image/generate",
            json={
                "provider": "nano_banana",
                "prompt": "edit teeth color",
                "reference_image_url": "https://example.com/ref.jpg",
            },
            headers={"x-admin-key": _ADMIN_KEY},
        )
    assert resp.status_code == 200
    assert captured["reference_image_url"] == "https://example.com/ref.jpg"
    assert "input_image_url" not in captured


def test_reference_image_url_forwarded_to_gpt_image(client, monkeypatch):
    """Symmetric: gpt_image's wrapper kwarg is input_image_url."""
    _enable_gpt_image(monkeypatch)
    captured = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        return ["https://cdn/g.png"]

    with patch.object(gpt_image, "generate", side_effect=_capture):
        resp = client.post(
            "/v1/admin/image/generate",
            json={
                "provider": "gpt_image",
                "prompt": "edit",
                "reference_image_url": "https://example.com/r.jpg",
            },
            headers={"x-admin-key": _ADMIN_KEY},
        )
    assert resp.status_code == 200
    assert captured["input_image_url"] == "https://example.com/r.jpg"
    assert "reference_image_url" not in captured


# ─── Error paths ─────────────────────────────────────────────────────


def test_provider_returns_none_yields_502(client, monkeypatch):
    """Wrapper returns None on auth/network/task failure → 502."""
    _enable_nano_banana(monkeypatch)
    with patch.object(nano_banana_image, "generate", return_value=None):
        resp = client.post(
            "/v1/admin/image/generate",
            json={"provider": "nano_banana", "prompt": "test"},
            headers={"x-admin-key": _ADMIN_KEY},
        )
    assert resp.status_code == 502
    assert "no images" in resp.json()["detail"]


def test_provider_returns_empty_list_yields_502(client, monkeypatch):
    """Empty list is treated the same as None — wrapper had nothing to
    surface. Caller renders nothing; 502 lets the dashboard skip."""
    _enable_nano_banana(monkeypatch)
    with patch.object(nano_banana_image, "generate", return_value=[]):
        resp = client.post(
            "/v1/admin/image/generate",
            json={"provider": "nano_banana", "prompt": "test"},
            headers={"x-admin-key": _ADMIN_KEY},
        )
    assert resp.status_code == 502


def test_irrelevant_provider_kwargs_ignored(client, monkeypatch):
    """nano_banana payload that includes gpt_image-only fields (size,
    quality) must NOT forward those to the nano_banana wrapper —
    Pydantic accepts them at the request layer but the route only
    reads provider-relevant fields."""
    _enable_nano_banana(monkeypatch)
    captured = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        return ["https://cdn/x.png"]

    with patch.object(nano_banana_image, "generate", side_effect=_capture):
        resp = client.post(
            "/v1/admin/image/generate",
            json={
                "provider": "nano_banana",
                "prompt": "test",
                "size": "1:1",  # gpt_image-only — must not leak
                "quality": "high",  # gpt_image-only — must not leak
            },
            headers={"x-admin-key": _ADMIN_KEY},
        )
    assert resp.status_code == 200
    assert "size" not in captured
    assert "quality" not in captured
