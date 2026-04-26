"""Tests for the patient upload route + polling endpoint.

Covers POST /v1/patient/upload (multipart) and GET /v1/patient/upload/
{asset_id}. The Supabase boundary (record_upload, get_upload, mark_*)
is mocked at the patient_uploads.* module level so tests don't need
a real DB. The dispatcher is the placeholder shipped in B2 — tests
assert that it's scheduled, B3 will replace the placeholder body
with the real Wiro routing.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.services import patient_upload_dispatcher, patient_uploads


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _enable_uploads(monkeypatch):
    monkeypatch.setattr(
        patient_uploads.settings, "PATIENT_UPLOAD_ENABLED", True
    )


def _png_bytes() -> bytes:
    """Minimal valid PNG header — keeps tests honest about content
    being a real binary, not just text."""
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


# ─── POST: feature gating ───────────────────────────────────────────


def test_post_returns_503_when_disabled(client, monkeypatch):
    monkeypatch.setattr(
        patient_uploads.settings, "PATIENT_UPLOAD_ENABLED", False
    )
    resp = client.post(
        "/v1/patient/upload",
        files={"file": ("a.png", _png_bytes(), "image/png")},
        data={"kind": "image", "consent_to_process": "true"},
        headers={"X-Session-Id": "sess-1"},
    )
    assert resp.status_code == 503


def test_post_requires_session_header(client, monkeypatch):
    _enable_uploads(monkeypatch)
    resp = client.post(
        "/v1/patient/upload",
        files={"file": ("a.png", _png_bytes(), "image/png")},
        data={"kind": "image", "consent_to_process": "true"},
        # No X-Session-Id.
    )
    assert resp.status_code == 400
    assert "Session-Id" in resp.json()["detail"]


# ─── POST: validation errors map to right HTTP code ─────────────────


def test_post_consent_false_returns_422(client, monkeypatch):
    _enable_uploads(monkeypatch)
    resp = client.post(
        "/v1/patient/upload",
        files={"file": ("a.png", _png_bytes(), "image/png")},
        data={"kind": "image", "consent_to_process": "false"},
        headers={"X-Session-Id": "sess-1"},
    )
    assert resp.status_code == 422
    assert "consent" in resp.json()["detail"].lower()


def test_post_unknown_kind_returns_422(client, monkeypatch):
    _enable_uploads(monkeypatch)
    resp = client.post(
        "/v1/patient/upload",
        files={"file": ("a.png", _png_bytes(), "image/png")},
        data={"kind": "ply_3d_model", "consent_to_process": "true"},
        headers={"X-Session-Id": "sess-1"},
    )
    assert resp.status_code == 422


def test_post_mime_video_with_kind_image_returns_415(client, monkeypatch):
    """Classic bypass attempt — declare image to dodge the 100MB
    video cap, send a video. Validator catches before the dispatcher."""
    _enable_uploads(monkeypatch)
    resp = client.post(
        "/v1/patient/upload",
        files={"file": ("a.mp4", b"\x00" * 100, "video/mp4")},
        data={"kind": "image", "consent_to_process": "true"},
        headers={"X-Session-Id": "sess-1"},
    )
    assert resp.status_code == 415


def test_post_oversize_returns_413(client, monkeypatch):
    _enable_uploads(monkeypatch)
    monkeypatch.setattr(
        patient_uploads.settings, "PATIENT_UPLOAD_MAX_IMAGE_BYTES", 100
    )
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200  # 208 bytes > 100
    resp = client.post(
        "/v1/patient/upload",
        files={"file": ("a.png", big, "image/png")},
        data={"kind": "image", "consent_to_process": "true"},
        headers={"X-Session-Id": "sess-1"},
    )
    assert resp.status_code == 413


def test_post_empty_file_returns_422(client, monkeypatch):
    _enable_uploads(monkeypatch)
    resp = client.post(
        "/v1/patient/upload",
        files={"file": ("a.png", b"", "image/png")},
        data={"kind": "image", "consent_to_process": "true"},
        headers={"X-Session-Id": "sess-1"},
    )
    assert resp.status_code == 422


# ─── POST: happy path ───────────────────────────────────────────────


def test_post_happy_path_returns_201_with_asset_id(client, monkeypatch):
    _enable_uploads(monkeypatch)
    with patch.object(
        patient_uploads, "record_upload", return_value="ASSET-XYZ",
    ), patch.object(
        patient_upload_dispatcher, "dispatch_to_ai",
    ):
        resp = client.post(
            "/v1/patient/upload",
            files={"file": ("a.png", _png_bytes(), "image/png")},
            data={
                "kind": "image",
                "consent_to_process": "true",
                "consent_text": "hair-loss estimate",
            },
            headers={"X-Session-Id": "sess-1"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["asset_id"] == "ASSET-XYZ"
    assert body["status"] == "pending"
    assert body["poll_url"] == "/v1/patient/upload/ASSET-XYZ"


def test_post_records_consent_text_through_to_db(client, monkeypatch):
    _enable_uploads(monkeypatch)
    captured = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        return "ASSET-1"

    with patch.object(
        patient_uploads, "record_upload", side_effect=_capture,
    ), patch.object(
        patient_upload_dispatcher, "dispatch_to_ai",
    ):
        client.post(
            "/v1/patient/upload",
            files={"file": ("a.png", _png_bytes(), "image/png")},
            data={
                "kind": "image",
                "consent_to_process": "true",
                "consent_text": "Norwood estimate (clinical)",
            },
            headers={"X-Session-Id": "sess-9"},
        )
    assert captured["consent_text"] == "Norwood estimate (clinical)"
    assert captured["consent_to_process"] is True
    assert captured["session_id"] == "sess-9"
    assert captured["upload_kind"] == "image"
    assert captured["content_type"] == "image/png"
    # sha256 was computed and forwarded.
    assert isinstance(captured["sha256_hex"], str)
    assert len(captured["sha256_hex"]) == 64


def test_post_schedules_dispatcher_with_correct_kwargs(client, monkeypatch):
    """The BG task receives asset_id + bytes + kind + content_type +
    filename. Critical because the placeholder dispatcher reads kind
    to decide which AI service to call (B3)."""
    _enable_uploads(monkeypatch)
    dispatched = []

    def _fake_dispatch(asset_id, content_bytes, **kwargs):
        dispatched.append({
            "asset_id": asset_id,
            "size": len(content_bytes),
            **kwargs,
        })

    with patch.object(
        patient_uploads, "record_upload", return_value="ASSET-1",
    ), patch.object(
        patient_upload_dispatcher, "dispatch_to_ai", side_effect=_fake_dispatch,
    ):
        png = _png_bytes()
        client.post(
            "/v1/patient/upload",
            files={"file": ("scalp.png", png, "image/png")},
            data={"kind": "image", "consent_to_process": "true"},
            headers={"X-Session-Id": "sess-1"},
        )
    assert len(dispatched) == 1
    assert dispatched[0]["asset_id"] == "ASSET-1"
    assert dispatched[0]["upload_kind"] == "image"
    assert dispatched[0]["content_type"] == "image/png"
    assert dispatched[0]["filename"] == "scalp.png"
    assert dispatched[0]["size"] == len(_png_bytes())


def test_post_db_failure_returns_500(client, monkeypatch):
    _enable_uploads(monkeypatch)
    with patch.object(
        patient_uploads, "record_upload",
        side_effect=ConnectionError("supabase down"),
    ):
        resp = client.post(
            "/v1/patient/upload",
            files={"file": ("a.png", _png_bytes(), "image/png")},
            data={"kind": "image", "consent_to_process": "true"},
            headers={"X-Session-Id": "sess-1"},
        )
    assert resp.status_code == 500


# ─── GET polling ────────────────────────────────────────────────────


def test_get_returns_404_when_not_found(client, monkeypatch):
    _enable_uploads(monkeypatch)
    with patch.object(patient_uploads, "get_upload", return_value=None):
        resp = client.get("/v1/patient/upload/missing-id")
    assert resp.status_code == 404


def test_get_returns_503_when_disabled(client, monkeypatch):
    monkeypatch.setattr(
        patient_uploads.settings, "PATIENT_UPLOAD_ENABLED", False
    )
    resp = client.get("/v1/patient/upload/anything")
    assert resp.status_code == 503


def test_get_pending_includes_retry_after_header(client, monkeypatch):
    _enable_uploads(monkeypatch)
    monkeypatch.setattr(
        patient_uploads.settings, "PATIENT_UPLOAD_POLL_INTERVAL_SECONDS", 7
    )
    fake_row = {
        "asset_id": "A1",
        "ai_status": "pending",
        "upload_kind": "image",
        "content_type": "image/png",
        "size_bytes": 100,
        "created_at": "2026-04-26T00:00:00Z",
        "expires_at": "2026-05-26T00:00:00Z",
    }
    with patch.object(patient_uploads, "get_upload", return_value=fake_row):
        resp = client.get("/v1/patient/upload/A1")
    assert resp.status_code == 200
    assert resp.headers.get("retry-after") == "7"


def test_get_succeeded_no_retry_after(client, monkeypatch):
    """Terminal state -> client should stop polling. Retry-After
    header MUST NOT be present so a header-respecting client stops."""
    _enable_uploads(monkeypatch)
    fake_row = {
        "asset_id": "A1",
        "ai_status": "succeeded",
        "ai_provider": "moondream",
        "ai_result_text": '{"norwood_stage": 3}',
        "ai_latency_ms": 4500,
        "upload_kind": "image",
        "content_type": "image/png",
        "size_bytes": 100,
        "created_at": "2026-04-26T00:00:00Z",
        "processed_at": "2026-04-26T00:00:05Z",
        "expires_at": "2026-05-26T00:00:00Z",
    }
    with patch.object(patient_uploads, "get_upload", return_value=fake_row):
        resp = client.get("/v1/patient/upload/A1")
    assert resp.status_code == 200
    assert "retry-after" not in {k.lower() for k in resp.headers.keys()}
    body = resp.json()
    assert body["status"] == "succeeded"
    assert body["ai_provider"] == "moondream"
    assert '"norwood_stage"' in body["ai_result_text"]


# ─── prompt_preset (B5) ─────────────────────────────────────────────


def test_post_image_with_valid_preset_201(client, monkeypatch):
    _enable_uploads(monkeypatch)
    captured = {}

    def _capture(asset_id, content_bytes, **kwargs):
        captured.update(kwargs)

    with patch.object(
        patient_uploads, "record_upload", return_value="ASSET-1",
    ), patch.object(
        patient_upload_dispatcher, "dispatch_to_ai", side_effect=_capture,
    ):
        resp = client.post(
            "/v1/patient/upload",
            files={"file": ("scalp.png", _png_bytes(), "image/png")},
            data={
                "kind": "image",
                "consent_to_process": "true",
                "prompt_preset": "hair_loss_norwood",
            },
            headers={"X-Session-Id": "sess-1"},
        )
    assert resp.status_code == 201
    assert captured["prompt_preset"] == "hair_loss_norwood"


def test_post_image_invalid_preset_returns_422(client, monkeypatch):
    _enable_uploads(monkeypatch)
    resp = client.post(
        "/v1/patient/upload",
        files={"file": ("a.png", _png_bytes(), "image/png")},
        data={
            "kind": "image",
            "consent_to_process": "true",
            "prompt_preset": "ultra_clinical",
        },
        headers={"X-Session-Id": "sess-1"},
    )
    assert resp.status_code == 422
    assert "hair_loss_norwood" in resp.json()["detail"]


def test_post_audio_with_any_preset_returns_422(client, monkeypatch):
    """Audio kind doesn't accept presets — whisper language is fixed."""
    _enable_uploads(monkeypatch)
    resp = client.post(
        "/v1/patient/upload",
        files={"file": ("memo.mp3", b"\x00\x01" * 100, "audio/mp3")},
        data={
            "kind": "audio",
            "consent_to_process": "true",
            "prompt_preset": "anything",
        },
        headers={"X-Session-Id": "sess-1"},
    )
    assert resp.status_code == 422
    assert "fixed dispatcher defaults" in resp.json()["detail"]


