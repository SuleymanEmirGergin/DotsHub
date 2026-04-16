"""Tests for app.services.email_sender_resend.send_via_resend.

httpx is imported lazily (inside the function body) so we cannot patch
``app.services.email_sender_resend.httpx``.  We patch ``httpx.Client``
directly on the httpx module, which is always the authoritative location
regardless of where the import happens.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

import httpx  # ensure the real module is imported so patching works


# ---------------------------------------------------------------------------
# Helper: build a mock httpx response
# ---------------------------------------------------------------------------

def _make_response(status_code: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.is_success = (200 <= status_code < 300)
    resp.text = ""
    return resp


# ---------------------------------------------------------------------------
# Class 1 — no API key
# ---------------------------------------------------------------------------

class ResendSenderNoKeyTests(unittest.TestCase):
    """send_via_resend must be a no-op when RESEND_API_KEY is missing."""

    def test_no_api_key_does_not_call_http(self):
        """When RESEND_API_KEY is empty the HTTP client must never be constructed."""
        env = {"RESEND_API_KEY": "", "RESEND_FROM": ""}
        with patch.dict(os.environ, env, clear=False):
            with patch("httpx.Client") as mock_cls:
                from app.services.email_sender_resend import send_via_resend
                send_via_resend("to@example.com", "subject", "body")
                mock_cls.assert_not_called()


# ---------------------------------------------------------------------------
# Class 2 — success paths
# ---------------------------------------------------------------------------

class ResendSenderSuccessTests(unittest.TestCase):
    """Happy-path tests for send_via_resend."""

    _BASE_ENV = {"RESEND_API_KEY": "test-key"}

    def _call_send(self, extra_env: dict, to="to@test.com", subject="Hello",
                   body_text="plain", body_html="<p>plain</p>"):
        env = {**self._BASE_ENV, **extra_env}
        with patch.dict(os.environ, env, clear=False):
            with patch("httpx.Client") as mock_cls:
                mock_client = MagicMock()
                mock_cls.return_value.__enter__.return_value = mock_client
                mock_client.post.return_value = _make_response(200)

                from app.services.email_sender_resend import send_via_resend
                send_via_resend(to, subject, body_text, body_html)

                return mock_client

    def test_success_200_sends_correct_payload(self):
        """A 200 response → post called once with to/subject/html/text keys."""
        mock_client = self._call_send(
            {},
            to="recipient@example.com",
            subject="Test Subject",
            body_text="hello",
            body_html="<b>hello</b>",
        )
        mock_client.post.assert_called_once()
        _, kwargs = mock_client.post.call_args
        payload = kwargs["json"]
        self.assertIn("to", payload)
        self.assertIn("subject", payload)
        self.assertIn("html", payload)
        self.assertEqual(payload["subject"], "Test Subject")
        self.assertIn("recipient@example.com", payload["to"])

    def test_from_address_uses_env_var(self):
        """RESEND_FROM env var is used as the from field."""
        mock_client = self._call_send({"RESEND_FROM": "custom@example.com"})
        _, kwargs = mock_client.post.call_args
        self.assertEqual(kwargs["json"]["from"], "custom@example.com")

    def test_from_address_falls_back_to_default(self):
        """When RESEND_FROM is empty the hardcoded default is used."""
        mock_client = self._call_send({"RESEND_FROM": ""})
        _, kwargs = mock_client.post.call_args
        self.assertEqual(kwargs["json"]["from"], "onboarding@resend.dev")


# ---------------------------------------------------------------------------
# Class 3 — failure paths
# ---------------------------------------------------------------------------

class ResendSenderFailureTests(unittest.TestCase):
    """Error-handling tests for send_via_resend."""

    _BASE_ENV = {"RESEND_API_KEY": "test-key", "RESEND_FROM": ""}

    def test_http_4xx_does_not_raise(self):
        """A 422 response must be logged, not re-raised."""
        with patch.dict(os.environ, self._BASE_ENV, clear=False):
            with patch("httpx.Client") as mock_cls:
                mock_client = MagicMock()
                mock_cls.return_value.__enter__.return_value = mock_client
                mock_client.post.return_value = _make_response(422)

                from app.services.email_sender_resend import send_via_resend
                # Should not raise
                try:
                    send_via_resend("x@x.com", "sub", "body")
                except Exception as exc:  # pragma: no cover
                    self.fail(f"send_via_resend raised unexpectedly: {exc}")

    def test_network_error_propagates(self):
        """A network-level exception from post() must propagate to the caller."""
        with patch.dict(os.environ, self._BASE_ENV, clear=False):
            with patch("httpx.Client") as mock_cls:
                mock_client = MagicMock()
                mock_cls.return_value.__enter__.return_value = mock_client
                mock_client.post.side_effect = Exception("connection error")

                from app.services.email_sender_resend import send_via_resend
                with self.assertRaises(Exception, msg="connection error"):
                    send_via_resend("x@x.com", "sub", "body")


if __name__ == "__main__":
    unittest.main()
