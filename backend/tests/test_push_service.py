"""Tests for push token service (app.push) and push-token route error handling."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.push import register_token, unregister_token

_VALID_REGISTER_BODY = {
    "expo_push_token": "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
    "device_id": "device-abc-123",
    "platform": "ios",
    "locale": "tr-TR",
}

_VALID_DELETE_BODY = {
    "device_id": "device-abc-123",
}


class RegisterTokenServiceTests(unittest.TestCase):
    """Unit tests for app.push.register_token / unregister_token."""

    def _make_mock_supabase(self, execute_return=None, execute_side_effect=None):
        """Return a patched supabase mock with a fluent table/upsert/update/eq/execute chain."""
        mock_sb = MagicMock()
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table
        mock_table.upsert.return_value = mock_table
        mock_table.update.return_value = mock_table
        mock_table.eq.return_value = mock_table
        if execute_side_effect is not None:
            mock_table.execute.side_effect = execute_side_effect
        else:
            mock_table.execute.return_value = execute_return
        return mock_sb

    # ------------------------------------------------------------------
    # 1. register_token — happy path
    # ------------------------------------------------------------------
    def test_register_token_success(self):
        execute_result = MagicMock(data=[{"id": 1}])
        mock_sb = self._make_mock_supabase(execute_return=execute_result)

        with patch("app.push.supabase", mock_sb):
            result = register_token(
                device_id="device-1",
                expo_token="ExponentPushToken[abc]",
                platform="ios",
                locale="tr-TR",
            )

        self.assertEqual(result, {"ok": True, "data": [{"id": 1}]})

    # ------------------------------------------------------------------
    # 2. register_token — Supabase exception propagates
    # ------------------------------------------------------------------
    def test_register_token_supabase_exception_propagates(self):
        mock_sb = self._make_mock_supabase(execute_side_effect=RuntimeError("DB down"))

        with patch("app.push.supabase", mock_sb):
            with self.assertRaises(RuntimeError) as ctx:
                register_token(
                    device_id="device-2",
                    expo_token="ExponentPushToken[abc]",
                    platform="android",
                    locale="tr-TR",
                )

        self.assertIn("DB down", str(ctx.exception))

    # ------------------------------------------------------------------
    # 3. unregister_token — Supabase exception propagates
    # ------------------------------------------------------------------
    def test_unregister_token_supabase_exception_propagates(self):
        mock_sb = self._make_mock_supabase(execute_side_effect=RuntimeError("DB down"))

        with patch("app.push.supabase", mock_sb):
            with self.assertRaises(RuntimeError) as ctx:
                unregister_token("device-x")

        self.assertIn("DB down", str(ctx.exception))


class PushTokenRouteErrorHandlingTests(unittest.TestCase):
    """HTTP route tests for fail-open / fail-closed push-token behavior."""

    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    # ------------------------------------------------------------------
    # 4. Fail-open: APP_ENV=test -> exception swallowed, HTTP 201 returned
    # ------------------------------------------------------------------
    def test_register_fail_open_returns_201(self):
        with patch("app.push.register_token", side_effect=RuntimeError("Supabase down")):
            response = self.client.post(
                "/v1/triage/push-token",
                json=_VALID_REGISTER_BODY,
            )

        self.assertEqual(response.status_code, 201)

    # ------------------------------------------------------------------
    # 5. Fail-closed: APP_ENV=production -> HTTP 503 raised
    # ------------------------------------------------------------------
    def test_register_fail_closed_returns_503(self):
        with patch.object(settings, "APP_ENV", "production"):
            with patch("app.push.register_token", side_effect=RuntimeError("Supabase down")):
                response = self.client.post(
                    "/v1/triage/push-token",
                    json=_VALID_REGISTER_BODY,
                )

        self.assertEqual(response.status_code, 503)

    # ------------------------------------------------------------------
    # 6. Fail-open DELETE: APP_ENV=test -> exception swallowed, HTTP 200 returned
    # ------------------------------------------------------------------
    def test_unregister_fail_open_returns_200(self):
        with patch("app.push.unregister_token", side_effect=RuntimeError("Supabase down")):
            response = self.client.request(
                "DELETE",
                "/v1/triage/push-token",
                json=_VALID_DELETE_BODY,
            )

        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