def test_post_document_with_any_preset_returns_422(client, monkeypatch):
    _enable_uploads(monkeypatch)
    resp = client.post(
        "/v1/patient/upload",
        files={"file": ("lab.pdf", b"%PDF-1" + b"\x00" * 32, "application/pdf")},
        data={
            "kind": "document",
            "consent_to_process": "true",
            "prompt_preset": "any",
        },
        headers={"X-Session-Id": "sess-1"},
    )
    assert resp.status_code == 422


def test_post_video_with_valid_preset_201(client, monkeypatch):
    _enable_uploads(monkeypatch)
    captured = {}

    def _capture(asset_id, content_bytes, **kwargs):
        captured.update(kwargs)

    with patch.object(
        patient_uploads, "record_upload", return_value="ASSET-V1",
    ), patch.object(
        patient_upload_dispatcher, "dispatch_to_ai", side_effect=_capture,
    ):
        resp = client.post(
            "/v1/patient/upload",
            files={"file": ("clip.mp4", b"\x00\x01" * 100, "video/mp4")},
            data={
                "kind": "video",
                "consent_to_process": "true",
                "prompt_preset": "rhinoplasty_assessment",
            },
            headers={"X-Session-Id": "sess-1"},
        )
    assert resp.status_code == 201
    assert captured["prompt_preset"] == "rhinoplasty_assessment"


