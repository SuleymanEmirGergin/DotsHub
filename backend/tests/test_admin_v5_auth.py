from __future__ import annotations

import unittest
from typing import Optional
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

    def execute(self):
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
        self._sessions = [
            {
                "id": "session-1",
                "session_id": "session-1",
                "created_at": "2026-02-10T10:00:00Z",
                "updated_at": "2026-02-10T10:05:00Z",
                "envelope_type": "RESULT",
                "stop_reason": "min_expected_gain",
                "confidence_0_1": 0.42,
                "recommended_specialty_tr": "Noroloji",
                "recommended_specialty_id": "neurology",
                "extracted_canonicals": ["headache"],
                "meta": {"risk": {"level": "LOW", "score_0_1": 0.2}},
            },
            {
                "id": "session-2",
                "session_id": "session-2",
                "created_at": "2026-02-11T12:00:00Z",
                "updated_at": "2026-02-11T12:02:00Z",
                "envelope_type": "EMERGENCY",
                "stop_reason": "emergency_detected",
                "confidence_0_1": 0.9,
                "recommended_specialty_tr": "Acil",
                "recommended_specialty_id": "emergency",
                "extracted_canonicals": ["chest_pain"],
                "meta": {"risk_level": "HIGH", "risk_score_0_1": 0.95},
            },
        ]
        self._feedback = [
            {
                "id": "fb-1",
                "session_id": "session-1",
                "rating": "down",
                "comment": "Yanlış branş önerisi",
                "user_selected_specialty_id": None,
                "created_at": "2026-02-12T09:00:00Z",
            },
            {
                "id": "fb-2",
                "session_id": "session-2",
                "rating": "up",
                "comment": None,
                "user_selected_specialty_id": None,
                "created_at": "2026-02-12T09:10:00Z",
            },
        ]

    def table(self, table_name: str):
        if table_name == "triage_sessions":
            return _FakeQuery(table_name, self._sessions)
        if table_name == "triage_feedback":
            return _FakeQuery(table_name, self._feedback)
        return _FakeQuery(table_name, [])


class AdminV5AuthTests(unittest.TestCase):
    # admin_v5_router is mounted at /v1 (main.py) so the admin_v5
    # endpoints (which carry their own prefix="/admin") land at
    # /v1/admin/*. The /v1 prefix was added so the admin rate-limit
    # middleware (which gates /v1/admin/*) actually covers these
    # routes — before, they were at /admin/* and bypassed the limit.
    def _get_sessions(self, headers: dict[str, str] | None = None):
        with TestClient(app) as client:
            return client.get("/v1/admin/sessions?limit=1", headers=headers or {})

    def _get_feedback_stats(self, headers: dict[str, str] | None = None):
        with TestClient(app) as client:
            return client.get("/v1/admin/feedback/stats?days=30", headers=headers or {})

    def _get_feedback_list(self, headers: dict[str, str] | None = None):
        with TestClient(app) as client:
            return client.get("/v1/admin/feedback/list?limit=20", headers=headers or {})

    def _get_daily_summary(self, headers: dict[str, str] | None = None):
        with TestClient(app) as client:
            return client.get("/v1/admin/stats/daily-summary?days=30", headers=headers or {})

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

    def test_feedback_stats_requires_admin_header(self):
        with patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"):
            response = self._get_feedback_stats()

        self.assertEqual(response.status_code, 401)

    def test_feedback_endpoints_with_valid_header(self):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", _FakeSupabase()),
        ):
            stats_resp = self._get_feedback_stats(headers={"x-admin-key": "secret"})
            list_resp = self._get_feedback_list(headers={"x-admin-key": "secret"})

        self.assertEqual(stats_resp.status_code, 200)
        stats = stats_resp.json()
        self.assertEqual(stats.get("total"), 2)
        self.assertIn("trend", stats)
        self.assertIn("top_down_specialties", stats)

        self.assertEqual(list_resp.status_code, 200)
        data = list_resp.json()
        self.assertEqual(data.get("count"), 2)
        self.assertTrue(data.get("items"))
        self.assertEqual(data["items"][0].get("session_specialty"), "Noroloji")


    def test_daily_summary_funnel_counts(self):
        """Funnel aggregates envelope_type + feedback join correctly.

        Fixture has 2 sessions (RESULT + EMERGENCY) and 2 feedback rows
        (one per session). Expected funnel:
          started=2, questioned=2 (cumulative; both resulted passed through
          Q&A), resulted=2 (RESULT+EMERGENCY+SAME_DAY), feedback=2.
        Also verifies by_envelope exposes the raw terminal-envelope tally.
        """
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", _FakeSupabase()),
        ):
            resp = self._get_daily_summary(headers={"x-admin-key": "secret"})

        self.assertEqual(resp.status_code, 200)
        body = resp.json()

        self.assertIn("funnel", body)
        self.assertEqual(body["funnel"]["started"], 2)
        self.assertEqual(body["funnel"]["questioned"], 2)
        self.assertEqual(body["funnel"]["resulted"], 2)
        self.assertEqual(body["funnel"]["feedback"], 2)

        self.assertIn("by_envelope", body)
        self.assertEqual(body["by_envelope"].get("RESULT"), 1)
        self.assertEqual(body["by_envelope"].get("EMERGENCY"), 1)


