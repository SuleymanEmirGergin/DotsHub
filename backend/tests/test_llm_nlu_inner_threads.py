"""Tests for llm_nlu inner thread bodies (_insert / _upsert closures).

test_llm_nlu_unit.py verifies _log_llm_call and _log_synonym_suggestions
at the THREAD-SPAWN level (mocked threading.Thread confirms a daemon
gets kicked off). That leaves the INSIDE of the thread — the actual
Supabase insert/upsert logic — uncovered, which is where most of the
lines-uncovered count (128-133, 225-257) sits.

This file covers those inner bodies by replacing threading.Thread with
a synchronous runner: the thread's target is invoked immediately,
under the test's patched Supabase chain. We then assert on what the
fake client saw.

Closes the llm_nlu 75% → 85%+ coverage gate per Session 3 plan.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class _InlineThread:
    """Stand-in for threading.Thread that runs its target eagerly.

    Patched in via `patch.object(llm_nlu.threading, "Thread")` so the
    closure executes synchronously under the test's mocks. start() is
    a no-op since the work already happened in __init__.
    """

    def __init__(self, *, target, daemon=True, **_kwargs):
        self._target = target

    def start(self):
        self._target()


class LogLlmCallInnerInsertTests(unittest.TestCase):
    """Inside _insert(): Supabase table insert happy path + failure."""

    def test_insert_happy_path_hits_supabase_once(self):
        from app.services import llm_nlu

        fake_sb = MagicMock()
        # Chainable: supabase.table("llm_calls").insert(row).execute()
        fake_table = MagicMock()
        fake_sb.table.return_value = fake_table
        fake_insert = MagicMock()
        fake_table.insert.return_value = fake_insert
        fake_insert.execute.return_value = MagicMock(data=[{"id": 1}])

        with patch.object(llm_nlu.settings, "LLM_NLU_LOG_TO_SUPABASE", True):
            with patch.object(llm_nlu.threading, "Thread", _InlineThread):
                with patch.dict(
                    "sys.modules",
                    {"app.db": MagicMock(supabase=fake_sb)},
                ):
                    with patch.object(llm_nlu, "_health_monitor_observe"):
                        llm_nlu._log_llm_call(
                            session_id="sess-1",
                            provider="wiro",
                            model="gemini",
                            input_tokens=12,
                            output_tokens=8,
                            latency_ms=200,
                            success=True,
                            error_type=None,
                            nlu_source="llm",
                        )

        fake_sb.table.assert_called_once_with("llm_calls")
        inserted_row = fake_table.insert.call_args.args[0]
        self.assertEqual(inserted_row["session_id"], "sess-1")
        self.assertEqual(inserted_row["provider"], "wiro")
        self.assertEqual(inserted_row["nlu_source"], "llm")
        self.assertTrue(inserted_row["success"])
        fake_insert.execute.assert_called_once()

    def test_insert_supabase_raises_is_swallowed(self):
        """The _insert body wraps Supabase in try/except — a DB error
        must never leak out to the caller or break the health hook."""
        from app.services import llm_nlu

        fake_sb = MagicMock()
        fake_sb.table.side_effect = RuntimeError("db down")

        with patch.object(llm_nlu.settings, "LLM_NLU_LOG_TO_SUPABASE", True):
            with patch.object(llm_nlu.threading, "Thread", _InlineThread):
                with patch.dict(
                    "sys.modules",
                    {"app.db": MagicMock(supabase=fake_sb)},
                ):
                    with patch.object(llm_nlu, "_health_monitor_observe") as mock_hm:
                        # Must not raise.
                        llm_nlu._log_llm_call(
                            session_id="s",
                            provider="p",
                            model="m",
                            input_tokens=0,
                            output_tokens=0,
                            latency_ms=0,
                            success=False,
                            error_type="timeout",
                            nlu_source="llm_timeout",
                        )
        # Health hook still fired — observability must be independent
        # of Supabase availability.
        mock_hm.assert_called_once()


class LogSynonymSuggestionsInnerTests(unittest.TestCase):
    """Inside _upsert(): insert-first + update-on-conflict fallback."""

    def _make_sb_chain(self, insert_raises: bool, existing_data=None, update_raises=False):
        """Build a fake Supabase client matching the chain:
          sb.table(name).insert(row).execute()           — primary path
          sb.table(name).select(cols).eq(k,v).single().execute()  — fetch
          sb.table(name).update(row).eq(k,v).execute()   — count-bump
        """
        sb = MagicMock()
        table = MagicMock()
        sb.table.return_value = table

        # insert branch
        insert_call = MagicMock()
        table.insert.return_value = insert_call
        if insert_raises:
            insert_call.execute.side_effect = RuntimeError("unique violation")
        else:
            insert_call.execute.return_value = MagicMock(data=[{"id": 1}])

        # select branch for the fallback fetch
        select_call = MagicMock()
        table.select.return_value = select_call
        eq1 = MagicMock()
        select_call.eq.return_value = eq1
        single_call = MagicMock()
        eq1.single.return_value = single_call
        single_call.execute.return_value = MagicMock(data=existing_data)

        # update branch for count-bump
        update_call = MagicMock()
        table.update.return_value = update_call
        eq2 = MagicMock()
        update_call.eq.return_value = eq2
        if update_raises:
            eq2.execute.side_effect = RuntimeError("update failed")
        else:
            eq2.execute.return_value = MagicMock(data=[{"id": 1, "count": 2}])

        return sb, table

    def test_insert_first_success(self):
        """Phrase is new → insert wins, update is not touched."""
        from app.services import llm_nlu

        sb, table = self._make_sb_chain(insert_raises=False)
        with patch.object(llm_nlu.settings, "LLM_NLU_LOG_TO_SUPABASE", True):
            with patch.object(llm_nlu.threading, "Thread", _InlineThread):
                with patch.dict("sys.modules", {"app.db": MagicMock(supabase=sb)}):
                    llm_nlu._log_synonym_suggestions(["kafam dönüyor"])
        table.insert.assert_called_once()
        table.update.assert_not_called()

    def test_insert_conflict_falls_back_to_update(self):
        """Phrase exists → insert raises, fallback fetches id + updates count."""
        from app.services import llm_nlu

        sb, table = self._make_sb_chain(
            insert_raises=True,
            existing_data={"id": 42, "count": 7},
        )
        with patch.object(llm_nlu.settings, "LLM_NLU_LOG_TO_SUPABASE", True):
            with patch.object(llm_nlu.threading, "Thread", _InlineThread):
                with patch.dict("sys.modules", {"app.db": MagicMock(supabase=sb)}):
                    llm_nlu._log_synonym_suggestions(["başım ağrıyor"])
        # insert tried (and raised), then update with count+1 fired
        table.insert.assert_called_once()
        update_call = table.update.call_args.args[0]
        self.assertEqual(update_call, {"count": 8})

    def test_insert_conflict_but_no_existing_row_is_swallowed(self):
        """Insert fails AND select returns empty → no update, no raise.

        Guards the race where INSERT hit a transient unique constraint
        but the row is gone by the time we SELECT. Should not crash.
        """
        from app.services import llm_nlu

        sb, table = self._make_sb_chain(insert_raises=True, existing_data=None)
        with patch.object(llm_nlu.settings, "LLM_NLU_LOG_TO_SUPABASE", True):
            with patch.object(llm_nlu.threading, "Thread", _InlineThread):
                with patch.dict("sys.modules", {"app.db": MagicMock(supabase=sb)}):
                    llm_nlu._log_synonym_suggestions(["xyz"])
        table.update.assert_not_called()

    def test_insert_conflict_update_also_fails(self):
        """Double-failure path — both insert and update raise. Must
        not propagate."""
        from app.services import llm_nlu

        sb, table = self._make_sb_chain(
            insert_raises=True,
            existing_data={"id": 1, "count": 1},
            update_raises=True,
        )
        with patch.object(llm_nlu.settings, "LLM_NLU_LOG_TO_SUPABASE", True):
            with patch.object(llm_nlu.threading, "Thread", _InlineThread):
                with patch.dict("sys.modules", {"app.db": MagicMock(supabase=sb)}):
                    # Must not raise.
                    llm_nlu._log_synonym_suggestions(["double-fail-phrase"])

    def test_empty_and_whitespace_phrases_are_skipped(self):
        """Branch: `if not phrase: continue` — empty strings are
        filtered inside the loop, not just by the outer `if not
        phrases` guard."""
        from app.services import llm_nlu

        sb, table = self._make_sb_chain(insert_raises=False)
        with patch.object(llm_nlu.settings, "LLM_NLU_LOG_TO_SUPABASE", True):
            with patch.object(llm_nlu.threading, "Thread", _InlineThread):
                with patch.dict("sys.modules", {"app.db": MagicMock(supabase=sb)}):
                    llm_nlu._log_synonym_suggestions(["  ", "valid", "\t"])
        # Only "valid" reaches insert.
        self.assertEqual(table.insert.call_count, 1)
        inserted = table.insert.call_args.args[0]
        self.assertEqual(inserted["phrase"], "valid")

    def test_outer_try_catches_everything(self):
        """If `from app.db import supabase` itself fails (circular
        import scenario), the outer try must swallow it."""
        from app.services import llm_nlu

        # Make the import itself raise by replacing app.db with a
        # module that explodes on supabase attribute access.
        bad_db = MagicMock()
        type(bad_db).supabase = property(
            lambda self: (_ for _ in ()).throw(ImportError("circular"))
        )

        with patch.object(llm_nlu.settings, "LLM_NLU_LOG_TO_SUPABASE", True):
            with patch.object(llm_nlu.threading, "Thread", _InlineThread):
                with patch.dict("sys.modules", {"app.db": bad_db}):
                    # Must not raise.
                    llm_nlu._log_synonym_suggestions(["anything"])


if __name__ == "__main__":
    unittest.main()
