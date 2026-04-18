"""Unit tests for llm_nlu observability + error paths.

test_llm_nlu.py already covers the extraction happy path and the four
"named" failure modes (timeout, 429 rate limit, schema error, provider
down). The gaps flagged by coverage audit are in the auxiliary
observability path — _log_llm_call, _health_monitor_observe,
_log_synonym_suggestions — plus two error branches in
extract_canonicals_llm itself (500 HTTPStatusError → llm_http_error,
and the generic exception → llm_error tag).

These are load-bearing for the ops dashboard and the paging webhook,
so a regression in them is easy to miss but expensive (silent data
loss or missed incident). The tests below patch threading.Thread so
the daemon work runs inline — we assert on the patched Supabase
handle rather than on wall-clock side-effects.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx


def _patch_monitor_settings(
    *,
    enabled: bool = True,
    window: int = 20,
    min_calls: int = 3,
    threshold_pct: float = 80.0,
    cooldown_sec: float = 900,
):
    """Replace llm_nlu.settings with a SimpleNamespace carrying only
    the fields the monitor reads.

    Patching settings attributes individually via patch.object works on
    Python 3.14 but has been flaky against Pydantic v2 BaseSettings on
    Python 3.11 — the `setattr` doesn't always round-trip through the
    Pydantic field machinery, so the monitor still reads the original
    default. Swapping the whole reference dodges that entirely.
    """
    from app.services import llm_nlu

    ns = SimpleNamespace(
        LLM_HEALTH_ALERT_ENABLED=enabled,
        LLM_HEALTH_ALERT_WINDOW=window,
        LLM_HEALTH_ALERT_MIN_CALLS=min_calls,
        LLM_HEALTH_ALERT_THRESHOLD_PCT=threshold_pct,
        LLM_HEALTH_ALERT_COOLDOWN_SEC=cooldown_sec,
        LLM_NLU_LOG_TO_SUPABASE=False,
    )
    return patch.object(llm_nlu, "settings", ns)


class LogLlmCallTests(unittest.TestCase):
    """_log_llm_call: Supabase insert + health monitor hook."""

    def test_disabled_short_circuits(self):
        """LLM_NLU_LOG_TO_SUPABASE=False → no work done."""
        from app.services import llm_nlu

        with patch.object(llm_nlu.settings, "LLM_NLU_LOG_TO_SUPABASE", False):
            with patch.object(llm_nlu.threading, "Thread") as mocked_thread:
                llm_nlu._log_llm_call(
                    session_id="s1",
                    provider="p",
                    model="m",
                    input_tokens=1,
                    output_tokens=1,
                    latency_ms=1,
                    success=True,
                    error_type=None,
                    nlu_source="llm",
                )
        # No thread spawned when disabled
        mocked_thread.assert_not_called()

    def test_enabled_spawns_daemon_thread_and_triggers_health_monitor(self):
        """When enabled, both the Supabase insert and the health-monitor
        hook fire. We don't care whether the insert succeeds; we care
        that the side-effects were attempted."""
        from app.services import llm_nlu

        with patch.object(llm_nlu.settings, "LLM_NLU_LOG_TO_SUPABASE", True):
            with patch.object(llm_nlu, "_health_monitor_observe") as mocked_obs:
                with patch.object(llm_nlu.threading, "Thread") as mocked_thread:
                    thread_inst = MagicMock()
                    mocked_thread.return_value = thread_inst
                    llm_nlu._log_llm_call(
                        session_id="s1",
                        provider="p",
                        model="m",
                        input_tokens=10,
                        output_tokens=5,
                        latency_ms=100,
                        success=False,
                        error_type="timeout",
                        nlu_source="llm_timeout",
                    )
        mocked_thread.assert_called_once()
        thread_inst.start.assert_called_once()
        mocked_obs.assert_called_once_with(success=False, error_type="timeout")

    def test_health_monitor_exception_does_not_propagate(self):
        """If _health_monitor_observe raises, _log_llm_call swallows it
        (observability must never break triage)."""
        from app.services import llm_nlu

        with patch.object(llm_nlu.settings, "LLM_NLU_LOG_TO_SUPABASE", True):
            with patch.object(
                llm_nlu,
                "_health_monitor_observe",
                side_effect=RuntimeError("boom"),
            ):
                with patch.object(llm_nlu.threading, "Thread"):
                    # Should not raise
                    llm_nlu._log_llm_call(
                        session_id="s1",
                        provider="p",
                        model="m",
                        input_tokens=1,
                        output_tokens=1,
                        latency_ms=1,
                        success=True,
                        error_type=None,
                        nlu_source="llm",
                    )


class HealthMonitorObserveTests(unittest.TestCase):
    """_health_monitor_observe: rolling-window alert dispatcher.

    The monitor carries module-level state (_HEALTH_EVENTS deque,
    _LAST_ALERT_TS). Earlier tests in the same pytest process can
    populate these — for example test_llm_nlu.py exercises the
    extraction path which logs through _log_llm_call → observe.
    setUp / tearDown both reset so a leaked alert-timestamp from a
    prior test doesn't swallow our first burst via the cooldown check.
    """

    def _reset_state(self):
        from app.services import llm_nlu

        # _LAST_ALERT_TS = 0.0 would LOOK like "never alerted", but the
        # cooldown check is `time.monotonic() - _LAST_ALERT_TS < cooldown`.
        # On a fresh CI worker, time.monotonic() is small (seconds since
        # process start), so 0.0 can sit INSIDE the cooldown window — the
        # first alert gets suppressed and `assert_called_once` fails with
        # "called 0 times". Use a large negative sentinel so the first
        # alert always clears the cooldown no matter how fresh the
        # process is. Locally this didn't bite because time.monotonic()
        # was already deep into the full test suite by the time these
        # tests ran.
        with llm_nlu._HEALTH_LOCK:
            llm_nlu._HEALTH_EVENTS.clear()
            llm_nlu._LAST_ALERT_TS = -1e12

    def setUp(self):
        self._reset_state()

    def tearDown(self):
        self._reset_state()

    def test_disabled_short_circuits(self):
        from app.services import llm_nlu

        with _patch_monitor_settings(enabled=False):
            with patch("app.notifier.send_llm_health_alert") as mocked_send:
                llm_nlu._health_monitor_observe(success=False, error_type="timeout")
        mocked_send.assert_not_called()

    def test_below_min_calls_no_alert(self):
        """Fewer than MIN_CALLS samples → silent, no alert."""
        from app.services import llm_nlu

        with _patch_monitor_settings(min_calls=10):
            with patch("app.notifier.send_llm_health_alert") as mocked_send:
                for _ in range(3):
                    llm_nlu._health_monitor_observe(success=False, error_type="timeout")
        mocked_send.assert_not_called()

    def test_success_rate_above_threshold_no_alert(self):
        """Healthy sliding window → no alert, no cooldown touched."""
        from app.services import llm_nlu

        with _patch_monitor_settings(min_calls=3, threshold_pct=80.0):
            with patch("app.notifier.send_llm_health_alert") as mocked_send:
                for _ in range(5):
                    llm_nlu._health_monitor_observe(success=True, error_type=None)
        mocked_send.assert_not_called()

    def test_failure_burst_fires_alert(self):
        """Below-threshold success rate after min_calls → webhook fires."""
        from app.services import llm_nlu

        with _patch_monitor_settings(
            min_calls=3, threshold_pct=80.0, cooldown_sec=900
        ):
            with patch("app.notifier.send_llm_health_alert") as mocked_send:
                # 5 failures in a row → 0% success rate, way below 80%
                # threshold → should fire once.
                for _ in range(5):
                    llm_nlu._health_monitor_observe(
                        success=False, error_type="timeout"
                    )
        mocked_send.assert_called_once()
        kwargs = mocked_send.call_args.kwargs
        self.assertEqual(kwargs["top_error"], "timeout")
        self.assertAlmostEqual(kwargs["success_rate_pct"], 0.0)

    def test_cooldown_suppresses_second_alert(self):
        """Within cooldown window, a second failure burst does not repage."""
        from app.services import llm_nlu

        with _patch_monitor_settings(
            min_calls=3, threshold_pct=80.0, cooldown_sec=9999
        ):
            with patch("app.notifier.send_llm_health_alert") as mocked_send:
                for _ in range(10):
                    llm_nlu._health_monitor_observe(
                        success=False, error_type="timeout"
                    )
        # Only first crossing of the threshold pages
        mocked_send.assert_called_once()

    def test_notifier_exception_does_not_propagate(self):
        from app.services import llm_nlu

        with _patch_monitor_settings(min_calls=3, threshold_pct=80.0):
            with patch(
                "app.notifier.send_llm_health_alert",
                side_effect=RuntimeError("webhook down"),
            ):
                # Must not raise
                for _ in range(5):
                    llm_nlu._health_monitor_observe(
                        success=False, error_type="timeout"
                    )


class LogSynonymSuggestionsTests(unittest.TestCase):
    """_log_synonym_suggestions: background upsert to synonym_suggestions."""

    def test_disabled_short_circuits(self):
        from app.services import llm_nlu

        with patch.object(llm_nlu.settings, "LLM_NLU_LOG_TO_SUPABASE", False):
            with patch.object(llm_nlu.threading, "Thread") as mocked_thread:
                llm_nlu._log_synonym_suggestions(["cough"])
        mocked_thread.assert_not_called()

    def test_empty_phrases_short_circuits(self):
        from app.services import llm_nlu

        with patch.object(llm_nlu.settings, "LLM_NLU_LOG_TO_SUPABASE", True):
            with patch.object(llm_nlu.threading, "Thread") as mocked_thread:
                llm_nlu._log_synonym_suggestions([])
        mocked_thread.assert_not_called()

    def test_spawns_thread_when_enabled_with_phrases(self):
        from app.services import llm_nlu

        with patch.object(llm_nlu.settings, "LLM_NLU_LOG_TO_SUPABASE", True):
            with patch.object(llm_nlu.threading, "Thread") as mocked_thread:
                thread_inst = MagicMock()
                mocked_thread.return_value = thread_inst
                llm_nlu._log_synonym_suggestions(["cough", "nausea"])
        mocked_thread.assert_called_once()
        thread_inst.start.assert_called_once()


class ExtractCanonicalsErrorBranchTests(unittest.TestCase):
    """Coverage gaps in extract_canonicals_llm error paths."""

    _SYN = {
        "synonyms": [
            {"canonical": "ateş", "variants_tr": ["ateşim var"]},
        ]
    }

    def _call(self, text: str = "hi"):
        from app.services.llm_nlu import extract_canonicals_llm

        return extract_canonicals_llm(
            text=text, locale="tr-TR", synonyms_json=self._SYN
        )

    def test_http_500_returns_llm_http_error_tag(self):
        """500 (non-429) HTTPStatusError maps to 'llm_http_error'."""
        fake_response = MagicMock()
        fake_response.status_code = 500
        exc = httpx.HTTPStatusError(
            "server error", request=MagicMock(), response=fake_response
        )
        with patch("app.services.llm_nlu.get_nlu_client") as mock_get:
            mock_client = MagicMock()
            mock_client.call.side_effect = exc
            mock_get.return_value = mock_client
            with patch("app.services.llm_nlu._log_llm_call"):
                canonicals, source = self._call()
        self.assertEqual(canonicals, [])
        self.assertEqual(source, "llm_http_error")

    def test_generic_exception_returns_llm_error_tag(self):
        """Any non-httpx exception falls through to 'llm_error'."""
        with patch("app.services.llm_nlu.get_nlu_client") as mock_get:
            mock_client = MagicMock()
            mock_client.call.side_effect = RuntimeError("provider exploded")
            mock_get.return_value = mock_client
            with patch("app.services.llm_nlu._log_llm_call"):
                canonicals, source = self._call()
        self.assertEqual(canonicals, [])
        self.assertEqual(source, "llm_error")

    def test_unrecognized_symptoms_trigger_suggestion_log(self):
        """When LLM reports unrecognized_symptoms, the suggestion
        pipeline logger is invoked."""
        import json

        response = {
            "canonicals": ["ateş"],
            "confidence": 0.9,
            "unrecognized_symptoms": ["new_weird_symptom"],
        }
        with patch("app.services.llm_nlu.get_nlu_client") as mock_get:
            mock_client = MagicMock()
            mock_client.call = MagicMock(
                return_value=(json.dumps(response), 10, 5)
            )
            mock_get.return_value = mock_client
            with patch("app.services.llm_nlu._log_llm_call"):
                with patch(
                    "app.services.llm_nlu._log_synonym_suggestions"
                ) as mocked_sugg:
                    canonicals, source = self._call()
        self.assertEqual(source, "llm")
        mocked_sugg.assert_called_once_with(["new_weird_symptom"])

    def test_json_extracted_from_surrounding_text(self):
        """LLM returned prose + JSON — the regex extraction salvages it."""
        import json

        raw = (
            "Sure! Here are the symptoms: "
            + json.dumps(
                {
                    "canonicals": ["ateş"],
                    "confidence": 0.7,
                    "unrecognized_symptoms": [],
                }
            )
            + " That's my best interpretation."
        )
        with patch("app.services.llm_nlu.get_nlu_client") as mock_get:
            mock_client = MagicMock()
            mock_client.call = MagicMock(return_value=(raw, 10, 5))
            mock_get.return_value = mock_client
            with patch("app.services.llm_nlu._log_llm_call"):
                canonicals, source = self._call()
        self.assertEqual(canonicals, ["ateş"])
        self.assertEqual(source, "llm")


if __name__ == "__main__":
    unittest.main()