# ─── Admin user management tests ───────────────────────────────────
#
# Covers the post-fix invariants for /admin/users*:
#   - list uses attribute access (prior ``supabase()`` call was a
#     TypeError at request time)
#   - invite resolves auth user by email then upserts
#   - patch updates role (and rejects invalid role)
#   - delete runs
# The user-management fake keeps a mutable admin_users table so we
# can assert the upsert/update/delete mutations.


class _UsersFakeQuery:
    def __init__(self, store: "_UsersFakeSupabase", table_name: str):
        self._store = store
        self.table_name = table_name
        self._mode: Optional[str] = None  # type: ignore[name-defined]
        self._payload = None
        self._on_conflict = None
        self._eq_filters: list = []

    def select(self, *_a, **_kw):
        self._mode = "select"
        return self

    def upsert(self, payload, on_conflict=None):
        self._mode = "upsert"
        self._payload = payload
        self._on_conflict = on_conflict
        return self

    def update(self, payload):
        self._mode = "update"
        self._payload = payload
        return self

    def delete(self):
        self._mode = "delete"
        return self

    def eq(self, col, val):
        self._eq_filters.append((col, val))
        return self

    def order(self, *_a, **_kw):
        return self

    def execute(self):
        rows = self._store.tables.setdefault(self.table_name, [])
        if self._mode == "select":
            return _FakeExecute(list(rows))
        if self._mode == "upsert":
            assert self._on_conflict == "user_id"
            key = self._payload["user_id"]
            existing_idx = next(
                (i for i, r in enumerate(rows) if r.get("user_id") == key), None
            )
            if existing_idx is not None:
                rows[existing_idx].update(self._payload)
                return _FakeExecute([rows[existing_idx]])
            rows.append(dict(self._payload))
            return _FakeExecute([rows[-1]])
        if self._mode == "update":
            updated = []
            for r in rows:
                if all(r.get(c) == v for c, v in self._eq_filters):
                    r.update(self._payload)
                    updated.append(r)
            return _FakeExecute(updated)
        if self._mode == "delete":
            kept = [r for r in rows if not all(r.get(c) == v for c, v in self._eq_filters)]
            removed = len(rows) - len(kept)
            self._store.tables[self.table_name] = kept
            return _FakeExecute([{"removed": removed}])
        return _FakeExecute([])


class _FakeAuthAdmin:
    """Minimal stand-in for supabase.auth.admin.list_users().

    Returns the configured auth users on page=1 and an empty list on
    later pages, matching the "fewer than per_page → stop" guard in
    invite_admin_user.
    """

    def __init__(self, users: list[dict]):
        self._users = users

    def list_users(self, page: int = 1, per_page: int = 100):
        if page == 1:
            return {"users": self._users}
        return {"users": []}


class _FakeAuth:
    def __init__(self, users: list[dict]):
        self.admin = _FakeAuthAdmin(users)


