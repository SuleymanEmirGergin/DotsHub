"""Tests for app.observability.sentry_init.

Scope:
  - init_sentry() is a no-op when SENTRY_DSN is blank (default)
  - init_sentry() calls sentry_sdk.init() with the right kwargs when
    the DSN is set
  - before_send scrubs PII from request headers, request body,
    breadcrumbs, and extras
  - before_send drops events when environment is "test" or "ci"

We don't test the real Sentry HTTP transport — that's the SDK's job.
We just verify our contract with it.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.observability.sentry_init import before_send, init_sentry


class InitSentryTests(unittest.TestCase):
    def test_blank_dsn_is_no_op(self):
        from app.observability import sentry_init

        with patch.object(sentry_init.settings, "SENTRY_DSN", ""):
            with patch("sentry_sdk.init") as mocked_init:
                result = init_sentry()
        self.assertFalse(result)
        mocked_init.assert_not_called()

    def test_whitespace_dsn_is_no_op(self):
        """A DSN of just whitespace should be treated as unset — ops
        shouldn't accidentally activate Sentry by misconfiguring a
        blank ENV var."""
        from app.observability import sentry_init

        with patch.object(sentry_init.settings, "SENTRY_DSN", "   \t\n  "):
            with patch("sentry_sdk.init") as mocked_init:
                result = init_sentry()
        self.assertFalse(result)
        mocked_init.assert_not_called()

    def test_dsn_set_calls_sdk_init(self):
        from app.observability import sentry_init

        with patch.object(
            sentry_init.settings, "SENTRY_DSN", "https://abc@ingest.sentry.io/1"
        ):
            with patch.object(sentry_init.settings, "SENTRY_ENVIRONMENT", "staging"):
                with patch.object(
                    sentry_init.settings, "SENTRY_TRACES_SAMPLE_RATE", 0.1
                ):
                    with patch("sentry_sdk.init") as mocked_init:
                        result = init_sentry()
        self.assertTrue(result)
        mocked_init.assert_called_once()
        kwargs = mocked_init.call_args.kwargs
        self.assertEqual(kwargs["environment"], "staging")
        self.assertEqual(kwargs["traces_sample_rate"], 0.1)
        self.assertEqual(kwargs["send_default_pii"], False)
        self.assertIn("before_send", kwargs)

    def test_missing_sdk_logs_warning_returns_false(self):
        """If sentry-sdk is not installed but DSN is set, init returns
        False gracefully — the app keeps running."""
        from app.observability import sentry_init

        with patch.object(sentry_init.settings, "SENTRY_DSN", "https://x@y/1"):
            # Simulate import error by poisoning sys.modules with an
            # object that raises on attribute access. A simpler
            # alternative — patching __import__ — is hard to scope.
            with patch.dict("sys.modules", {"sentry_sdk": None}):
                result = init_sentry()
        self.assertFalse(result)


class BeforeSendScrubTests(unittest.TestCase):
    def test_drops_events_from_test_environment(self):
        from app.observability import sentry_init

        with patch.object(sentry_init.settings, "SENTRY_ENVIRONMENT", "test"):
            result = before_send({"message": "boom"}, {})
        self.assertIsNone(result)

    def test_drops_events_from_ci_environment(self):
        from app.observability import sentry_init

        with patch.object(sentry_init.settings, "SENTRY_ENVIRONMENT", "ci"):
            result = before_send({"message": "boom"}, {})
        self.assertIsNone(result)

    def test_scrubs_auth_headers(self):
        from app.observability import sentry_init

        with patch.object(sentry_init.settings, "SENTRY_ENVIRONMENT", "production"):
            event = {
                "request": {
                    "headers": {
                        "Authorization": "Bearer eyJxxx...",
                        "Cookie": "session=abc",
                        "X-Admin-Key": "admin-secret",
                        "x-device-id": "dev-12345",
                        "User-Agent": "DotsHub/1.0",
                    }
                }
            }
            out = before_send(event, {})
        headers = out["request"]["headers"]
        self.assertEqual(headers["Authorization"], "[SCRUBBED]")
        self.assertEqual(headers["Cookie"], "[SCRUBBED]")
        self.assertEqual(headers["X-Admin-Key"], "[SCRUBBED]")
        self.assertEqual(headers["x-device-id"], "[SCRUBBED]")
        # Non-sensitive headers pass through.
        self.assertEqual(headers["User-Agent"], "DotsHub/1.0")

    def test_scrubs_body_keys(self):
        from app.observability import sentry_init

        with patch.object(sentry_init.settings, "SENTRY_ENVIRONMENT", "production"):
            event = {
                "request": {
                    "data": {
                        "session_id": "sess-123",  # keep (non-PII)
                        "input_text": "TC 12345678901 ateşim var",  # scrub
                        "doctor_ready_summary_tr": "Patient summary",  # scrub
                        "nested": {
                            "answers": {"q1": "yes"},  # scrub
                        },
                    }
                }
            }
            out = before_send(event, {})
        data = out["request"]["data"]
        self.assertEqual(data["session_id"], "sess-123")
        self.assertEqual(data["input_text"], "[SCRUBBED]")
        self.assertEqual(data["doctor_ready_summary_tr"], "[SCRUBBED]")
        self.assertEqual(data["nested"]["answers"], "[SCRUBBED]")

    def test_redacts_pii_in_free_text_strings(self):
        """Free-text strings not in the scrub-key list still get PII
        redaction applied — TC IDs / phone numbers in logs shouldn't
        leak even if the key name is unrecognised."""
        from app.observability import sentry_init

        with patch.object(sentry_init.settings, "SENTRY_ENVIRONMENT", "production"):
            event = {
                "request": {
                    "data": {
                        "user_note": "my TC is 12345678901 please call 05321234567",
                    }
                }
            }
            out = before_send(event, {})
        note = out["request"]["data"]["user_note"]
        self.assertNotIn("12345678901", note)
        self.assertNotIn("05321234567", note)

    def test_scrubs_breadcrumb_messages(self):
        from app.observability import sentry_init

        with patch.object(sentry_init.settings, "SENTRY_ENVIRONMENT", "production"):
            event = {
                "breadcrumbs": {
                    "values": [
                        {"message": "TC 12345678901 logged in"},
                        {"message": "normal message"},
                        {"data": {"input_text": "patient said this"}},
                    ]
                }
            }
            out = before_send(event, {})
        crumbs = out["breadcrumbs"]["values"]
        self.assertNotIn("12345678901", crumbs[0]["message"])
        self.assertEqual(crumbs[1]["message"], "normal message")
        self.assertEqual(crumbs[2]["data"]["input_text"], "[SCRUBBED]")

    def test_preserves_event_shape_on_clean_input(self):
        """Idempotency check — a clean event should round-trip without
        losing any fields."""
        from app.observability import sentry_init

        with patch.object(sentry_init.settings, "SENTRY_ENVIRONMENT", "production"):
            event = {
                "message": "Something broke",
                "level": "error",
                "request": {
                    "url": "https://api.dotshub.co/v1/triage/turn",
                    "method": "POST",
                    "headers": {"X-Request-ID": "abc"},
                    "data": {"session_id": "s1"},
                },
            }
            out = before_send(event, {})
        self.assertEqual(out["message"], "Something broke")
        self.assertEqual(out["request"]["url"], "https://api.dotshub.co/v1/triage/turn")
        self.assertEqual(out["request"]["headers"]["X-Request-ID"], "abc")
        self.assertEqual(out["request"]["data"]["session_id"], "s1")


if __name__ == "__main__":
    unittest.main()
