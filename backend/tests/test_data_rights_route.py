"""Unit tests for DELETE /v1/me/sessions/{session_id} — KVKK/GDPR.

This endpoint is the user-facing "right to erasure" surface. A broken
implementation here is both a legal risk (we'd be failing a GDPR Art.17
obligation) and a trust risk (user deletes session, the app says "ok",
but the row actually still carries PII). Prior coverage was 20%; the
404/idempotent/partial-failure/500 branches weren't exercised, which
is exactly where a regression would hide.

Test strategy:
    - Use `patch("app.db.supabase", fake)` because the route imports
      `from app.db import supabase` lazily inside the handler (to keep
      `app.main` CI-importable without SUPABASE env vars — see the
      _LazySupabase note in MEMORY.md).
    - The fake is filter-aware: each `.eq()` narrows an in-memory
      row set, so a regression that drops a filter (e.g. forgets to
      `.eq("id", session_id)` on the tombstone UPDATE) shows up as
      "all rows got nulled" instead of passing silently.
    - Error injection: override specific table/mode pairs to raise,
      so we can prove the try/except branches still produce the
      documented receipt shape.
"""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


# ─── filter-aware fake supabase ───────────────────────────────────────

_VALID_SESSION_ID = "12345678-1234-1234-1234-123456789abc"  # 36-char UUID-ish


class _FakeResponse:
    """Mirrors the attribute shape of postgrest's APIResponse."""

    def __init__(self, data: Any):
        self.data = data


class _FakeQuery:
    """Builder that records filters and replays them at `.execute()`.

    Supports the three shapes the data_rights handler uses:
      .table(T).select(cols).eq(c,v).maybe_single().execute()
      .table(T).delete().eq(c,v).execute()
      .table(T).update(vals).eq(c,v).execute()

    For a regression that drops `.eq("id", session_id)` on the tombstone
    UPDATE, the update would then match every row and this fake surfaces
    that by recording the filter set and letting assertions check it.
    """

    def __init__(
        self,
        table_name: str,
        rows_by_table: dict,
        mutations_log: list,
        fail_on: set,
    ):
        self.table_name = table_name
        self.rows_by_table = rows_by_table
        self.mutations_log = mutations_log
        self.fail_on = fail_on
        self.mode: str | None = None
        self.update_values: dict | None = None
        self.eq_filters: list[tuple[str, Any]] = []
        self.maybe_single_flag = False

    def select(self, *_args, **_kwargs):
        self.mode = "select"
        return self

    def update(self, values: dict):
        self.mode = "update"
        self.update_values = values
        return self

    def delete(self):
        self.mode = "delete"
        return self

    def eq(self, column: str, value: Any):
        self.eq_filters.append((column, value))
        return self

    def maybe_single(self):
        self.maybe_single_flag = True
        return self

    def _matches(self, row: dict) -> bool:
        return all(row.get(c) == v for c, v in self.eq_filters)

    def execute(self):
        key = (self.table_name, self.mode)
        if key in self.fail_on:
            raise RuntimeError(f"injected failure on {key}")

        rows = self.rows_by_table.get(self.table_name, [])
        matched = [r for r in rows if self._matches(r)]

        if self.mode == "select":
            if self.maybe_single_flag:
                return _FakeResponse(matched[0] if matched else None)
            return _FakeResponse(matched)

        if self.mode == "delete":
            remaining = [r for r in rows if not self._matches(r)]
            self.rows_by_table[self.table_name] = remaining
            self.mutations_log.append(
                ("delete", self.table_name, dict(self.eq_filters))
            )
            return _FakeResponse(matched)

        if self.mode == "update":
            for row in matched:
                row.update(self.update_values or {})
            self.mutations_log.append(
                (
                    "update",
                    self.table_name,
                    dict(self.eq_filters),
                    dict(self.update_values or {}),
                )
            )
            return _FakeResponse(matched)

        raise AssertionError(f"unexpected mode: {self.mode}")


class _FakeSupabase:
    def __init__(self, rows_by_table: dict, fail_on: set | None = None):
        self.rows_by_table = rows_by_table
        self.mutations_log: list = []
        self.fail_on = fail_on or set()

    def table(self, name: str):
        return _FakeQuery(
            name, self.rows_by_table, self.mutations_log, self.fail_on
        )


# ─── tests ────────────────────────────────────────────────────────────


