from __future__ import annotations

import unittest
from unittest.mock import patch

from app import push


class _FakeExecute:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table_name: str):
        self.table_name = table_name
        self.last_upsert = None
        self.last_update = None
        self.eq_filters: list[tuple[str, object]] = []
        self.limit_value: int | None = None

    def upsert(self, payload, on_conflict=None):
        self.last_upsert = {"payload": payload, "on_conflict": on_conflict}
        return self

    def update(self, payload):
        self.last_update = payload
        return self

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column: str, value: object):
        self.eq_filters.append((column, value))
        return self

    def limit(self, value: int):
        self.limit_value = value
        return self

    def execute(self):
        if self.table_name == "push_tokens" and self.last_upsert:
            return _FakeExecute([self.last_upsert["payload"]])
        if self.table_name == "push_tokens" and self.last_update:
            return _FakeExecute([{"updated": True}])
        return _FakeExecute([{"expo_token": "ExponentPushToken[a]"}, {"expo_token": "ExponentPushToken[b]"}])


class _FakeSupabase:
    def __init__(self):
        self.queries: dict[str, _FakeQuery] = {}

    def table(self, table_name: str):
        query = _FakeQuery(table_name)
        self.queries[table_name] = query
        return query


class PushServiceTests(unittest.TestCase):
    def test_register_token_uses_supabase_client_without_calling_it(self):
        fake = _FakeSupabase()
        with patch.object(push, "supabase", fake):
            response = push.register_token(
                device_id="device-1",
                expo_token="ExponentPushToken[abc]",
                platform="ios",
                locale="tr-TR",
            )

        self.assertTrue(response["ok"])
        query = fake.queries["push_tokens"]
        self.assertEqual(query.last_upsert["on_conflict"], "device_id")
        self.assertEqual(query.last_upsert["payload"]["device_id"], "device-1")
        self.assertEqual(query.last_upsert["payload"]["active"], True)

    def test_unregister_token_marks_token_inactive(self):
        fake = _FakeSupabase()
        with patch.object(push, "supabase", fake):
            response = push.unregister_token(device_id="device-2")

        self.assertTrue(response["ok"])
        query = fake.queries["push_tokens"]
        self.assertEqual(query.last_update, {"active": False})
        self.assertIn(("device_id", "device-2"), query.eq_filters)

    def test_get_active_tokens_reads_active_rows(self):
        fake = _FakeSupabase()
        with patch.object(push, "supabase", fake):
            tokens = push._get_active_tokens()

        self.assertEqual(tokens, ["ExponentPushToken[a]", "ExponentPushToken[b]"])
        query = fake.queries["push_tokens"]
        self.assertIn(("active", True), query.eq_filters)
        self.assertEqual(query.limit_value, 500)


# ─── Follow-up reminder tests ──────────────────────────────────────
#
# Uses a richer fake that supports the full query chain the follow-up
# logic builds: .select().gte().lte().in_().not_.is_().limit().execute().
# We plug table-specific row fixtures and let the fake filter them
# in-memory so the assertion can check which sessions actually got
# pushed.


class _FollowupFakeQuery:
    def __init__(self, rows: list[dict]):
        self._rows = list(rows)
        self._filters: list = []
        self._limit: int | None = None
        self.not_ = self  # chainable `.not_.is_()` mirrors postgrest-py

    def select(self, *_args, **_kwargs):
        return self

    def gte(self, col, val):
        self._filters.append(("gte", col, val))
        return self

    def lte(self, col, val):
        self._filters.append(("lte", col, val))
        return self

    def eq(self, col, val):
        self._filters.append(("eq", col, val))
        return self

    def in_(self, col, vals):
        self._filters.append(("in", col, set(vals)))
        return self

    def is_(self, col, val):
        # Called via `.not_.is_(col, "null")` → require col is not null
        self._filters.append(("not_is", col, val))
        return self

    def limit(self, n):
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
            # gte/lte ignored — fixtures pre-filtered to the window
        if self._limit is not None:
            data = data[: self._limit]
        return _FakeExecute(data)


class _FollowupFakeSupabase:
    def __init__(
        self,
        sessions: list[dict],
        feedback: list[dict],
        tokens: list[dict],
    ):
        self._tables = {
            "triage_sessions": sessions,
            "triage_feedback": feedback,
            "push_tokens": tokens,
        }

    def table(self, name: str):
        return _FollowupFakeQuery(self._tables.get(name, []))


class FollowupReminderTests(unittest.TestCase):
    def test_skips_sessions_that_already_have_feedback(self):
        sessions = [
            {"id": "s1", "device_id": "d1", "locale": "tr-TR", "envelope_type": "RESULT"},
            {"id": "s2", "device_id": "d2", "locale": "tr-TR", "envelope_type": "RESULT"},
        ]
        feedback = [{"session_id": "s1"}]
        tokens = [
            {"device_id": "d1", "expo_token": "tok-1", "active": True},
            {"device_id": "d2", "expo_token": "tok-2", "active": True},
        ]
        fake = _FollowupFakeSupabase(sessions, feedback, tokens)

        # httpx.Client is instantiated inside the function; patch it so we
        # can record the payload without hitting the network.
        class _MockResp:
            status_code = 200
            text = ""

        class _MockClient:
            def __init__(self, *a, **kw): ...
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def post(self, url, json):
                _MockClient.sent = json  # type: ignore[attr-defined]
                return _MockResp()

        with (
            patch.object(push, "supabase", fake),
            patch("app.push.httpx.Client", _MockClient),
        ):
            result = push.send_followup_reminders(hours_min=20, hours_max=48)

        # s1 has feedback → skipped; s2 gets pushed.
        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["skipped_feedback"], 1)
        self.assertEqual(result["candidates"], 2)
        sent_batch = getattr(_MockClient, "sent", [])
        self.assertEqual(len(sent_batch), 1)
        self.assertEqual(sent_batch[0]["to"], "tok-2")
        self.assertEqual(sent_batch[0]["data"]["action"], "feedback_prompt")

    def test_skips_sessions_without_matching_token(self):
        sessions = [
            {"id": "s3", "device_id": "d3", "locale": "en-US", "envelope_type": "SAME_DAY"},
        ]
        # No matching push_tokens row for d3.
        fake = _FollowupFakeSupabase(sessions, [], [])

        with patch.object(push, "supabase", fake):
            result = push.send_followup_reminders()

        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["skipped_no_token"], 1)

    def test_locale_selects_english_copy(self):
        self.assertEqual(push._pick_copy("en-US")["title"], "💬 How did it go?")
        self.assertEqual(push._pick_copy("tr-TR")["title"], "💬 Geri bildiriminizi alalım")
        self.assertEqual(push._pick_copy(None)["title"], "💬 Geri bildiriminizi alalım")
        self.assertEqual(push._pick_copy("de-DE")["title"], "💬 Geri bildiriminizi alalım")


if __name__ == "__main__":
    unittest.main()
