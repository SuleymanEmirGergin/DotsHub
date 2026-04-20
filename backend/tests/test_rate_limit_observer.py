"""Tests for the rate-limit rejection observer in app.main.

Same design as LLM health / HTTP 5xx observer tests: mock
send_rate_limit_alert and assert it fires / stays silent under
combinations of window size, rejection rate, and cool-down.

These matter because a regression in the observer silently disables
abuse paging — it's the kind of bug you only find out about during
an actual incident.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app import main as app_main


class ObserverStateMixin:
    """Shared setUp that clears the in-memory ring + alert timestamp.

    The observer owns module-level state (_RL_EVENTS, _RL_LAST_ALERT_TS).
    Each test has to start from a known-clean state or an earlier test's
    rejections + cool-down timestamp will poison it.
    """

    def _reset(self):
        with app_main._RL_LOCK:
            app_main._RL_EVENTS.clear()
            # Large-negative sentinel — same trick the llm_nlu unit
            # tests use. time.monotonic() - (-1e12) >> any cooldown,
            # so the first alert always crosses regardless of how
            # fresh the process is.
            app_main._RL_LAST_ALERT_TS = -1e12


class DisabledTests(unittest.TestCase, ObserverStateMixin):
    def setUp(self):
        self._reset()

    def test_disabled_flag_short_circuits(self):
        with patch.object(app_main.settings, "RATE_LIMIT_ALERT_ENABLED", False):
            with patch("app.notifier.send_rate_limit_alert") as mocked:
                for _ in range(50):
                    app_main._rate_limit_observe("default", "ip:1.2.3.4", False)
        mocked.assert_not_called()


class WindowGateTests(unittest.TestCase, ObserverStateMixin):
    def setUp(self):
        self._reset()

    def test_below_min_decisions_no_alert(self):
        """Don't alert until we've seen MIN_DECISIONS samples —
        otherwise a single early rejection blows up a 100% rate."""
        with patch.object(app_main.settings, "RATE_LIMIT_ALERT_ENABLED", True):
            with patch.object(app_main.settings, "RATE_LIMIT_ALERT_MIN_DECISIONS", 30):
                with patch.object(app_main.settings, "RATE_LIMIT_ALERT_THRESHOLD_PCT", 10.0):
                    with patch("app.notifier.send_rate_limit_alert") as mocked:
                        for _ in range(5):
                            app_main._rate_limit_observe("default", "ip:x", False)
        mocked.assert_not_called()


class RejectionAlertTests(unittest.TestCase, ObserverStateMixin):
    def setUp(self):
        self._reset()

    def test_rejection_burst_fires_alert_once(self):
        with patch.object(app_main.settings, "RATE_LIMIT_ALERT_ENABLED", True):
            with patch.object(app_main.settings, "RATE_LIMIT_ALERT_MIN_DECISIONS", 10):
                with patch.object(app_main.settings, "RATE_LIMIT_ALERT_THRESHOLD_PCT", 20.0):
                    with patch.object(
                        app_main.settings, "RATE_LIMIT_ALERT_COOLDOWN_SEC", 600
                    ):
                        with patch("app.notifier.send_rate_limit_alert") as mocked:
                            # 15 rejections + 0 allowed = 100% rejection
                            # rate, way above 20% threshold. min_decisions
                            # met at call #10.
                            for _ in range(15):
                                app_main._rate_limit_observe(
                                    "default", "ip:abuser", False
                                )
        mocked.assert_called_once()
        kwargs = mocked.call_args.kwargs
        self.assertEqual(kwargs["top_bucket"], "default")
        self.assertEqual(kwargs["top_key"], "ip:abuser")
        self.assertAlmostEqual(kwargs["rejection_rate_pct"], 100.0, places=1)

    def test_healthy_traffic_no_alert(self):
        """Heavy allowed traffic — zero rejections — must stay silent."""
        with patch.object(app_main.settings, "RATE_LIMIT_ALERT_ENABLED", True):
            with patch.object(app_main.settings, "RATE_LIMIT_ALERT_MIN_DECISIONS", 10):
                with patch.object(app_main.settings, "RATE_LIMIT_ALERT_THRESHOLD_PCT", 10.0):
                    with patch("app.notifier.send_rate_limit_alert") as mocked:
                        for _ in range(50):
                            app_main._rate_limit_observe("default", "ip:user", True)
        mocked.assert_not_called()

    def test_cooldown_suppresses_second_alert(self):
        with patch.object(app_main.settings, "RATE_LIMIT_ALERT_ENABLED", True):
            with patch.object(app_main.settings, "RATE_LIMIT_ALERT_MIN_DECISIONS", 5):
                with patch.object(app_main.settings, "RATE_LIMIT_ALERT_THRESHOLD_PCT", 10.0):
                    with patch.object(
                        app_main.settings, "RATE_LIMIT_ALERT_COOLDOWN_SEC", 9999
                    ):
                        with patch("app.notifier.send_rate_limit_alert") as mocked:
                            for _ in range(30):
                                app_main._rate_limit_observe(
                                    "default", "ip:burst", False
                                )
        mocked.assert_called_once()

    def test_notifier_raising_is_swallowed(self):
        with patch.object(app_main.settings, "RATE_LIMIT_ALERT_ENABLED", True):
            with patch.object(app_main.settings, "RATE_LIMIT_ALERT_MIN_DECISIONS", 5):
                with patch.object(app_main.settings, "RATE_LIMIT_ALERT_THRESHOLD_PCT", 10.0):
                    with patch(
                        "app.notifier.send_rate_limit_alert",
                        side_effect=RuntimeError("webhook down"),
                    ):
                        # Must not raise — observability never breaks
                        # the request path.
                        for _ in range(10):
                            app_main._rate_limit_observe("default", "ip:x", False)

    def test_top_bucket_reports_most_rejected(self):
        """When multiple buckets reject, the alert picks the most-
        frequent (bucket, key) pair."""
        with patch.object(app_main.settings, "RATE_LIMIT_ALERT_ENABLED", True):
            with patch.object(app_main.settings, "RATE_LIMIT_ALERT_MIN_DECISIONS", 5):
                with patch.object(app_main.settings, "RATE_LIMIT_ALERT_THRESHOLD_PCT", 10.0):
                    with patch("app.notifier.send_rate_limit_alert") as mocked:
                        # 2 send_summary rejects, 5 admin rejects.
                        for _ in range(2):
                            app_main._rate_limit_observe(
                                "send_summary", "ip:A", False
                            )
                        for _ in range(5):
                            app_main._rate_limit_observe("admin", "ip:B", False)
        kwargs = mocked.call_args.kwargs
        self.assertEqual(kwargs["top_bucket"], "admin")
        self.assertEqual(kwargs["top_key"], "ip:B")


if __name__ == "__main__":
    unittest.main()