class SessionIdShapeTests(unittest.TestCase):
    """Guard clause: reject malformed session_ids before touching DB.

    Prevents the handler from paying a round-trip for obviously-bogus
    inputs, and gives the mobile app a clean 400 distinct from 404.
    """

    def setUp(self):
        self.client = TestClient(app)

    def test_rejects_too_short_session_id(self):
        # 10 chars — shorter than 32.
        fake = _FakeSupabase({"triage_sessions": []})
        with patch("app.db.supabase", fake):
            r = self.client.delete("/v1/me/sessions/abcd1234xy")
        self.assertEqual(r.status_code, 400)
        self.assertIn("malformed", r.json()["detail"])
        # No table calls — handler bailed before touching DB.
        self.assertEqual(fake.mutations_log, [])

    def test_rejects_too_long_session_id(self):
        # 50 chars — longer than 40.
        fake = _FakeSupabase({"triage_sessions": []})
        long_id = "x" * 50
        with patch("app.db.supabase", fake):
            r = self.client.delete(f"/v1/me/sessions/{long_id}")
        self.assertEqual(r.status_code, 400)

    def test_accepts_boundary_length_32(self):
        # Exactly 32 chars: should pass the shape check and then 404
        # because the session doesn't exist.
        fake = _FakeSupabase({"triage_sessions": []})
        boundary = "a" * 32
        with patch("app.db.supabase", fake):
            r = self.client.delete(f"/v1/me/sessions/{boundary}")
        self.assertEqual(r.status_code, 404)

    def test_accepts_boundary_length_40(self):
        fake = _FakeSupabase({"triage_sessions": []})
        boundary = "a" * 40
        with patch("app.db.supabase", fake):
            r = self.client.delete(f"/v1/me/sessions/{boundary}")
        self.assertEqual(r.status_code, 404)


class SessionNotFoundTests(unittest.TestCase):
    """If the session isn't in triage_sessions, return 404 — don't
    silently 200 "ok" as if we deleted something."""

    def setUp(self):
        self.client = TestClient(app)

    def test_returns_404_when_session_missing(self):
        fake = _FakeSupabase({"triage_sessions": []})
        with patch("app.db.supabase", fake):
            r = self.client.delete(f"/v1/me/sessions/{_VALID_SESSION_ID}")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["detail"], "session not found")
        # No mutations — we only read.
        deletes_or_updates = [m for m in fake.mutations_log if m[0] != "select"]
        self.assertEqual(deletes_or_updates, [])


class IdempotentDoubleDeleteTests(unittest.TestCase):
    """Already-tombstoned rows should 200 with `already_deleted: true`.

    The mobile app might retry a delete after a flaky connection. A
    second call that 500s or re-wipes would confuse the user; the
    documented contract is "idempotent no-op".
    """

    def setUp(self):
        self.client = TestClient(app)

    def test_returns_200_noop_on_already_tombstoned(self):
        fake = _FakeSupabase(
            {
                "triage_sessions": [
                    {
                        "id": _VALID_SESSION_ID,
                        "deleted_at": "2026-04-20T12:00:00Z",
                    }
                ]
            }
        )
        with patch("app.db.supabase", fake):
            r = self.client.delete(f"/v1/me/sessions/{_VALID_SESSION_ID}")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["already_deleted"])
        self.assertEqual(body["session_id"], _VALID_SESSION_ID)
        # Crucially, no derived deletes or further update when already
        # tombstoned — we short-circuit.
        mutations = [m for m in fake.mutations_log if m[0] in ("update", "delete")]
        self.assertEqual(mutations, [])


