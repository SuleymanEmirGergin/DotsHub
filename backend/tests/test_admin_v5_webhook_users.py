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
    def __init__(self, table_name: str, rows: list[dict]):
        self.table_name = table_name
        self.rows = rows
        self.eq_filters: list[tuple[str, object]] = []
        self.in_filters: list[tuple[str, set[object]]] = []
        self._limit: int | None = None
        self._upsert_data = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        if _args:
            col = str(_args[0])
            val = _args[1] if len(_args) > 1 else None
            self.eq_filters.append((col, val))
        return self

    def in_(self, *_args, **_kwargs):
        if _args:
            col = str(_args[0])
            vals = set(_args[1]) if len(_args) > 1 else set()
            self.in_filters.append((col, vals))
        return self

    def gte(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        if _args:
            self._limit = int(_args[0])
        return self

    def delete(self):
        return self

    def upsert(self, data, **_kwargs):
        self._upsert_data = data
        return self

    def execute(self):
        if self._upsert_data is not None:
            data = self._upsert_data
            result = [data] if isinstance(data, dict) else data
            return _FakeExecute(result)
        data = list(self.rows)
        for col, val in self.eq_filters:
            data = [row for row in data if row.get(col) == val]
        for col, vals in self.in_filters:
            data = [row for row in data if row.get(col) in vals]
        if self._limit is not None:
            data = data[: self._limit]
        return _FakeExecute(data)


class _FakeSupabase:
    def __init__(self):
        self._admin_users: list[dict] = [
            {"id": "1", "user_id": "u-1", "email": "admin@example.com", "role": "admin", "created_at": "2026-01-01T00:00:00Z"},
        ]

    def table(self, table_name: str):
        if table_name == "admin_users":
            return _FakeQuery(table_name, self._admin_users)
        return _FakeQuery(table_name, [])


class WebhookStatusTests(unittest.TestCase):
    """Tests for GET /admin/webhook/status."""

    def _get_status(self, headers: dict[str, str] | None = None):
        with TestClient(app) as client:
            return client.get("/admin/webhook/status", headers=headers or {})

    def test_webhook_status_requires_admin(self):
        with patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"):
            r = self._get_status()
        self.assertEqual(r.status_code, 401)

    def test_webhook_status_returns_shape(self):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch("app.core.config.settings.WEBHOOK_ENABLED", True),
            patch("app.core.config.settings.WEBHOOK_SLACK_URL", "https://hooks.slack.com/test"),
            patch("app.core.config.settings.WEBHOOK_DISCORD_URL", ""),
        ):
            r = self._get_status(headers={"x-admin-key": "secret"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("enabled", body)
        self.assertIn("channels", body)
        self.assertIn("slack", body["channels"])
        self.assertIn("discord", body["channels"])


class WebhookTestTests(unittest.TestCase):
    """Tests for POST /admin/webhook/test."""

    def _post_test(self, headers: dict[str, str] | None = None):
        with TestClient(app) as client:
            return client.post("/admin/webhook/test", headers=headers or {})

    def test_webhook_test_requires_admin(self):
        with patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"):
            r = self._post_test()
        self.assertEqual(r.status_code, 401)

    def test_webhook_test_calls_notifier(self):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch("app.notifier.send_test", return_value={"slack": "ok"}),
        ):
            r = self._post_test(headers={"x-admin-key": "secret"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("results", body)


class AddUserTests(unittest.TestCase):
    """Tests for POST /admin/users."""

    def _post_user(self, headers: dict[str, str] | None = None, params: dict | None = None):
        params = params or {"email": "new@example.com", "user_id": "u-new", "role": "admin"}
        with TestClient(app) as client:
            return client.post("/admin/users", headers=headers or {}, params=params)

    def test_add_user_requires_admin(self):
        with patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"):
            r = self._post_user()
        self.assertEqual(r.status_code, 401)

    def test_add_user_with_valid_key(self):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", _FakeSupabase()),
        ):
            r = self._post_user(headers={"x-admin-key": "secret"})
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertTrue(body.get("ok"))


class DeleteUserTests(unittest.TestCase):
    """Tests for DELETE /admin/users/{user_id}."""

    def _delete_user(self, user_id: str = "u-1", headers: dict[str, str] | None = None):
        with TestClient(app) as client:
            return client.delete(f"/admin/users/{user_id}", headers=headers or {})

    def test_delete_user_requires_admin(self):
        with patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"):
            r = self._delete_user()
        self.assertEqual(r.status_code, 401)

    def test_delete_user_with_valid_key(self):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", _FakeSupabase()),
        ):
            r = self._delete_user(headers={"x-admin-key": "secret"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body.get("ok"))


if __name__ == "__main__":
    unittest.main()
