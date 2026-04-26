"""Tests for the patient_uploads service module.

Validation, hashing, and the Supabase boundary (mocked). Route-level
tests live in test_patient_upload_route.py (B2 commit). Dispatcher
tests live in test_patient_upload_dispatcher.py (B3 commit).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services import patient_uploads


# ─── Validation ──────────────────────────────────────────────────────


def test_validate_consent_false_raises_422():
    with pytest.raises(patient_uploads.UploadValidationError) as exc:
        patient_uploads.validate_upload(
            kind="image",
            content_type="image/jpeg",
            size_bytes=100,
            consent_to_process=False,
        )
    assert exc.value.status_code == 422
    assert "consent" in exc.value.detail.lower()


def test_validate_unknown_kind_raises_422():
    with pytest.raises(patient_uploads.UploadValidationError) as exc:
        patient_uploads.validate_upload(
            kind="3d_model",
            content_type="image/jpeg",
            size_bytes=100,
            consent_to_process=True,
        )
    assert exc.value.status_code == 422


def test_validate_mime_not_in_kind_whitelist_raises_415():
    """An MP4 with kind=image is the classic bypass attempt for the
    image cap; must 415 before the dispatcher sees it."""
    with pytest.raises(patient_uploads.UploadValidationError) as exc:
        patient_uploads.validate_upload(
            kind="image",
            content_type="video/mp4",
            size_bytes=100,
            consent_to_process=True,
        )
    assert exc.value.status_code == 415


def test_validate_zero_size_rejected():
    with pytest.raises(patient_uploads.UploadValidationError) as exc:
        patient_uploads.validate_upload(
            kind="image",
            content_type="image/jpeg",
            size_bytes=0,
            consent_to_process=True,
        )
    assert exc.value.status_code == 422


def test_validate_size_over_cap_returns_413(monkeypatch):
    monkeypatch.setattr(
        patient_uploads.settings,
        "PATIENT_UPLOAD_MAX_IMAGE_BYTES",
        100,
    )
    with pytest.raises(patient_uploads.UploadValidationError) as exc:
        patient_uploads.validate_upload(
            kind="image",
            content_type="image/jpeg",
            size_bytes=101,
            consent_to_process=True,
        )
    assert exc.value.status_code == 413


def test_validate_happy_path_returns_none():
    """Valid input — no exception, returns None implicitly."""
    assert patient_uploads.validate_upload(
        kind="image",
        content_type="image/jpeg",
        size_bytes=1000,
        consent_to_process=True,
    ) is None


def test_document_kind_accepts_image_jpeg():
    """A JPEG with kind=document routes to dots_ocr later — same MIME,
    different intent. Validator must accept this combo."""
    assert patient_uploads.validate_upload(
        kind="document",
        content_type="image/jpeg",
        size_bytes=1000,
        consent_to_process=True,
    ) is None


def test_size_caps_distinct_per_kind():
    """Image cap should be lower than video cap by a healthy margin —
    sanity check on settings, not a tautology because the caps are
    independent env vars."""
    assert (
        patient_uploads.size_cap_for_kind("image")
        < patient_uploads.size_cap_for_kind("video")
    )


# ─── Prompt preset validation ────────────────────────────────────────


def test_validate_preset_none_is_valid():
    """No preset = use dispatcher default. Both '' and None accepted."""
    assert patient_uploads.validate_prompt_preset("image", None) is None
    assert patient_uploads.validate_prompt_preset("image", "") is None


def test_validate_preset_image_known_valid():
    assert patient_uploads.validate_prompt_preset(
        "image", "hair_loss_norwood"
    ) is None
    assert patient_uploads.validate_prompt_preset("image", "general") is None


def test_validate_preset_image_unknown_returns_422():
    with pytest.raises(patient_uploads.UploadValidationError) as exc:
        patient_uploads.validate_prompt_preset("image", "ultra_clinical")
    assert exc.value.status_code == 422
    assert "hair_loss_norwood" in exc.value.detail  # surface valid options


def test_validate_preset_audio_returns_422_even_when_known():
    """Audio uses fixed dispatcher defaults (whisper language='Turkish');
    a preset string is a config error -- 422."""
    with pytest.raises(patient_uploads.UploadValidationError) as exc:
        patient_uploads.validate_prompt_preset("audio", "anything")
    assert exc.value.status_code == 422
    assert "fixed dispatcher defaults" in exc.value.detail


def test_validate_preset_document_returns_422():
    with pytest.raises(patient_uploads.UploadValidationError):
        patient_uploads.validate_prompt_preset("document", "anything")


def test_validate_preset_video_known_valid():
    """Video presets are NOT the same set as image (cogvlm vs moondream
    naming); validator must respect the per-kind whitelist."""
    assert patient_uploads.validate_prompt_preset(
        "video", "rhinoplasty_assessment"  # cogvlm-only key
    ) is None


def test_validate_preset_image_video_keysets_differ():
    """Cross-pollination tripwire: 'rhinoplasty_assessment' is video
    only, 'rhinoplasty_profile' is image only. If someone consolidates
    the dicts upstream, this test surfaces it."""
    img = patient_uploads.PROMPT_PRESETS_BY_KIND["image"]
    vid = patient_uploads.PROMPT_PRESETS_BY_KIND["video"]
    assert "rhinoplasty_profile" in img
    assert "rhinoplasty_profile" not in vid
    assert "rhinoplasty_assessment" in vid
    assert "rhinoplasty_assessment" not in img


# ─── Hashing ─────────────────────────────────────────────────────────


def test_compute_sha256_deterministic():
    out1 = patient_uploads.compute_sha256(b"hello world")
    out2 = patient_uploads.compute_sha256(b"hello world")
    assert out1 == out2
    assert len(out1) == 64  # 32 bytes hex


def test_compute_sha256_changes_with_content():
    a = patient_uploads.compute_sha256(b"a")
    b = patient_uploads.compute_sha256(b"b")
    assert a != b


# ─── DB boundary (Supabase mocked) ───────────────────────────────────


@pytest.fixture
def fake_supabase():
    """Build a chainable mock that supports
    ``supabase.table(...).insert(...).execute()`` and
    ``.update(...).eq(...).is_(...).execute()``.
    """
    sb = MagicMock()
    chain = MagicMock()
    sb.table.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.lt.return_value = chain
    chain.is_.return_value = chain
    chain.maybe_single.return_value = chain
    return sb, chain


def test_record_upload_inserts_row_returns_asset_id(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=[{"asset_id": "AAA-111"}])
    with patch("app.db.supabase", sb):
        out = patient_uploads.record_upload(
            session_id="sess-1",
            sha256_hex="deadbeef",
            content_type="image/jpeg",
            size_bytes=1024,
            upload_kind="image",
            consent_to_process=True,
            consent_text="hair-loss estimate",
        )
    assert out == "AAA-111"
    sb.table.assert_called_with("patient_uploads")
    inserted = chain.insert.call_args.args[0]
    assert inserted["session_id"] == "sess-1"
    assert inserted["sha256_hex"] == "deadbeef"
    assert inserted["upload_kind"] == "image"
    assert inserted["consent_to_process"] is True
    assert inserted["ai_status"] == "pending"
    assert "expires_at" in inserted


def test_record_upload_empty_response_raises(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=[])
    with patch("app.db.supabase", sb), pytest.raises(RuntimeError):
        patient_uploads.record_upload(
            session_id="sess-1",
            sha256_hex="deadbeef",
            content_type="image/jpeg",
            size_bytes=1024,
            upload_kind="image",
            consent_to_process=True,
        )


def test_mark_succeeded_swallows_db_failure(fake_supabase, caplog):
    """Status updates run on the BG task; a transient DB blip must
    not crash the task — log + continue."""
    sb, chain = fake_supabase
    chain.execute.side_effect = ConnectionError("supabase down")
    with patch("app.db.supabase", sb):
        # Must not raise.
        patient_uploads.mark_succeeded(
            "asset-1", ai_result_text="ok", ai_latency_ms=500
        )


def test_mark_processing_writes_provider(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=[{"asset_id": "asset-1"}])
    with patch("app.db.supabase", sb):
        patient_uploads.mark_processing("asset-1", "moondream")
    patch_arg = chain.update.call_args.args[0]
    assert patch_arg["ai_status"] == "processing"
    assert patch_arg["ai_provider"] == "moondream"


def test_mark_failed_persists_error_string(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=[{"asset_id": "asset-1"}])
    with patch("app.db.supabase", sb):
        patient_uploads.mark_failed(
            "asset-1", ai_error="WiroAuthError: ...", ai_latency_ms=42
        )
    patch_arg = chain.update.call_args.args[0]
    assert patch_arg["ai_status"] == "failed"
    assert "WiroAuthError" in patch_arg["ai_error"]


def test_get_upload_returns_row_on_match(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(
        data={"asset_id": "asset-1", "ai_status": "succeeded", "deleted_at": None}
    )
    with patch("app.db.supabase", sb):
        out = patient_uploads.get_upload("asset-1")
    assert out is not None
    assert out["asset_id"] == "asset-1"


def test_get_upload_treats_tombstoned_as_not_found(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(
        data={"asset_id": "asset-1", "deleted_at": "2026-04-26T00:00:00Z"}
    )
    with patch("app.db.supabase", sb):
        out = patient_uploads.get_upload("asset-1")
    assert out is None


def test_get_upload_returns_none_on_db_404(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=None)
    with patch("app.db.supabase", sb):
        assert patient_uploads.get_upload("missing") is None


# ─── KVKK tombstone ──────────────────────────────────────────────────


def test_tombstone_clears_content_columns(fake_supabase):
    """The tombstone shape mirrors triage_sessions: content NULLed,
    ID + deleted_at kept. We assert the patch dict explicitly because
    a future schema addition (e.g. exif_metadata) would silently leak
    through if we forget to NULL it."""
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(
        data=[{"asset_id": "asset-1"}, {"asset_id": "asset-2"}]
    )
    with patch("app.db.supabase", sb):
        count = patient_uploads.tombstone_uploads_for_session("sess-1")
    assert count == 2
    patch_arg = chain.update.call_args.args[0]
    for content_col in (
        "sha256_hex", "ai_result_text", "ai_error", "consent_text",
    ):
        assert patch_arg[content_col] is None
    assert patch_arg["deleted_reason"] == "user_request"
    assert "deleted_at" in patch_arg


def test_tombstone_skips_already_deleted(fake_supabase):
    """Idempotency: the .is_('deleted_at', 'null') filter ensures
    re-running the tombstone on already-deleted rows is a no-op
    rather than re-stamping deleted_at."""
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=[])
    with patch("app.db.supabase", sb):
        count = patient_uploads.tombstone_uploads_for_session("sess-1")
    assert count == 0
    # The .is_ filter MUST appear in the chain — guarantees idempotency.
    chain.is_.assert_called_with("deleted_at", "null")


def test_tombstone_returns_minus_one_on_db_failure(fake_supabase):
    """A Supabase blip during data-rights deletion must NOT prevent
    the user from completing their delete — we surface -1 to signal
    'attempted, failed' (same convention as the existing tombstone)."""
    sb, chain = fake_supabase
    chain.execute.side_effect = ConnectionError("down")
    with patch("app.db.supabase", sb):
        assert patient_uploads.tombstone_uploads_for_session("sess-1") == -1


# ─── Retention sweep ─────────────────────────────────────────────────


def test_tombstone_expired_uploads_filters_by_expires_at(fake_supabase):
    """The sweep must use lt(expires_at, now) AND is_(deleted_at, null)
    so it skips both future and already-tombstoned rows. Future drift
    here would either leak PII (no expires_at filter) or re-stamp
    deleted_at (no idempotency filter)."""
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(
        data=[{"asset_id": "a"}, {"asset_id": "b"}, {"asset_id": "c"}]
    )
    with patch("app.db.supabase", sb):
        count = patient_uploads.tombstone_expired_uploads()
    assert count == 3
    chain.lt.assert_called_once()
    lt_call = chain.lt.call_args
    assert lt_call.args[0] == "expires_at"
    chain.is_.assert_called_with("deleted_at", "null")


def test_tombstone_expired_clears_content_columns(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=[{"asset_id": "a"}])
    with patch("app.db.supabase", sb):
        patient_uploads.tombstone_expired_uploads()
    patch_arg = chain.update.call_args.args[0]
    for content_col in (
        "sha256_hex", "ai_result_text", "ai_error", "consent_text",
    ):
        assert patch_arg[content_col] is None
    assert patch_arg["deleted_reason"] == "scheduled_retention"


def test_tombstone_expired_returns_minus_one_on_db_blip(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.side_effect = ConnectionError("supabase down")
    with patch("app.db.supabase", sb):
        assert patient_uploads.tombstone_expired_uploads() == -1


def test_tombstone_expired_zero_when_no_rows(fake_supabase):
    """Healthy steady-state: no rows past expires_at -> count 0,
    no exception. The cron treats 200 with count=0 as success."""
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=[])
    with patch("app.db.supabase", sb):
        assert patient_uploads.tombstone_expired_uploads() == 0


def test_tombstone_expired_custom_reason(fake_supabase):
    """Lets a manual sweep tag rows differently for forensic distinction
    (e.g. operator triggers a one-off cleanup post-incident)."""
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=[{"asset_id": "a"}])
    with patch("app.db.supabase", sb):
        patient_uploads.tombstone_expired_uploads(reason="post_incident_cleanup")
    patch_arg = chain.update.call_args.args[0]
    assert patch_arg["deleted_reason"] == "post_incident_cleanup"
