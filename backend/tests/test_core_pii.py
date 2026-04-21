"""Unit tests for app/core/pii.py — log-line PII masking.

The `mask_for_log` helper is the last line of defense before any
potentially-sensitive string (device_id, email, session tokens, raw
symptom text) reaches structured logs. Prior to this suite the module
had 0% coverage, which meant a regression that, say, returned the full
email instead of the masked version would not trip CI. Since every
backend log pipeline funnels through this function, silent failures
here would leak PII to Sentry / stdout / Fly.io's log drain.

The tests walk each branch of the field-name dispatcher (device, email,
default) plus the three length bands that decide how much of the
string survives the mask.
"""

from __future__ import annotations

import unittest

from app.core.pii import mask_for_log


class EmptyAndNoneInputTests(unittest.TestCase):
    """The module promises `(empty)` for any falsy / whitespace-only input.

    Loggers frequently pass through optional request headers that may be
    absent — we must not crash on `None` and must not emit the raw empty
    string, since ``f"device={mask_for_log(None)}"`` would otherwise
    render as ``device=`` and silently drop a diagnostic field.
    """

    def test_none_returns_empty_marker(self):
        self.assertEqual(mask_for_log(None), "(empty)")

    def test_empty_string_returns_empty_marker(self):
        self.assertEqual(mask_for_log(""), "(empty)")

    def test_whitespace_only_returns_empty_marker(self):
        self.assertEqual(mask_for_log("   "), "(empty)")

    def test_tab_and_newline_returns_empty_marker(self):
        self.assertEqual(mask_for_log("\t\n "), "(empty)")

    def test_none_with_device_field_still_empty(self):
        # Branch: None short-circuits before field dispatch.
        self.assertEqual(mask_for_log(None, field_name="device_id"), "(empty)")


class DeviceIdMaskingTests(unittest.TestCase):
    """device_id values: keep first 4 chars for debugging, mask the rest.

    The mobile app ships a UUID-shaped device_id, so the typical value
    is well over 8 chars and falls into the "prefix + stars" branch.
    The <=8 path exists as a safety net for legacy / truncated values.
    """

    def test_long_device_id_shows_first_four_then_stars(self):
        # 36-char UUID — the real-world shape.
        uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        self.assertEqual(mask_for_log(uuid, field_name="device_id"), "a1b2****")

    def test_short_device_id_is_fully_masked(self):
        self.assertEqual(mask_for_log("abc12", field_name="device_id"), "****")

    def test_device_id_exactly_eight_chars_is_fully_masked(self):
        # Boundary: len == 8 falls into the "<= 8" branch.
        self.assertEqual(mask_for_log("abcdefgh", field_name="device_id"), "****")

    def test_device_id_nine_chars_shows_prefix(self):
        # Boundary: len == 9 crosses into the prefix branch.
        self.assertEqual(mask_for_log("abcdefghi", field_name="device_id"), "abcd****")

    def test_field_name_case_insensitive_for_device(self):
        self.assertEqual(
            mask_for_log("abcdefghij", field_name="X-DEVICE-ID"), "abcd****"
        )

    def test_field_name_with_device_substring_routes_through_device_branch(self):
        # "user_device" contains "device" — should still trigger device masking.
        self.assertEqual(
            mask_for_log("abcdefghij", field_name="user_device"), "abcd****"
        )

    def test_device_id_value_is_stripped_before_masking(self):
        # Leading/trailing whitespace must not shift the visible prefix.
        self.assertEqual(
            mask_for_log("  abcdefghij  ", field_name="device_id"), "abcd****"
        )


