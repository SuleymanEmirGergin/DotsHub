"""Multi-tenant / cross-device isolation test coverage.

Why this file exists:
    The production data model has three distinct tenant-scoping models,
    each enforced at a different layer:

      1. **Device-scoped** (triage_sessions, triage_feedback, push_tokens):
         the backend filters by `device_id` on reads and sets it on
         writes. There is NO database-level RLS for these tables —
         every query runs under the service-role key which bypasses
         RLS even if we added policies. The only thing keeping device
         A from reading device B's rows is that the backend's own
         query builders apply `.eq("device_id", …)` correctly.

      2. **User-scoped RLS** (admin_users): the dashboard hits Supabase
         with the caller's JWT, so the `admin_users_self_read` policy
         (user_id = auth.uid()) is the actual isolation. See
         `backend/sql/20260419_admin_users_rls.sql`.

      3. **Tenant-scoped** (curated catalog, tenant_catalog_audit):
         `tenant_id` is a path parameter; isolation is enforced at the
         route handler layer.

    Because device-scoping is 100% application-logic, a refactor that
    drops an `.eq("device_id", …)` filter silently turns every endpoint
    into a cross-device leak. The tests below pin the ACTUAL row-level
    isolation: fakes carry two devices' worth of rows, the endpoint is
    invoked under one device, and we assert the other device's rows
    never surface. This is the real "does RLS actually work" coverage
    we were missing.

    Scope of this file:
      - /v1/triage/history — cross-device read isolation
      - session_repo.create_session — write-side device_id attribution
      - push.register_token / push.unregister_token — scoped writes
      - push.send_followup_reminders — correct session→token pairing
      - admin_users RLS SQL — shape of the self-read policy
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import push
from app.api.routes import triage as triage_routes
from app.main import app


# ─── Shared fakes ────────────────────────────────────────────────────────
#
# These fakes emulate the shape of the postgrest-py fluent query builder
# (``sb.table(T).select(…).eq(col, val).execute()``) and carry multi-device
# fixtures so we can prove isolation happens at the filter layer, not by
# accident. They apply `eq`/`in` filters in-memory on execute(); anything
# the endpoint DOESN'T filter by leaks across devices and the test fails.


class _FakeExecute:
    def __init__(self, data):
        self.data = data


class _MultiDeviceFakeQuery:
    """Query fake that actually applies eq/in/limit filters in-memory.

    This is the crux of the test: the existing history-route test uses
    a fake that returns a fixed row regardless of filter, so a regression
    that drops `.eq("device_id", …)` wouldn't fail it. This fake DOES
    filter, so if the endpoint forgets device_id, the other device's
    rows will surface in the response and the assertion catches it.
    """

    def __init__(self, rows: list[dict]):
        self._rows = list(rows)
        self._filters: list[tuple] = []
        self._limit: int | None = None
        # `.not_.is_(col, "null")` chain mirrored for parity with postgrest.
        self.not_ = self

    def select(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def eq(self, col: str, val):
        self._filters.append(("eq", col, val))
        return self

    def in_(self, col: str, vals):
        self._filters.append(("in", col, set(vals)))
        return self

    def is_(self, col: str, val):
        self._filters.append(("not_is", col, val))
        return self

    def gte(self, *_a, **_kw):
        return self

    def lte(self, *_a, **_kw):
        return self

    def limit(self, n: int):
        self._limit = int(n)
        return self

    def execute(self):
        data = list(self._rows)
        for f in self._filters:
            if f[0] == "eq":
                data = [r for r in data if r.get(f[1]) == f[2]]
            elif f[0] == "in":
                data = [r for r in data if r.get(f[1]) in f[2]]
            elif f[0] == "not_is" and f[2] == "null":
                data = [r for r in data if r.get(f[1]) is not None]
        if self._limit is not None:
            data = data[: self._limit]
        return _FakeExecute(data)


class _MultiDeviceFakeSupabase:
    def __init__(self, tables: dict[str, list[dict]]):
        self._tables = tables
        self.last_insert: dict | None = None
        self.last_upsert: dict | None = None
        self.last_update_filters: list[tuple] = []
        self.last_update_payload: dict | None = None

    def table(self, name: str):
        return _MultiDeviceFakeQuery(self._tables.get(name, []))


# ─── 1. Cross-device read isolation on /v1/triage/history ──────────────


class TriageHistoryCrossDeviceIsolationTests(unittest.TestCase):
    """Device A must never see device B's sessions via /v1/triage/history.

    Regression guard: the existing history-route test pre-dates this one
    and only checks that `.eq("device_id", X)` is CALLED. It doesn't
    verify the filter is effective — a broken endpoint that stored the
    filter but then discarded it would still pass. This test uses a
    filter-aware fake and asserts on returned rows.
    """

    def _get_history(self, device_id: str):
        with TestClient(app) as client:
            return client.get(
                "/v1/triage/history?limit=50",
                headers={"x-device-id": device_id},
            )

    def test_device_a_does_not_see_device_b_sessions(self):
        sessions = [
            {
                "id": "sess-A1",
                "device_id": "device-A",
                "created_at": "2026-04-20T10:00:00Z",
                "envelope_type": "RESULT",
                "recommended_specialty_tr": "Dahiliye",
                "confidence_label_tr": "yüksek",
                "confidence_0_1": 0.9,
                "stop_reason": "confidence_reached",
            },
            {
                "id": "sess-B1",
                "device_id": "device-B",
                "created_at": "2026-04-20T11:00:00Z",
                "envelope_type": "RESULT",
                "recommended_specialty_tr": "Kardiyoloji",
                "confidence_label_tr": "yüksek",
                "confidence_0_1": 0.88,
                "stop_reason": "confidence_reached",
            },
            {
                "id": "sess-B2",
                "device_id": "device-B",
                "created_at": "2026-04-20T12:00:00Z",
                "envelope_type": "EMERGENCY",
                "recommended_specialty_tr": "Acil",
                "confidence_label_tr": "acil",
                "confidence_0_1": 0.95,
                "stop_reason": "emergency",
            },
        ]
        fake = _MultiDeviceFakeSupabase({"triage_sessions": sessions})

        with (
            patch.object(triage_routes, "_has_supabase", return_value=True),
            patch("app.supabase_client.get_supabase", return_value=fake),
        ):
            resp_a = self._get_history("device-A")
            resp_b = self._get_history("device-B")

        self.assertEqual(resp_a.status_code, 200)
        self.assertEqual(resp_b.status_code, 200)

        ids_a = {item["id"] for item in resp_a.json()["items"]}
        ids_b = {item["id"] for item in resp_b.json()["items"]}

        self.assertEqual(ids_a, {"sess-A1"})
        self.assertEqual(ids_b, {"sess-B1", "sess-B2"})
        # Belt-and-braces: assert no intersection — device A must never
        # see device B's ids and vice versa.
        self.assertTrue(ids_a.isdisjoint(ids_b))

    def test_unknown_device_id_returns_nothing_even_when_sessions_exist(self):
        sessions = [
            {
                "id": "sess-X",
                "device_id": "device-known",
                "created_at": "2026-04-20T10:00:00Z",
                "envelope_type": "RESULT",
                "recommended_specialty_tr": "Dahiliye",
                "confidence_label_tr": "orta",
                "confidence_0_1": 0.5,
                "stop_reason": "min_expected_gain",
            },
        ]
        fake = _MultiDeviceFakeSupabase({"triage_sessions": sessions})

        with (
            patch.object(triage_routes, "_has_supabase", return_value=True),
            patch("app.supabase_client.get_supabase", return_value=fake),
        ):
            resp = self._get_history("device-spoofed-attacker")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["items"], [])

    def test_non_result_envelopes_never_leak(self):
        """QUESTION / ERROR envelopes must be filtered regardless of device.

        Sanity check on the `in_("envelope_type", ["RESULT", "EMERGENCY",
        "SAME_DAY"])` filter. If that filter goes missing, unfinished
        sessions (QUESTION) would expose the raw input_text PII the user
        typed before the session completed.
        """
        sessions = [
            {
                "id": "sess-RESULT",
                "device_id": "device-A",
                "envelope_type": "RESULT",
                "created_at": "2026-04-20T10:00:00Z",
            },
            {
                "id": "sess-QUESTION",
                "device_id": "device-A",
                "envelope_type": "QUESTION",
                "created_at": "2026-04-20T10:05:00Z",
            },
            {
                "id": "sess-ERROR",
                "device_id": "device-A",
                "envelope_type": "ERROR",
                "created_at": "2026-04-20T10:10:00Z",
            },
        ]
        fake = _MultiDeviceFakeSupabase({"triage_sessions": sessions})

        with (
            patch.object(triage_routes, "_has_supabase", return_value=True),
            patch("app.supabase_client.get_supabase", return_value=fake),
        ):
            resp = self._get_history("device-A")

        self.assertEqual(resp.status_code, 200)
        ids = {item["id"] for item in resp.json()["items"]}
        self.assertEqual(ids, {"sess-RESULT"})


# ─── 2. Write-side device attribution (create_session) ─────────────────


class SessionCreateDeviceAttributionTests(unittest.TestCase):
    """create_session() must attach the caller's device_id to the row.

    If write-side attribution ever regresses (e.g. a refactor accidentally
    drops `device_id` from the insert payload) every subsequent read via
    /v1/triage/history for that user will return nothing because the row
    is unattributed. This test pins the attribution.
    """

    def test_insert_payload_carries_device_id_verbatim(self):
        from app import session_repo

        captured: dict = {}

        class _InsertFake:
            def __init__(self):
                self.data = [{"id": "00000000-0000-4000-8000-000000000001"}]

            def insert(self, payload):
                captured["payload"] = payload
                return self

            def execute(self):
                return _FakeExecute(self.data)

        class _SBFake:
            def table(self, _name):
                return _InsertFake()

        with patch("app.session_repo.get_supabase", return_value=_SBFake()):
            session_repo.create_session(
                locale="tr-TR",
                input_text="Göğüs ağrım var",
                device_id="device-alpha",
            )

        self.assertEqual(captured["payload"]["device_id"], "device-alpha")
        self.assertEqual(captured["payload"]["locale"], "tr-TR")

    def test_insert_strips_and_caps_device_id_length(self):
        """Defense-in-depth: trim + 128-char cap prevents storage of
        runaway strings even if Pydantic validation is bypassed at the
        route edge (e.g. direct library usage from tuning_tasks)."""
        from app import session_repo

        captured: dict = {}

        class _InsertFake:
            data = [{"id": "00000000-0000-4000-8000-000000000001"}]

            def insert(self, payload):
                captured["payload"] = payload
                return self

            def execute(self):
                return _FakeExecute(self.data)

        class _SBFake:
            def table(self, _name):
                return _InsertFake()

        # Surrounding whitespace + a 200-char body. Expected: trim + 128
        # from session_repo.create_session().
        noisy = "  " + ("x" * 200) + "  "

        with patch("app.session_repo.get_supabase", return_value=_SBFake()):
            session_repo.create_session(
                locale="tr-TR",
                input_text="test",
                device_id=noisy,
            )

        stored = captured["payload"]["device_id"]
        self.assertEqual(stored, "x" * 128)


# ─── 3. Push-token scoped writes ───────────────────────────────────────


class PushTokenScopedWriteTests(unittest.TestCase):
    """register_token upserts on (device_id) and unregister_token only
    affects the requested device's row.

    These two are the write-side equivalent of the read-side history
    isolation: if the filter ever gets dropped, `unregister_token('d1')`
    would flip EVERY row in `push_tokens.active=false` and silently
    break push for every user. A filter-aware fake catches that.
    """

    def test_register_upserts_on_device_id(self):
        captured: dict = {}

        class _QueryFake:
            def upsert(self, payload, on_conflict=None):
                captured["payload"] = payload
                captured["on_conflict"] = on_conflict
                return self

            def execute(self):
                return _FakeExecute([captured.get("payload", {})])

        class _SBFake:
            def table(self, name):
                captured["table"] = name
                return _QueryFake()

        with patch.object(push, "supabase", _SBFake()):
            push.register_token(
                device_id="device-1",
                expo_token="ExponentPushToken[abc]",
                platform="ios",
                locale="tr-TR",
            )

        self.assertEqual(captured["table"], "push_tokens")
        # on_conflict="device_id" is the ONLY thing preventing device A
        # from clobbering device B's row via a row-id collision. Pin it.
        self.assertEqual(captured["on_conflict"], "device_id")
        self.assertEqual(captured["payload"]["device_id"], "device-1")

    def test_unregister_token_d1_does_not_touch_d2(self):
        """Prove the `.eq("device_id", d1)` filter is effective.

        Uses a filter-aware fake so a regression that drops the filter
        would flip BOTH rows inactive, and the assertion would catch it.
        """
        rows = [
            {"device_id": "d1", "expo_token": "tok-1", "active": True},
            {"device_id": "d2", "expo_token": "tok-2", "active": True},
        ]
        captured: dict = {"updates_applied_to": []}

        class _UpdateFake:
            def __init__(self, table_rows):
                self._rows = table_rows
                self._eq_filters: list[tuple] = []
                self._update_payload: dict | None = None

            def update(self, payload):
                self._update_payload = payload
                return self

            def eq(self, col, val):
                self._eq_filters.append((col, val))
                return self

            def execute(self):
                # Apply the update in-memory to whichever rows match the
                # filter; capture the list of device_ids affected.
                affected = []
                for row in self._rows:
                    if all(row.get(c) == v for c, v in self._eq_filters):
                        row.update(self._update_payload or {})
                        affected.append(row["device_id"])
                captured["updates_applied_to"].extend(affected)
                return _FakeExecute([{"updated": True}])

        class _SBFake:
            def table(self, _name):
                return _UpdateFake(rows)

        with patch.object(push, "supabase", _SBFake()):
            push.unregister_token(device_id="d1")

        # d1 flipped, d2 untouched
        self.assertEqual(captured["updates_applied_to"], ["d1"])
        self.assertEqual(
            [r for r in rows if r["device_id"] == "d1"][0]["active"],
            False,
        )
        self.assertEqual(
            [r for r in rows if r["device_id"] == "d2"][0]["active"],
            True,
        )


# ─── 4. Follow-up reminder correct session→token pairing ──────────────


class FollowupReminderPairingTests(unittest.TestCase):
    """The follow-up push flow does session→token lookup by device_id in
    Python (no SQL JOIN). A regression that mis-pairs (e.g. indexing by
    session.id instead of session.device_id) would send device A's
    reminder to device B's token — a privacy leak and a user-confusion
    bug.

    This test uses two devices with interleaved sessions to prove the
    pairing is keyed by device_id, not by list index or session_id.
    """

    def test_each_device_gets_its_own_token(self):
        sessions = [
            {
                "id": "sess-A",
                "device_id": "device-A",
                "locale": "tr-TR",
                "envelope_type": "RESULT",
                "recommended_specialty_tr": "Dahiliye",
            },
            {
                "id": "sess-B",
                "device_id": "device-B",
                "locale": "en-US",
                "envelope_type": "RESULT",
                "recommended_specialty_tr": "Cardiology",
            },
        ]
        tokens = [
            {"device_id": "device-A", "expo_token": "tok-A", "active": True},
            {"device_id": "device-B", "expo_token": "tok-B", "active": True},
        ]
        fake = _MultiDeviceFakeSupabase(
            {
                "triage_sessions": sessions,
                "triage_feedback": [],
                "push_tokens": tokens,
            }
        )

        class _MockResp:
            status_code = 200
            text = ""

        sent_batches: list[list[dict]] = []

        class _MockClient:
            def __init__(self, *a, **kw): ...

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def post(self, _url, json):
                sent_batches.append(json)
                return _MockResp()

        with (
            patch.object(push, "supabase", fake),
            patch("app.push.httpx.Client", _MockClient),
        ):
            result = push.send_followup_reminders(hours_min=20, hours_max=48)

        self.assertEqual(result["sent"], 2)
        self.assertEqual(result["skipped_feedback"], 0)
        self.assertEqual(result["skipped_no_token"], 0)

        # Flatten the batched payloads and confirm each session went to
        # its own device's token.
        all_msgs = [m for batch in sent_batches for m in batch]
        pairs = {m["data"]["session_id"]: m["to"] for m in all_msgs}
        self.assertEqual(pairs, {"sess-A": "tok-A", "sess-B": "tok-B"})

    def test_inactive_token_is_not_reused_for_another_device(self):
        """If device A's token is inactive AND device B has no token,
        neither device should receive a push. A regression that falls
        back to "any active token" would leak A's reminder to another
        device entirely."""
        sessions = [
            {
                "id": "sess-A",
                "device_id": "device-A",
                "locale": "tr-TR",
                "envelope_type": "RESULT",
                "recommended_specialty_tr": "Dahiliye",
            },
            {
                "id": "sess-B",
                "device_id": "device-B",
                "locale": "tr-TR",
                "envelope_type": "RESULT",
                "recommended_specialty_tr": "Dahiliye",
            },
        ]
        tokens = [
            # device-A inactive, device-B missing entirely.
            {"device_id": "device-A", "expo_token": "tok-A", "active": False},
        ]
        fake = _MultiDeviceFakeSupabase(
            {
                "triage_sessions": sessions,
                "triage_feedback": [],
                "push_tokens": tokens,
            }
        )

        sent_batches: list[list[dict]] = []

        class _MockResp:
            status_code = 200
            text = ""

        class _MockClient:
            def __init__(self, *a, **kw): ...

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def post(self, _url, json):
                sent_batches.append(json)
                return _MockResp()

        with (
            patch.object(push, "supabase", fake),
            patch("app.push.httpx.Client", _MockClient),
        ):
            result = push.send_followup_reminders()

        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["skipped_no_token"], 2)
        self.assertEqual(sent_batches, [])


# ─── 5. admin_users RLS self-read policy shape ─────────────────────────


class AdminUsersRLSMigrationShapeTests(unittest.TestCase):
    """The admin_users RLS policy is the ONLY thing stopping a signed-in
    user from reading everyone else's admin rows via the dashboard
    (which hits Supabase with the caller's JWT, not the service key).

    There's no live Postgres in the unit-test environment, but we CAN
    pin the migration's text shape so a refactor that accidentally
    drops the `user_id = auth.uid()` USING clause, or widens the
    policy to FOR ALL, gets caught in CI before it ships.
    """

    _MIGRATION_PATH = (
        Path(__file__).resolve().parent.parent
        / "sql"
        / "20260419_admin_users_rls.sql"
    )

    def setUp(self):
        self.assertTrue(
            self._MIGRATION_PATH.exists(),
            f"Expected migration at {self._MIGRATION_PATH}",
        )
        self.sql = self._MIGRATION_PATH.read_text(encoding="utf-8")

    def test_rls_is_enabled_on_admin_users(self):
        self.assertRegex(
            self.sql,
            r"alter\s+table\s+public\.admin_users\s+enable\s+row\s+level\s+security",
        )

    def test_self_read_policy_is_select_only(self):
        # `FOR ALL` or `FOR UPDATE` would widen the policy beyond what
        # the dashboard needs (it only SELECTs) and risk accidentally
        # letting authenticated users mutate their own role.
        self.assertRegex(
            self.sql,
            r'create\s+policy\s+"admin_users_self_read"'
            r"[^;]*\bfor\s+select\b",
            msg="self_read policy must be scoped to SELECT only",
        )

    def test_self_read_policy_uses_auth_uid_filter(self):
        # The actual isolation rule. A regression that swaps this for
        # `true` or drops the USING clause would turn the table into a
        # public read.
        self.assertRegex(
            self.sql,
            r"using\s*\(\s*user_id\s*=\s*auth\.uid\(\)\s*\)",
            msg="self_read policy must filter on user_id = auth.uid()",
        )

    def test_policy_targets_authenticated_role_not_public(self):
        # Granting to `public` would include the anon role and let any
        # visitor hit the table. We explicitly want authenticated only.
        self.assertRegex(
            self.sql,
            r"to\s+authenticated",
        )
        self.assertNotRegex(
            self.sql,
            r"to\s+public\b",
            msg="policy must not grant to public/anon roles",
        )

    def test_migration_is_idempotent(self):
        """The migration must be safely rerunnable — uses IF EXISTS /
        IF NOT EXISTS or DROP-then-CREATE so a second apply is a no-op.
        """
        # We have `drop policy if exists` before the create, which is
        # the project's idempotency pattern for RLS policies.
        self.assertRegex(
            self.sql,
            r"drop\s+policy\s+if\s+exists\s+\"admin_users_self_read\"",
        )


if __name__ == "__main__":
    unittest.main()