class _UsersFakeSupabase:
    def __init__(self, admin_users: list[dict], auth_users: list[dict]):
        self.tables: dict[str, list[dict]] = {"admin_users": list(admin_users)}
        self.auth = _FakeAuth(auth_users)

    def table(self, name: str):
        return _UsersFakeQuery(self, name)


class AdminUserManagementTests(unittest.TestCase):
    def _client(self):
        return TestClient(app)

    def test_list_admin_users_uses_attribute_access(self):
        """Regression: prior code called supabase() → TypeError."""
        fake = _UsersFakeSupabase(
            admin_users=[
                {
                    "id": "row-1",
                    "user_id": "u-1",
                    "email": "a@ex.com",
                    "role": "super_admin",
                    "created_at": "2026-04-20T10:00:00Z",
                },
            ],
            auth_users=[],
        )
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", fake),
        ):
            resp = self._client().get(
                "/v1/admin/users", headers={"x-admin-key": "secret"}
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body["users"]), 1)
        self.assertEqual(body["users"][0]["email"], "a@ex.com")

    def test_invite_resolves_email_and_upserts(self):
        fake = _UsersFakeSupabase(
            admin_users=[],
            auth_users=[
                {"id": "auth-99", "email": "Invitee@Example.com"},
                {"id": "auth-42", "email": "other@example.com"},
            ],
        )
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", fake),
        ):
            resp = self._client().post(
                "/v1/admin/users/invite?email=invitee@example.com&role=admin",
                headers={"x-admin-key": "secret"},
            )

        self.assertEqual(resp.status_code, 200)
        rows = fake.tables["admin_users"]
        self.assertEqual(len(rows), 1)
        # Canonical email comes from the auth record (preserves
        # original case), and user_id is the auth user's id.
        self.assertEqual(rows[0]["user_id"], "auth-99")
        self.assertEqual(rows[0]["email"], "Invitee@Example.com")
        self.assertEqual(rows[0]["role"], "admin")

    def test_invite_returns_409_when_email_not_found(self):
        fake = _UsersFakeSupabase(
            admin_users=[],
            auth_users=[{"id": "auth-1", "email": "someone@else.com"}],
        )
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", fake),
        ):
            resp = self._client().post(
                "/v1/admin/users/invite?email=missing@example.com",
                headers={"x-admin-key": "secret"},
            )

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(fake.tables["admin_users"], [])

    def test_invite_rejects_invalid_role(self):
        fake = _UsersFakeSupabase(
            admin_users=[],
            auth_users=[{"id": "auth-1", "email": "a@b.com"}],
        )
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", fake),
        ):
            resp = self._client().post(
                "/v1/admin/users/invite?email=a@b.com&role=owner",
                headers={"x-admin-key": "secret"},
            )
        self.assertEqual(resp.status_code, 400)

    def test_patch_user_updates_role(self):
        fake = _UsersFakeSupabase(
            admin_users=[
                {
                    "id": "row-1",
                    "user_id": "u-1",
                    "email": "a@ex.com",
                    "role": "admin",
                    "created_at": "2026-04-20T10:00:00Z",
                },
            ],
            auth_users=[],
        )
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", fake),
        ):
            resp = self._client().patch(
                "/v1/admin/users/u-1?role=super_admin",
                headers={"x-admin-key": "secret"},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(fake.tables["admin_users"][0]["role"], "super_admin")

    def test_patch_user_404_when_missing(self):
        fake = _UsersFakeSupabase(admin_users=[], auth_users=[])
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", fake),
        ):
            resp = self._client().patch(
                "/v1/admin/users/nope?role=admin",
                headers={"x-admin-key": "secret"},
            )
        self.assertEqual(resp.status_code, 404)

    def test_delete_user_removes_row(self):
        fake = _UsersFakeSupabase(
            admin_users=[
                {
                    "id": "row-1",
                    "user_id": "u-1",
                    "email": "a@ex.com",
                    "role": "admin",
                    "created_at": "2026-04-20T10:00:00Z",
                },
            ],
            auth_users=[],
        )
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", fake),
        ):
            resp = self._client().delete(
                "/v1/admin/users/u-1",
                headers={"x-admin-key": "secret"},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(fake.tables["admin_users"], [])


if __name__ == "__main__":
    unittest.main()
