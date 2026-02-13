from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import admin_v5
from app.main import app


class _FakeExecute:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table_name: str):
        self.table_name = table_name

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        if self.table_name == "triage_sessions":
            return _FakeExecute([])
        return _FakeExecute([])


class _FakeSupabase:
    def table(self, table_name: str):
        return _FakeQuery(table_name)


class AdminV5AuthTests(unittest.TestCase):
    def _get_sessions(self, headers: dict[str, str] | None = None):
        with TestClient(app) as client:
            return client.get("/admin/sessions?limit=1", headers=headers or {})

    def test_returns_503_when_admin_key_missing(self):
        with patch("app.admin_auth.settings.ADMIN_API_KEY", ""):
            response = self._get_sessions(headers={"x-admin-key": "anything"})

        self.assertEqual(response.status_code, 503)

    def test_returns_401_when_header_missing(self):
        with patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"):
            response = self._get_sessions()

        self.assertEqual(response.status_code, 401)

    def test_returns_401_when_header_invalid(self):
        with patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"):
            response = self._get_sessions(headers={"x-admin-key": "wrong"})

        self.assertEqual(response.status_code, 401)

    def test_allows_request_with_valid_header(self):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", _FakeSupabase()),
        ):
            response = self._get_sessions(headers={"x-admin-key": "secret"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("items", response.json())


if __name__ == "__main__":
    unittest.main()