class HappyPathDeleteTests(unittest.TestCase):
    """Full-tombstone flow: delete derived rows, null the session row,
    stamp deleted_at + deleted_reason."""

    def setUp(self):
        self.client = TestClient(app)

    def test_deletes_derived_and_tombstones_session(self):
        rows = {
            "triage_sessions": [
                {
                    "id": _VALID_SESSION_ID,
                    "deleted_at": None,
                    "input_text": "Başım ağrıyor",
                    "answers": {"q1": "evet"},
                    "meta": {"lang": "tr"},
                }
            ],
            "triage_events": [
                {"session_id": _VALID_SESSION_ID, "turn": 1},
                {"session_id": _VALID_SESSION_ID, "turn": 2},
                {"session_id": "other-session", "turn": 1},
            ],
            "llm_calls": [
                {"session_id": _VALID_SESSION_ID, "provider": "openai"}
            ],
            "triage_feedback": [
                {"session_id": _VALID_SESSION_ID, "rating": "up"}
            ],
        }
        fake = _FakeSupabase(rows)
        with patch("app.db.supabase", fake):
            r = self.client.delete(f"/v1/me/sessions/{_VALID_SESSION_ID}")

        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["session_id"], _VALID_SESSION_ID)
        self.assertEqual(body["derived_deleted"]["triage_events"], 2)
        self.assertEqual(body["derived_deleted"]["llm_calls"], 1)
        self.assertEqual(body["derived_deleted"]["triage_feedback"], 1)

        # Cross-session bleed check: other-session event is untouched.
        self.assertEqual(
            len([r for r in rows["triage_events"] if r.get("session_id") == "other-session"]),
            1,
        )
        # Target session's derived rows all gone.
        self.assertEqual(
            [r for r in rows["triage_events"] if r.get("session_id") == _VALID_SESSION_ID],
            [],
        )

        # Session row was updated (not deleted); verify tombstone fields.
        session = rows["triage_sessions"][0]
        self.assertIsNone(session["input_text"])
        self.assertIsNone(session["answers"])
        self.assertIsNone(session["meta"])
        self.assertEqual(session["deleted_reason"], "user_request")
        self.assertIsNotNone(session["deleted_at"])

    def test_tombstone_update_is_scoped_to_the_requested_session(self):
        # Defense-in-depth: if a regression removed `.eq("id", ...)` on
        # the tombstone UPDATE, it would null *every* triage_sessions
        # row. This test sets up two rows and verifies only the target
        # is touched.
        other_id = "ffffffff-ffff-ffff-ffff-ffffffffffff"
        rows = {
            "triage_sessions": [
                {
                    "id": _VALID_SESSION_ID,
                    "deleted_at": None,
                    "input_text": "hedef",
                },
                {
                    "id": other_id,
                    "deleted_at": None,
                    "input_text": "komşu — dokunulmamalı",
                },
            ],
            "triage_events": [],
            "llm_calls": [],
            "triage_feedback": [],
        }
        fake = _FakeSupabase(rows)
        with patch("app.db.supabase", fake):
            r = self.client.delete(f"/v1/me/sessions/{_VALID_SESSION_ID}")

        self.assertEqual(r.status_code, 200)
        # Target: nulled.
        target = next(r for r in rows["triage_sessions"] if r["id"] == _VALID_SESSION_ID)
        self.assertIsNone(target["input_text"])
        # Neighbor: untouched.
        neighbor = next(r for r in rows["triage_sessions"] if r["id"] == other_id)
        self.assertEqual(neighbor["input_text"], "komşu — dokunulmamalı")
        self.assertIsNone(neighbor.get("deleted_at"))


class DerivedDeletePartialFailureTests(unittest.TestCase):
    """If one of the derived DELETEs fails (e.g. transient network),
    the handler should log + mark -1 in the receipt and still proceed
    to tombstone the session row. Otherwise a flaky derived delete
    leaves PII in `triage_sessions.input_text` forever."""

    def setUp(self):
        self.client = TestClient(app)

    def test_llm_calls_delete_failure_does_not_abort_tombstone(self):
        rows = {
            "triage_sessions": [
                {"id": _VALID_SESSION_ID, "deleted_at": None, "input_text": "x"}
            ],
            "triage_events": [{"session_id": _VALID_SESSION_ID}],
            "llm_calls": [{"session_id": _VALID_SESSION_ID}],
            "triage_feedback": [],
        }
        fake = _FakeSupabase(
            rows,
            fail_on={("llm_calls", "delete")},
        )
        with patch("app.db.supabase", fake):
            r = self.client.delete(f"/v1/me/sessions/{_VALID_SESSION_ID}")

        self.assertEqual(r.status_code, 200)
        body = r.json()
        # Failed derived table marked with -1.
        self.assertEqual(body["derived_deleted"]["llm_calls"], -1)
        # Sibling tables still processed.
        self.assertEqual(body["derived_deleted"]["triage_events"], 1)
        self.assertEqual(body["derived_deleted"]["triage_feedback"], 0)
        # Most important: session row *was* tombstoned.
        self.assertIsNone(rows["triage_sessions"][0]["input_text"])
        self.assertEqual(
            rows["triage_sessions"][0]["deleted_reason"], "user_request"
        )


class TombstoneFailureTests(unittest.TestCase):
    """If the session UPDATE itself fails, return 500 — we can't lie
    and say ok=true when the user's input_text is still in the DB."""

    def setUp(self):
        self.client = TestClient(app)

    def test_tombstone_update_failure_returns_500(self):
        rows = {
            "triage_sessions": [
                {"id": _VALID_SESSION_ID, "deleted_at": None, "input_text": "x"}
            ],
            "triage_events": [],
            "llm_calls": [],
            "triage_feedback": [],
        }
        fake = _FakeSupabase(
            rows,
            fail_on={("triage_sessions", "update")},
        )
        with patch("app.db.supabase", fake):
            r = self.client.delete(f"/v1/me/sessions/{_VALID_SESSION_ID}")

        self.assertEqual(r.status_code, 500)
        self.assertIn("tombstone failed", r.json()["detail"])
        # Since the UPDATE raised, the row keeps its input_text — the
        # 500 tells the caller to retry.
        self.assertEqual(rows["triage_sessions"][0]["input_text"], "x")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