def test_post_image_with_video_preset_returns_422(client, monkeypatch):
    """rhinoplasty_assessment is a cogvlm-only key — sending it with
    kind=image must 422 (caller's intent likely a typo)."""
    _enable_uploads(monkeypatch)
    resp = client.post(
        "/v1/patient/upload",
        files={"file": ("a.png", _png_bytes(), "image/png")},
        data={
            "kind": "image",
            "consent_to_process": "true",
            "prompt_preset": "rhinoplasty_assessment",
        },
        headers={"X-Session-Id": "sess-1"},
    )
    assert resp.status_code == 422


def test_get_does_not_leak_session_id_or_sha256(client, monkeypatch):
    """Operator data + forensic hash MUST NOT appear in the polling
    response. Patient sees only their own upload metadata + AI result."""
    _enable_uploads(monkeypatch)
    fake_row = {
        "asset_id": "A1",
        "session_id": "sess-internal-1",
        "sha256_hex": "deadbeef" * 8,
        "ai_status": "succeeded",
        "ai_result_text": "blurb",
        "upload_kind": "image",
        "content_type": "image/png",
        "size_bytes": 100,
        "created_at": "2026-04-26T00:00:00Z",
        "expires_at": "2026-05-26T00:00:00Z",
    }
    with patch.object(patient_uploads, "get_upload", return_value=fake_row):
        resp = client.get("/v1/patient/upload/A1")
    body = resp.json()
    assert "session_id" not in body
    assert "sha256_hex" not in body
