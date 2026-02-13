from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import admin_api
from app.main import app


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table_name: str):
        self.table_name = table_name

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def maybe_single(self):
        return self

    def insert(self, *_args, **_kwargs):
        return self

    def update(self, *_args, **_kwargs):
        return self

    def execute(self):
        if self.table_name == "triage_sessions":
            return _FakeResponse({"id": "session-1"})
        return _FakeResponse({"ok": True})


class _FakeSupabase:
    def table(self, table_name: str):
        return _FakeQuery(table_name)


class AdminTuningAuthTests(unittest.TestCase):
    def _post_from_session(self, headers: dict[str, str] | None = None):
        with TestClient(app) as client:
            return client.post(
                "/v1/admin/tuning-tasks/from-session/session-1",
                headers=headers or {},
            )

    def test_returns_503_when_admin_key_missing(self):
        with patch("app.admin_auth.settings.ADMIN_API_KEY", ""):
            response = self._post_from_session(headers={"x-admin-key": "anything"})

        self.assertEqual(response.status_code, 503)
        self.assertIn("ADMIN_API_KEY", response.json().get("detail", ""))

    def test_returns_401_when_header_missing(self):
        with patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"):
            response = self._post_from_session()

        self.assertEqual(response.status_code, 401)

    def test_returns_401_when_header_invalid(self):
        with patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"):
            response = self._post_from_session(headers={"x-admin-key": "wrong"})

        self.assertEqual(response.status_code, 401)

    def test_allows_request_with_valid_header(self):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_api, "get_supabase", return_value=_FakeSupabase()) as mocked_get_supabase,
            patch.object(admin_api, "build_tuning_tasks_from_session", return_value=[]),
        ):
            response = self._post_from_session(headers={"x-admin-key": "secret"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("created"), 0)
        self.assertTrue(mocked_get_supabase.called)


if __name__ == "__main__":
    unittest.main()
