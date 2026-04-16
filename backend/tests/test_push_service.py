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


if __name__ == "__main__":
    unittest.main()
