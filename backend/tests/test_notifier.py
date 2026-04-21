"""Unit tests for app/notifier.py — Slack/Discord webhook alerts.

The notifier is the on-call surface: when a triage session hits
EMERGENCY, when LLM NLU success rate tanks, when backend 5xx rate
climbs, or when rate-limit rejections spike, these webhooks page the
ops team. Prior coverage was 9.87% — every webhook we've written could
have been silently broken for weeks before anyone noticed the pager
never fired.

Tests are organized by public entry point. Thread dispatch is
short-circuited by patching `threading.Thread` so each public call is
observable without needing to sync with daemon threads. The internal
`_dispatch_*` + `_send_slack` / `_send_discord` + `_extract_info`
functions are tested directly to pin the wire format (Slack Block Kit,
Discord Embed) that Slack/Discord servers expect — a regression in the
body shape would produce 4xx responses silently (we only log `.warning`
on 4xx, per the "never raises" contract).

Settings are patched per-test with `patch.object(notifier.settings, ...)`
so one test's config can't leak into another.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app import notifier


# ─── Helpers ─────────────────────────────────────────────────────────


def _mock_httpx_client(status_code: int = 200, text: str = "ok"):
    """Return a MagicMock that mimics `httpx.Client()` as a context manager.

    `with httpx.Client(timeout=10) as client: client.post(...)` →
    we need the ctx-manager protocol plus a `.post()` that returns a
    response-like object with `.status_code` and `.text`.
    """
    resp = MagicMock(status_code=status_code, text=text)
    client = MagicMock()
    client.post.return_value = resp
    client.get.return_value = resp  # unused by notifier but harmless
    ctx = MagicMock()
    ctx.__enter__.return_value = client
    ctx.__exit__.return_value = False
    return ctx, client, resp


# ─── send_alert gates (early return) ────────────────────────────────


class SendAlertGateTests(unittest.TestCase):
    """send_alert must silently no-op when webhooks aren't configured.

    Triage must never fail because webhooks are disabled. Each gate
    below is a potential regression where a config change would cause
    triage to spawn threads with no URLs to post to (noise) or worse,
    start leaking errors back to the caller.
    """

    def test_returns_when_webhook_disabled(self):
        with patch.object(notifier.settings, "WEBHOOK_ENABLED", False), patch(
            "app.notifier.threading.Thread"
        ) as thread:
            notifier.send_alert("EMERGENCY", "s1", {"reason_tr": "x"}, "HIGH")
            thread.assert_not_called()

    def test_returns_when_no_urls_configured(self):
        with patch.object(notifier.settings, "WEBHOOK_ENABLED", True), patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", ""
        ), patch.object(notifier.settings, "WEBHOOK_DISCORD_URL", ""), patch(
            "app.notifier.threading.Thread"
        ) as thread:
            notifier.send_alert("EMERGENCY", "s1", {"reason_tr": "x"}, "HIGH")
            thread.assert_not_called()

    def test_ignores_non_alertable_envelope_types(self):
        # QUESTION / ERROR / RESULT-LOW should NOT page the on-call.
        with patch.object(notifier.settings, "WEBHOOK_ENABLED", True), patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", "https://slack.test/hook"
        ), patch.object(notifier.settings, "WEBHOOK_DISCORD_URL", ""), patch(
            "app.notifier.threading.Thread"
        ) as thread:
            notifier.send_alert("QUESTION", "s1", {}, None)
            notifier.send_alert("RESULT", "s1", {}, "LOW")
            notifier.send_alert("RESULT", "s1", {}, "MEDIUM")
            thread.assert_not_called()

    def test_emergency_spawns_thread(self):
        with patch.object(notifier.settings, "WEBHOOK_ENABLED", True), patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", "https://slack.test/hook"
        ), patch.object(notifier.settings, "WEBHOOK_DISCORD_URL", ""), patch(
            "app.notifier.threading.Thread"
        ) as thread_cls:
            notifier.send_alert("EMERGENCY", "s1", {"reason_tr": "Göğüs ağrısı"}, None)
            thread_cls.assert_called_once()
            # Check the target + args are what we expect.
            kwargs = thread_cls.call_args.kwargs
            self.assertEqual(kwargs["target"], notifier._dispatch)
            self.assertEqual(kwargs["args"][0], "EMERGENCY")
            self.assertEqual(kwargs["args"][1], "s1")
            self.assertTrue(kwargs["daemon"])

    def test_high_risk_result_spawns_thread(self):
        with patch.object(notifier.settings, "WEBHOOK_ENABLED", True), patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", ""
        ), patch.object(
            notifier.settings, "WEBHOOK_DISCORD_URL", "https://discord.test/hook"
        ), patch("app.notifier.threading.Thread") as thread_cls:
            notifier.send_alert("RESULT", "s1", {"confidence_0_1": 0.88}, "HIGH")
            thread_cls.assert_called_once()


# ─── send_llm_health_alert / send_http_5xx_alert / send_rate_limit_alert ─


class SpecializedAlertGateTests(unittest.TestCase):
    """The 3 specialized alerts share the same 2-gate pattern as send_alert
    but without the envelope-type filter. Guard against regressions where
    someone accidentally flips one gate but not the other."""

    def test_llm_health_respects_webhook_enabled(self):
        with patch.object(notifier.settings, "WEBHOOK_ENABLED", False), patch(
            "app.notifier.threading.Thread"
        ) as thread:
            notifier.send_llm_health_alert(50.0, 100, "timeout", 85.0)
            thread.assert_not_called()

    def test_llm_health_respects_url_presence(self):
        with patch.object(notifier.settings, "WEBHOOK_ENABLED", True), patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", ""
        ), patch.object(notifier.settings, "WEBHOOK_DISCORD_URL", ""), patch(
            "app.notifier.threading.Thread"
        ) as thread:
            notifier.send_llm_health_alert(50.0, 100, "timeout", 85.0)
            thread.assert_not_called()

    def test_llm_health_spawns_when_configured(self):
        with patch.object(notifier.settings, "WEBHOOK_ENABLED", True), patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", "https://slack/h"
        ), patch.object(notifier.settings, "WEBHOOK_DISCORD_URL", ""), patch(
            "app.notifier.threading.Thread"
        ) as thread_cls:
            notifier.send_llm_health_alert(50.0, 100, "timeout", 85.0)
            thread_cls.assert_called_once()
            self.assertEqual(
                thread_cls.call_args.kwargs["target"], notifier._dispatch_llm_health
            )

    def test_http_5xx_respects_webhook_enabled(self):
        with patch.object(notifier.settings, "WEBHOOK_ENABLED", False), patch(
            "app.notifier.threading.Thread"
        ) as thread:
            notifier.send_http_5xx_alert(70.0, 500, "/v1/triage/turn", 500, 95.0)
            thread.assert_not_called()

    def test_http_5xx_spawns_when_configured(self):
        with patch.object(notifier.settings, "WEBHOOK_ENABLED", True), patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", "https://slack/h"
        ), patch.object(notifier.settings, "WEBHOOK_DISCORD_URL", ""), patch(
            "app.notifier.threading.Thread"
        ) as thread_cls:
            notifier.send_http_5xx_alert(70.0, 500, "/v1/triage/turn", 500, 95.0)
            thread_cls.assert_called_once()
            self.assertEqual(
                thread_cls.call_args.kwargs["target"], notifier._dispatch_http_5xx
            )

    def test_rate_limit_respects_webhook_enabled(self):
        with patch.object(notifier.settings, "WEBHOOK_ENABLED", False), patch(
            "app.notifier.threading.Thread"
        ) as thread:
            notifier.send_rate_limit_alert(30.0, 200, "default", "1.2.3.4", 10.0)
            thread.assert_not_called()

    def test_rate_limit_spawns_when_configured(self):
        with patch.object(notifier.settings, "WEBHOOK_ENABLED", True), patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", ""
        ), patch.object(
            notifier.settings, "WEBHOOK_DISCORD_URL", "https://discord/h"
        ), patch("app.notifier.threading.Thread") as thread_cls:
            notifier.send_rate_limit_alert(30.0, 200, "default", "1.2.3.4", 10.0)
            thread_cls.assert_called_once()
            self.assertEqual(
                thread_cls.call_args.kwargs["target"], notifier._dispatch_rate_limit
            )


# ─── _extract_info (pure function) ───────────────────────────────────


class ExtractInfoTests(unittest.TestCase):
    """_extract_info is the single place where envelope → display shape
    happens. Every dispatcher calls it. If EMERGENCY no longer returns
    a red (#C62828) card or if RESULT loses the specialty line, both
    Slack and Discord messages silently degrade."""

    def test_emergency_envelope_maps_to_red_card(self):
        info = notifier._extract_info(
            "EMERGENCY",
            {"reason_tr": "Göğüs ağrısı", "instructions_tr": ["112'yi arayın"]},
            risk_level=None,
        )
        self.assertEqual(info["color"], "#C62828")
        self.assertIn("ACİL", info["title"])
        self.assertEqual(info["reason"], "Göğüs ağrısı")
        self.assertIn("112", info["instructions"])
        self.assertEqual(info["risk"], "EMERGENCY")

    def test_emergency_without_instructions_uses_dash(self):
        info = notifier._extract_info(
            "EMERGENCY", {"reason_tr": "x"}, risk_level=None
        )
        self.assertEqual(info["instructions"], "-")

    def test_emergency_without_reason_falls_back_to_default(self):
        info = notifier._extract_info("EMERGENCY", {}, risk_level=None)
        # Module promises a Turkish fallback rather than an empty string.
        self.assertEqual(info["reason"], "Bilinmeyen acil durum")

    def test_result_envelope_maps_to_amber_card(self):
        info = notifier._extract_info(
            "RESULT",
            {
                "recommended_specialty": {"id": "cardiology", "name_tr": "Kardiyoloji"},
                "confidence_0_1": 0.82,
                "stop_reason": "HIGH_CONFIDENCE_SINGLE_DISEASE",
            },
            risk_level="HIGH",
        )
        self.assertEqual(info["color"], "#F57F17")
        self.assertIn("YÜKSEK RİSK", info["title"])
        self.assertEqual(info["specialty"], "Kardiyoloji")
        self.assertEqual(info["confidence"], "82%")
        self.assertIn("HIGH_CONFIDENCE_SINGLE_DISEASE", info["instructions"])
        self.assertEqual(info["risk"], "HIGH")

    def test_result_without_confidence_shows_question_mark(self):
        info = notifier._extract_info(
            "RESULT",
            {"recommended_specialty": {"name_tr": "Dahiliye"}},
            risk_level="HIGH",
        )
        self.assertEqual(info["confidence"], "?")

    def test_result_with_non_dict_specialty_coerces_to_string(self):
        # Defensive: some legacy envelopes pass a bare string.
        info = notifier._extract_info(
            "RESULT",
            {"recommended_specialty": "Kardiyoloji", "confidence_0_1": 0.7},
            risk_level="HIGH",
        )
        self.assertEqual(info["specialty"], "Kardiyoloji")

    def test_result_risk_level_fallback_to_high_when_none(self):
        # risk_level=None on a RESULT is pathological (should be HIGH to
        # even get here) but we must not crash — coerce to "HIGH".
        info = notifier._extract_info(
            "RESULT",
            {"recommended_specialty": {"name_tr": "x"}, "confidence_0_1": 0.5},
            risk_level=None,
        )
        self.assertEqual(info["risk"], "HIGH")


# ─── _dispatch (EMERGENCY/RESULT main alert body) ────────────────────


class DispatchBodyTests(unittest.TestCase):
    """_dispatch is what the background thread actually runs for
    send_alert. Asserts the Slack/Discord POSTs actually happen with
    the right bodies."""

    def test_dispatch_slack_only_when_discord_missing(self):
        ctx, client, _ = _mock_httpx_client()
        with patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", "https://slack/h"
        ), patch.object(notifier.settings, "WEBHOOK_DISCORD_URL", ""), patch(
            "app.notifier.httpx.Client", return_value=ctx
        ):
            notifier._dispatch(
                "EMERGENCY", "sess-1", {"reason_tr": "x"}, None
            )
            client.post.assert_called_once()
            # Post URL should be the Slack URL.
            args, kwargs = client.post.call_args
            self.assertEqual(args[0], "https://slack/h")
            self.assertIn("blocks", kwargs["json"])

    def test_dispatch_discord_only_when_slack_missing(self):
        ctx, client, _ = _mock_httpx_client()
        with patch.object(notifier.settings, "WEBHOOK_SLACK_URL", ""), patch.object(
            notifier.settings, "WEBHOOK_DISCORD_URL", "https://discord/h"
        ), patch("app.notifier.httpx.Client", return_value=ctx):
            notifier._dispatch("EMERGENCY", "sess-1", {"reason_tr": "x"}, None)
            client.post.assert_called_once()
            args, kwargs = client.post.call_args
            self.assertEqual(args[0], "https://discord/h")
            self.assertIn("embeds", kwargs["json"])

    def test_dispatch_posts_to_both_channels_when_both_configured(self):
        ctx, client, _ = _mock_httpx_client()
        with patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", "https://slack/h"
        ), patch.object(
            notifier.settings, "WEBHOOK_DISCORD_URL", "https://discord/h"
        ), patch("app.notifier.httpx.Client", return_value=ctx):
            notifier._dispatch(
                "EMERGENCY", "sess-1", {"reason_tr": "x"}, None
            )
            self.assertEqual(client.post.call_count, 2)

    def test_dispatch_swallows_slack_exceptions(self):
        # Thread target must never raise — triage already completed.
        with patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", "https://slack/h"
        ), patch.object(notifier.settings, "WEBHOOK_DISCORD_URL", ""), patch(
            "app.notifier.httpx.Client", side_effect=RuntimeError("DNS fail")
        ):
            # Should not raise.
            notifier._dispatch("EMERGENCY", "s1", {"reason_tr": "x"}, None)

    def test_dispatch_logs_on_4xx_but_does_not_raise(self):
        ctx, client, _ = _mock_httpx_client(status_code=429, text="rate limited")
        with patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", "https://slack/h"
        ), patch.object(notifier.settings, "WEBHOOK_DISCORD_URL", ""), patch(
            "app.notifier.httpx.Client", return_value=ctx
        ):
            # Logger.warning is called internally; just ensure no raise.
            notifier._dispatch("EMERGENCY", "s1", {"reason_tr": "x"}, None)
            client.post.assert_called_once()


# ─── _send_slack / _send_discord body shape ──────────────────────────


class SlackBodyShapeTests(unittest.TestCase):
    """The Slack Block Kit body is what makes the pager message readable.
    Pin the top-level block types so a refactor that accidentally
    removes the header or context (timestamp footer) is caught."""

    def test_slack_body_has_header_divider_section_context(self):
        ctx, client, _ = _mock_httpx_client()
        with patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", "https://slack/h"
        ), patch("app.notifier.httpx.Client", return_value=ctx):
            notifier._send_slack(
                "EMERGENCY", "sess-abc-123", {"reason_tr": "Göğüs ağrısı"}, None
            )
            body = client.post.call_args.kwargs["json"]
            types = [b.get("type") for b in body["blocks"]]
            self.assertIn("header", types)
            self.assertIn("divider", types)
            self.assertIn("section", types)
            self.assertIn("context", types)
            # Session ID must be truncated for PII safety — first 8 chars + …
            body_str = str(body)
            self.assertIn("sess-abc", body_str)
            # The un-truncated ID should NOT appear.
            self.assertNotIn("sess-abc-123", body_str)


class DiscordBodyShapeTests(unittest.TestCase):
    """Discord embed has a different shape (int color, fields array)."""

    def test_discord_color_is_int_not_hex_string(self):
        ctx, client, _ = _mock_httpx_client()
        with patch.object(
            notifier.settings, "WEBHOOK_DISCORD_URL", "https://discord/h"
        ), patch("app.notifier.httpx.Client", return_value=ctx):
            notifier._send_discord(
                "EMERGENCY", "s1", {"reason_tr": "x"}, None
            )
            body = client.post.call_args.kwargs["json"]
            embed = body["embeds"][0]
            # #C62828 == 12986408 in decimal; Discord requires int.
            self.assertEqual(embed["color"], 0xC62828)
            self.assertIsInstance(embed["color"], int)

    def test_discord_embed_has_expected_field_names(self):
        ctx, client, _ = _mock_httpx_client()
        with patch.object(
            notifier.settings, "WEBHOOK_DISCORD_URL", "https://discord/h"
        ), patch("app.notifier.httpx.Client", return_value=ctx):
            notifier._send_discord(
                "RESULT",
                "s1",
                {
                    "recommended_specialty": {"name_tr": "Kardiyoloji"},
                    "confidence_0_1": 0.7,
                    "stop_reason": "x",
                },
                "HIGH",
            )
            body = client.post.call_args.kwargs["json"]
            names = [f["name"] for f in body["embeds"][0]["fields"]]
            for expected in ("Oturum", "Risk", "Uzmanlık", "Güven", "Sebep"):
                self.assertIn(expected, names)


# ─── Specialized dispatchers (direct bodies) ─────────────────────────


class LlmHealthDispatchTests(unittest.TestCase):
    def test_slack_body_contains_threshold_and_window(self):
        ctx, client, _ = _mock_httpx_client()
        with patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", "https://slack/h"
        ), patch.object(notifier.settings, "WEBHOOK_DISCORD_URL", ""), patch(
            "app.notifier.httpx.Client", return_value=ctx
        ):
            notifier._dispatch_llm_health(
                success_rate_pct=42.3,
                window_size=100,
                top_error="timeout",
                threshold_pct=85.0,
            )
            body = client.post.call_args.kwargs["json"]
            body_str = str(body)
            self.assertIn("42.3", body_str)  # success rate
            self.assertIn("100", body_str)  # window size
            self.assertIn("timeout", body_str)  # top error
            self.assertIn("85", body_str)  # threshold

    def test_slack_body_handles_none_top_error_gracefully(self):
        ctx, client, _ = _mock_httpx_client()
        with patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", "https://slack/h"
        ), patch.object(notifier.settings, "WEBHOOK_DISCORD_URL", ""), patch(
            "app.notifier.httpx.Client", return_value=ctx
        ):
            notifier._dispatch_llm_health(
                success_rate_pct=50.0,
                window_size=50,
                top_error=None,
                threshold_pct=85.0,
            )
            body_str = str(client.post.call_args.kwargs["json"])
            self.assertIn("N/A", body_str)

    def test_discord_body_has_error_field(self):
        ctx, client, _ = _mock_httpx_client()
        with patch.object(notifier.settings, "WEBHOOK_SLACK_URL", ""), patch.object(
            notifier.settings, "WEBHOOK_DISCORD_URL", "https://discord/h"
        ), patch("app.notifier.httpx.Client", return_value=ctx):
            notifier._dispatch_llm_health(50.0, 100, "401 Unauthorized", 85.0)
            body = client.post.call_args.kwargs["json"]
            fields = body["embeds"][0]["fields"]
            error_field = next(f for f in fields if f["name"] == "En sık hata")
            self.assertEqual(error_field["value"], "401 Unauthorized")

    def test_swallows_exceptions(self):
        with patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", "https://slack/h"
        ), patch.object(
            notifier.settings, "WEBHOOK_DISCORD_URL", "https://discord/h"
        ), patch("app.notifier.httpx.Client", side_effect=RuntimeError("x")):
            # Must not raise — the thread that calls this has nobody to catch.
            notifier._dispatch_llm_health(50.0, 100, "e", 85.0)


class Http5xxDispatchTests(unittest.TestCase):
    def test_slack_body_uses_error_rate_in_title(self):
        ctx, client, _ = _mock_httpx_client()
        with patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", "https://slack/h"
        ), patch.object(notifier.settings, "WEBHOOK_DISCORD_URL", ""), patch(
            "app.notifier.httpx.Client", return_value=ctx
        ):
            notifier._dispatch_http_5xx(
                success_rate_pct=70.0,
                window_size=500,
                top_path="/v1/triage/turn",
                top_status=500,
                threshold_pct=95.0,
            )
            body = client.post.call_args.kwargs["json"]
            # Title should include the error rate (100 - 70 = 30%).
            self.assertIn("30", body["text"])
            body_str = str(body)
            self.assertIn("/v1/triage/turn", body_str)

    def test_handles_missing_path_gracefully(self):
        ctx, client, _ = _mock_httpx_client()
        with patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", "https://slack/h"
        ), patch.object(notifier.settings, "WEBHOOK_DISCORD_URL", ""), patch(
            "app.notifier.httpx.Client", return_value=ctx
        ):
            notifier._dispatch_http_5xx(70.0, 500, None, None, 95.0)
            body_str = str(client.post.call_args.kwargs["json"])
            self.assertIn("Yol bilgisi yok", body_str)

    def test_swallows_exceptions(self):
        with patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", "https://slack/h"
        ), patch.object(
            notifier.settings, "WEBHOOK_DISCORD_URL", "https://discord/h"
        ), patch("app.notifier.httpx.Client", side_effect=RuntimeError("x")):
            notifier._dispatch_http_5xx(70.0, 500, "/x", 500, 95.0)


class RateLimitDispatchTests(unittest.TestCase):
    def test_slack_body_surfaces_bucket_and_key(self):
        ctx, client, _ = _mock_httpx_client()
        with patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", "https://slack/h"
        ), patch.object(notifier.settings, "WEBHOOK_DISCORD_URL", ""), patch(
            "app.notifier.httpx.Client", return_value=ctx
        ):
            notifier._dispatch_rate_limit(
                rejection_rate_pct=25.5,
                window_size=200,
                top_bucket="admin",
                top_key="1.2.3.4",
                threshold_pct=10.0,
            )
            body_str = str(client.post.call_args.kwargs["json"])
            self.assertIn("admin", body_str)
            self.assertIn("1.2.3.4", body_str)
            self.assertIn("25.5", body_str)

    def test_handles_missing_bucket_gracefully(self):
        ctx, client, _ = _mock_httpx_client()
        with patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", "https://slack/h"
        ), patch.object(notifier.settings, "WEBHOOK_DISCORD_URL", ""), patch(
            "app.notifier.httpx.Client", return_value=ctx
        ):
            notifier._dispatch_rate_limit(25.5, 200, None, None, 10.0)
            body_str = str(client.post.call_args.kwargs["json"])
            self.assertIn("Bucket bilgisi yok", body_str)

    def test_discord_body_has_top_key_field(self):
        ctx, client, _ = _mock_httpx_client()
        with patch.object(notifier.settings, "WEBHOOK_SLACK_URL", ""), patch.object(
            notifier.settings, "WEBHOOK_DISCORD_URL", "https://discord/h"
        ), patch("app.notifier.httpx.Client", return_value=ctx):
            notifier._dispatch_rate_limit(25.5, 200, "default", "5.5.5.5", 10.0)
            body = client.post.call_args.kwargs["json"]
            fields = body["embeds"][0]["fields"]
            key_field = next(f for f in fields if f["name"] == "Top key")
            self.assertEqual(key_field["value"], "5.5.5.5")

    def test_swallows_exceptions(self):
        with patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", "https://slack/h"
        ), patch.object(
            notifier.settings, "WEBHOOK_DISCORD_URL", "https://discord/h"
        ), patch("app.notifier.httpx.Client", side_effect=RuntimeError("x")):
            notifier._dispatch_rate_limit(25.5, 200, "default", "1.1.1.1", 10.0)


# ─── send_test (synchronous) ────────────────────────────────────────


class SendTestHelperTests(unittest.TestCase):
    """`send_test` is called from the admin UI to verify webhook URL
    configuration. Unlike the other `send_*` functions, it runs
    synchronously and returns a results dict."""

    def test_returns_empty_dict_shape_when_no_urls_configured(self):
        with patch.object(notifier.settings, "WEBHOOK_SLACK_URL", ""), patch.object(
            notifier.settings, "WEBHOOK_DISCORD_URL", ""
        ):
            result = notifier.send_test()
            self.assertEqual(result, {"slack": None, "discord": None})

    def test_reports_slack_success(self):
        ctx, client, _ = _mock_httpx_client(status_code=200)
        with patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", "https://slack/h"
        ), patch.object(notifier.settings, "WEBHOOK_DISCORD_URL", ""), patch(
            "app.notifier.httpx.Client", return_value=ctx
        ):
            result = notifier.send_test()
            self.assertEqual(result["slack"], {"ok": True, "status": 200})
            self.assertIsNone(result["discord"])

    def test_reports_discord_success(self):
        ctx, client, _ = _mock_httpx_client(status_code=204)
        with patch.object(notifier.settings, "WEBHOOK_SLACK_URL", ""), patch.object(
            notifier.settings, "WEBHOOK_DISCORD_URL", "https://discord/h"
        ), patch("app.notifier.httpx.Client", return_value=ctx):
            result = notifier.send_test()
            self.assertEqual(result["discord"], {"ok": True, "status": 204})
            self.assertIsNone(result["slack"])

    def test_reports_4xx_as_not_ok(self):
        ctx, client, _ = _mock_httpx_client(status_code=401)
        with patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", "https://slack/h"
        ), patch.object(notifier.settings, "WEBHOOK_DISCORD_URL", ""), patch(
            "app.notifier.httpx.Client", return_value=ctx
        ):
            result = notifier.send_test()
            self.assertEqual(result["slack"], {"ok": False, "status": 401})

    def test_reports_exception_as_error(self):
        with patch.object(
            notifier.settings, "WEBHOOK_SLACK_URL", "https://slack/h"
        ), patch.object(notifier.settings, "WEBHOOK_DISCORD_URL", ""), patch(
            "app.notifier.httpx.Client", side_effect=RuntimeError("DNS fail")
        ):
            result = notifier.send_test()
            self.assertFalse(result["slack"]["ok"])
            self.assertIn("DNS fail", result["slack"]["error"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