class EmailMaskingTests(unittest.TestCase):
    """Email values: keep 2-char local and domain prefixes.

    The pattern `xx***@yy***` lets engineers correlate the same user
    across log lines (via the same masked prefix) without ever storing
    the plaintext address in logs.
    """

    def test_normal_email_shows_both_prefixes(self):
        self.assertEqual(
            mask_for_log("alice@example.com", field_name="email"),
            "al***@ex***",
        )

    def test_email_with_short_local_part_masks_fully(self):
        # Local part is exactly 2 chars — no room for a prefix, so "***".
        self.assertEqual(
            mask_for_log("ab@example.com", field_name="email"),
            "***@ex***",
        )

    def test_email_with_one_char_local_masks_fully(self):
        self.assertEqual(
            mask_for_log("a@example.com", field_name="email"),
            "***@ex***",
        )

    def test_email_with_short_domain_masks_domain_fully(self):
        self.assertEqual(
            mask_for_log("alice@ab", field_name="email"),
            "al***@***",
        )

    def test_email_without_at_sign_falls_back_to_prefix(self):
        # If the "email" field doesn't contain an @, treat as opaque string
        # with a 2-char visible prefix.
        self.assertEqual(
            mask_for_log("notanemail", field_name="email"),
            "no***",
        )

    def test_email_without_at_sign_short_value_is_fully_masked(self):
        self.assertEqual(mask_for_log("a", field_name="email"), "***")

    def test_email_without_at_sign_exactly_two_chars_is_fully_masked(self):
        # Boundary: len == 2 falls into the "<= 2" branch.
        self.assertEqual(mask_for_log("ab", field_name="email"), "***")

    def test_email_field_name_case_insensitive(self):
        self.assertEqual(
            mask_for_log("alice@example.com", field_name="EMAIL"),
            "al***@ex***",
        )

    def test_user_email_field_name_routes_through_email_branch(self):
        # Substring match: "user_email" contains "email".
        self.assertEqual(
            mask_for_log("alice@example.com", field_name="user_email"),
            "al***@ex***",
        )


class DefaultMaskingTests(unittest.TestCase):
    """Fallback masking for unknown field names.

    This is what protects fields we haven't explicitly categorized —
    session_id, access_token, raw symptom strings, etc. The three bands
    (<=4, 5-8, >8) correspond to "too short to reveal anything", "still
    risky to show partial", and "safe to show last 4 for correlation".
    """

    def test_short_value_fully_masked(self):
        self.assertEqual(mask_for_log("abcd", field_name="value"), "****")

    def test_one_char_value_fully_masked(self):
        self.assertEqual(mask_for_log("a", field_name="value"), "****")

    def test_medium_value_fully_masked(self):
        # Length 5-8 still doesn't reveal any characters.
        self.assertEqual(mask_for_log("abcdef", field_name="value"), "****")

    def test_eight_char_value_fully_masked(self):
        # Boundary: len == 8 falls into the "<= 8" branch of the final
        # conditional (not the ">8" branch).
        self.assertEqual(mask_for_log("abcdefgh", field_name="value"), "****")

    def test_long_value_shows_stars_and_last_four(self):
        self.assertEqual(
            mask_for_log("abcdefghij", field_name="value"), "***ghij"
        )

    def test_session_id_like_value_shows_last_four(self):
        session_like = "ses_01HXYZABCD1234"
        self.assertEqual(
            mask_for_log(session_like, field_name="session_id"), "***1234"
        )

    def test_default_branch_strips_whitespace_before_length_check(self):
        # "   abc   " -> stripped to "abc" -> len 3 -> "****".
        self.assertEqual(mask_for_log("   abc   ", field_name="value"), "****")

    def test_default_field_name_when_unspecified(self):
        # `field_name` defaults to "value"; confirm the default routes
        # through the generic branch (not device or email).
        self.assertEqual(mask_for_log("abcdefghij"), "***ghij")

    def test_unicode_value_survives_masking(self):
        # Last-4 slicing should work on Python 3 strings regardless of
        # whether the chars are multi-byte in UTF-8.
        self.assertEqual(
            mask_for_log("tıknefes123456", field_name="symptom"), "***3456"
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
