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
    chain.gte.return_value = chain
    chain.is_.return_value = chain
    chain.order.return_value = chain
    chain.range.return_value = chain
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


# ─── Set review state (A2) ──────────────────────────────────────────


def test_set_review_state_invalid_status_raises():
    with pytest.raises(ValueError):
        patient_uploads.set_review_state(
            "A1",
            review_status="archived",
            reviewer_notes=None,
            reviewed_by="admin",
        )


def test_set_review_state_excludes_tombstoned(fake_supabase):
    """Tombstoned rows MUST NOT receive review updates — KVKK contract:
    deleted means deleted, no further mutations."""
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=[])
    with patch("app.db.supabase", sb):
        out = patient_uploads.set_review_state(
            "A1",
            review_status="approved",
            reviewer_notes=None,
            reviewed_by="admin",
        )
    assert out is None
    chain.is_.assert_called_with("deleted_at", "null")


def test_set_review_state_writes_full_patch(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(
        data=[{
            "asset_id": "A1",
            "review_status": "needs_followup",
            "reviewed_by": "ops@x.tr",
        }]
    )
    with patch("app.db.supabase", sb):
        out = patient_uploads.set_review_state(
            "A1",
            review_status="needs_followup",
            reviewer_notes="please re-upload",
            reviewed_by="ops@x.tr",
        )
    assert out is not None
    patch_arg = chain.update.call_args.args[0]
    assert patch_arg["review_status"] == "needs_followup"
    assert patch_arg["reviewer_notes"] == "please re-upload"
    assert patch_arg["reviewed_by"] == "ops@x.tr"
    assert "reviewed_at" in patch_arg


def test_set_review_state_returns_none_on_db_blip(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.side_effect = ConnectionError("supabase down")
    with patch("app.db.supabase", sb):
        assert patient_uploads.set_review_state(
            "A1",
            review_status="approved",
            reviewer_notes=None,
            reviewed_by="admin",
        ) is None


def test_set_review_state_all_valid_statuses_accepted(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(
        data=[{"asset_id": "A1"}]
    )
    with patch("app.db.supabase", sb):
        for status in patient_uploads.VALID_REVIEW_STATUSES:
            assert patient_uploads.set_review_state(
                "A1",
                review_status=status,
                reviewer_notes=None,
                reviewed_by="admin",
            ) is not None


# ─── List for review (operator queue) ───────────────────────────────


def test_list_for_review_default_excludes_tombstoned(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=[], count=0)
    with patch("app.db.supabase", sb):
        patient_uploads.list_for_review()
    chain.is_.assert_called_with("deleted_at", "null")


def test_list_for_review_include_tombstoned_skips_filter(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=[], count=0)
    with patch("app.db.supabase", sb):
        patient_uploads.list_for_review(include_tombstoned=True)
    chain.is_.assert_not_called()


def test_list_for_review_returns_tuple_with_count(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(
        data=[{"asset_id": "A1"}, {"asset_id": "A2"}], count=99,
    )
    with patch("app.db.supabase", sb):
        rows, total = patient_uploads.list_for_review()
    assert len(rows) == 2
    assert total == 99


def test_list_for_review_filters_compose_with_and(fake_supabase):
    """Each non-None filter adds an .eq / .gte / .lt; absent filters
    skip entirely so the SQL doesn't carry redundant clauses."""
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=[], count=0)
    with patch("app.db.supabase", sb):
        patient_uploads.list_for_review(
            ai_status="failed",
            kind="image",
            session_id="S1",
            created_after="2026-04-01T00:00:00Z",
            created_before="2026-05-01T00:00:00Z",
        )
    eq_calls = [args.args for args in chain.eq.call_args_list]
    assert ("ai_status", "failed") in eq_calls
    assert ("upload_kind", "image") in eq_calls
    assert ("session_id", "S1") in eq_calls
    chain.gte.assert_called_with("created_at", "2026-04-01T00:00:00Z")
    chain.lt.assert_called_with("created_at", "2026-05-01T00:00:00Z")


def test_list_for_review_pagination_uses_range(fake_supabase):
    """range(offset, offset+limit-1) inclusive on both ends."""
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=[], count=0)
    with patch("app.db.supabase", sb):
        patient_uploads.list_for_review(limit=25, offset=50)
    chain.range.assert_called_with(50, 50 + 25 - 1)


def test_list_for_review_db_error_returns_empty_zero(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.side_effect = ConnectionError("supabase down")
    with patch("app.db.supabase", sb):
        rows, total = patient_uploads.list_for_review()
    assert rows == []
    assert total == 0


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
