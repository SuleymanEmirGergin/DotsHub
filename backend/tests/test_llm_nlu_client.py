"""Unit tests for app.services.llm_nlu_client.

Covers:
  - Wiro auth header helpers (_wiro_api_key, _wiro_auth_headers)
  - Wiro submit/poll lifecycle (_wiro_submit, _wiro_poll)
  - Text extraction from Wiro task outputs (_extract_wiro_text, _extract_wiro_usage)
  - Direct REST providers (google / openai / anthropic) via _direct_call
  - NLUDirectClient public API: call/close, retry-on-transient, error propagation
  - get_nlu_client singleton
"""

from __future__ import annotations

import hashlib
import hmac
import time
import unittest
from unittest.mock import MagicMock, patch

import httpx

from app.services import llm_nlu_client as mod


# ---------------------------------------------------------------------------
# Wiro auth header tests
# ---------------------------------------------------------------------------


class WiroAuthTests(unittest.TestCase):
    def test_api_key_prefers_llm_api_key(self):
        with patch.object(mod.settings, "LLM_API_KEY", "llm-k"), \
             patch.object(mod.settings, "WIRO_API_KEY", "wiro-k"):
            self.assertEqual(mod._wiro_api_key(), "llm-k")

    def test_api_key_falls_back_to_wiro_api_key(self):
        with patch.object(mod.settings, "LLM_API_KEY", ""), \
             patch.object(mod.settings, "WIRO_API_KEY", "wiro-k"):
            self.assertEqual(mod._wiro_api_key(), "wiro-k")

    def test_auth_headers_legacy_when_no_secret(self):
        with patch.object(mod.settings, "LLM_API_KEY", "k"), \
             patch.object(mod.settings, "WIRO_API_KEY", ""), \
             patch.object(mod.settings, "WIRO_API_SECRET", ""):
            headers = mod._wiro_auth_headers()
        self.assertEqual(headers, {"x-api-key": "k"})
        self.assertNotIn("x-signature", headers)

    def test_auth_headers_hmac_signed_when_secret_set(self):
        with patch.object(mod.settings, "LLM_API_KEY", "key"), \
             patch.object(mod.settings, "WIRO_API_KEY", ""), \
             patch.object(mod.settings, "WIRO_API_SECRET", "shh"), \
             patch("app.services.llm_nlu_client.time.time", return_value=1700000000):
            headers = mod._wiro_auth_headers()
        self.assertEqual(headers["x-api-key"], "key")
        self.assertEqual(headers["x-nonce"], "1700000000")
        expected_sig = hmac.new(
            b"key", b"shh1700000000", hashlib.sha256,
        ).hexdigest()
        self.assertEqual(headers["x-signature"], expected_sig)


class WiroBaseTests(unittest.TestCase):
    def test_base_strips_trailing_slash(self):
        with patch.object(mod.settings, "WIRO_BASE_URL", "https://api.wiro.ai/"):
            self.assertEqual(mod._wiro_base(), "https://api.wiro.ai")

    def test_base_no_trailing_slash_untouched(self):
        with patch.object(mod.settings, "WIRO_BASE_URL", "https://api.wiro.ai"):
            self.assertEqual(mod._wiro_base(), "https://api.wiro.ai")


class WiroPromptTests(unittest.TestCase):
    def test_build_wiro_prompt_includes_system_user_and_json_hint(self):
        p = mod._build_wiro_prompt("SYS", "USR")
        self.assertIn("SYS", p)
        self.assertIn("USR", p)
        self.assertIn("valid JSON object", p)


# ---------------------------------------------------------------------------
# Helper: build a MagicMock that stands in for httpx.Client with scripted post/get
# ---------------------------------------------------------------------------


def _ok_resp(json_body):
    r = MagicMock(spec=httpx.Response)
    r.json.return_value = json_body
    r.raise_for_status.return_value = None
    r.text = ""
    r.status_code = 200
    return r


# ---------------------------------------------------------------------------
# _wiro_submit
# ---------------------------------------------------------------------------


class WiroSubmitTests(unittest.TestCase):
    def test_returns_token_when_result_true(self):
        client = MagicMock()
        client.post.return_value = _ok_resp({
            "result": True,
            "socketaccesstoken": "tok-abc",
        })
        with patch.object(mod.settings, "WIRO_BASE_URL", "https://api.wiro.ai"), \
             patch.object(mod.settings, "LLM_API_KEY", "k"), \
             patch.object(mod.settings, "WIRO_API_SECRET", ""):
            token = mod._wiro_submit(client, "google/gemini-2-5-flash", "prompt")
        self.assertEqual(token, "tok-abc")
        # url should include the model suffix
        url_arg = client.post.call_args.args[0]
        self.assertTrue(url_arg.endswith("/v1/Run/google/gemini-2-5-flash"))

    def test_raises_when_result_false(self):
        client = MagicMock()
        client.post.return_value = _ok_resp({"result": False, "errors": "nope"})
        with patch.object(mod.settings, "WIRO_BASE_URL", "https://api.wiro.ai"), \
             patch.object(mod.settings, "LLM_API_KEY", "k"), \
             patch.object(mod.settings, "WIRO_API_SECRET", ""):
            with self.assertRaises(RuntimeError) as cm:
                mod._wiro_submit(client, "m", "p")
        self.assertIn("Wiro submit failed", str(cm.exception))

    def test_raises_when_token_missing(self):
        client = MagicMock()
        client.post.return_value = _ok_resp({"result": True})
        with patch.object(mod.settings, "WIRO_BASE_URL", "https://api.wiro.ai"), \
             patch.object(mod.settings, "LLM_API_KEY", "k"), \
             patch.object(mod.settings, "WIRO_API_SECRET", ""):
            with self.assertRaises(RuntimeError) as cm:
                mod._wiro_submit(client, "m", "p")
        self.assertIn("missing socketaccesstoken", str(cm.exception))


# ---------------------------------------------------------------------------
# _wiro_poll
# ---------------------------------------------------------------------------


class WiroPollTests(unittest.TestCase):
    """All tests share the same Wiro-settings patches. The previous
    pattern built a tuple of `patch.object(...)` twice per test (once
    to `__enter__`, once to `__exit__`) which works on Python 3.14
    but fails on 3.11 (CI) with
    `AttributeError: '_patch' object has no attribute 'is_local'` —
    `__exit__` was being called on newly-constructed, never-entered
    patch objects. Use setUp + addCleanup to tie each patch's
    lifecycle to the test runner correctly.
    """

    def setUp(self):
        for patcher in (
            patch.object(mod.settings, "WIRO_BASE_URL", "https://api.wiro.ai"),
            patch.object(mod.settings, "LLM_NLU_POLL_INTERVAL_SECONDS", 0.001),
            patch.object(mod.settings, "LLM_NLU_TIMEOUT_SECONDS", 5),
            patch.object(mod.settings, "LLM_API_KEY", "k"),
            patch.object(mod.settings, "WIRO_API_SECRET", ""),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_returns_task_when_status_terminal_success(self):
        client = MagicMock()
        client.post.return_value = _ok_resp({
            "tasklist": [{"status": "task_end", "debugoutput": "done"}],
        })
        task = mod._wiro_poll(client, "tok", deadline=time.monotonic() + 10)
        self.assertEqual(task["status"], "task_end")

    def test_raises_runtime_error_on_terminal_error(self):
        client = MagicMock()
        client.post.return_value = _ok_resp({
            "tasklist": [{"status": "task_error", "debugerror": "upstream 500"}],
        })
        with self.assertRaises(RuntimeError) as cm:
            mod._wiro_poll(client, "tok", deadline=time.monotonic() + 10)
        self.assertIn("Wiro task failed", str(cm.exception))
        self.assertIn("upstream 500", str(cm.exception))

    def test_raises_timeout_when_deadline_passed(self):
        client = MagicMock()
        client.post.return_value = _ok_resp({
            "tasklist": [{"status": "running"}],
        })
        with self.assertRaises(TimeoutError):
            mod._wiro_poll(client, "tok", deadline=time.monotonic() - 1)

    def test_raises_runtime_error_on_empty_tasklist(self):
        client = MagicMock()
        client.post.return_value = _ok_resp({"tasklist": []})
        with self.assertRaises(RuntimeError) as cm:
            mod._wiro_poll(client, "tok", deadline=time.monotonic() + 10)
        self.assertIn("empty tasklist", str(cm.exception))

    def test_poll_retries_until_success(self):
        client = MagicMock()
        # First two calls: running; third: done.
        client.post.side_effect = [
            _ok_resp({"tasklist": [{"status": "running"}]}),
            _ok_resp({"tasklist": [{"status": "running"}]}),
            _ok_resp({"tasklist": [{"status": "task_postprocess_end", "debugoutput": "ok"}]}),
        ]
        task = mod._wiro_poll(client, "tok", deadline=time.monotonic() + 10)
        self.assertEqual(task["debugoutput"], "ok")
        self.assertEqual(client.post.call_count, 3)


# ---------------------------------------------------------------------------
# _extract_wiro_text / _extract_wiro_usage
# ---------------------------------------------------------------------------


class ExtractWiroTextTests(unittest.TestCase):
    def test_returns_debugoutput_when_present(self):
        self.assertEqual(mod._extract_wiro_text({"debugoutput": "  hi  "}), "hi")

    def test_returns_result_when_no_debugoutput(self):
        self.assertEqual(mod._extract_wiro_text({"result": "payload"}), "payload")

    def test_fetches_text_from_output_url(self):
        task = {
            "outputs": [
                {"contenttype": "text/plain", "url": "https://cdn/foo.txt"},
            ],
        }
        fake_resp = MagicMock(text="remote text\n")
        fake_resp.raise_for_status.return_value = None
        with patch("app.services.llm_nlu_client.httpx.get", return_value=fake_resp):
            out = mod._extract_wiro_text(task)
        self.assertEqual(out, "remote text")

    def test_json_contenttype_is_also_fetched(self):
        task = {
            "outputs": [
                {"contenttype": "application/json", "url": "https://cdn/foo.json"},
            ],
        }
        fake_resp = MagicMock(text='{"k":"v"}')
        fake_resp.raise_for_status.return_value = None
        with patch("app.services.llm_nlu_client.httpx.get", return_value=fake_resp):
            out = mod._extract_wiro_text(task)
        self.assertEqual(out, '{"k":"v"}')

    def test_raises_when_no_text_found_anywhere(self):
        with self.assertRaises(RuntimeError) as cm:
            mod._extract_wiro_text({"outputs": []})
        self.assertIn("no text output", str(cm.exception))

    def test_url_fetch_failure_falls_through_to_raise(self):
        task = {
            "outputs": [
                {"contenttype": "text/plain", "url": "https://cdn/x"},
            ],
        }
        with patch(
            "app.services.llm_nlu_client.httpx.get",
            side_effect=httpx.ConnectError("boom"),
        ):
            with self.assertRaises(RuntimeError):
                mod._extract_wiro_text(task)

    def test_non_dict_output_skipped(self):
        task = {"outputs": ["not-a-dict", {"contenttype": "image/png", "url": "x"}]}
        with self.assertRaises(RuntimeError):
            mod._extract_wiro_text(task)


class ExtractWiroUsageTests(unittest.TestCase):
    def test_always_returns_zero_zero(self):
        self.assertEqual(mod._extract_wiro_usage({}), (0, 0))
        self.assertEqual(
            mod._extract_wiro_usage({"totalcost": 1.23}),
            (0, 0),
        )


# ---------------------------------------------------------------------------
# _direct_call
# ---------------------------------------------------------------------------


class DirectCallTests(unittest.TestCase):
    def test_anthropic_extracts_text_and_usage(self):
        client = MagicMock()
        client.post.return_value = _ok_resp({
            "content": [
                {"type": "text", "text": "hello"},
                {"type": "other", "text": "ignore"},
            ],
            "usage": {"input_tokens": 12, "output_tokens": 7},
        })
        with patch.object(mod.settings, "LLM_API_KEY", "ak"):
            text, in_tok, out_tok = mod._direct_call(
                client, "anthropic", "claude-3", "sys", "user",
            )
        self.assertEqual(text, "hello")
        self.assertEqual((in_tok, out_tok), (12, 7))
        # Headers should use anthropic's x-api-key schema.
        headers = client.post.call_args.kwargs["headers"]
        self.assertEqual(headers["x-api-key"], "ak")
        self.assertIn("anthropic-version", headers)

    def test_google_uses_openai_compat_schema(self):
        client = MagicMock()
        client.post.return_value = _ok_resp({
            "choices": [{"message": {"content": "reply"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        })
        with patch.object(mod.settings, "LLM_API_KEY", "gk"):
            text, in_tok, out_tok = mod._direct_call(
                client, "google", "gemini-2.5-flash", "sys", "user",
            )
        self.assertEqual(text, "reply")
        self.assertEqual((in_tok, out_tok), (5, 3))
        url_arg = client.post.call_args.args[0]
        self.assertIn("generativelanguage.googleapis.com", url_arg)

    def test_openai_uses_openai_url(self):
        client = MagicMock()
        client.post.return_value = _ok_resp({
            "choices": [{"message": {"content": "hi"}}],
            "usage": {},
        })
        with patch.object(mod.settings, "LLM_API_KEY", "oa"):
            text, _, _ = mod._direct_call(client, "openai", "gpt-x", "sys", "user")
        self.assertEqual(text, "hi")
        url_arg = client.post.call_args.args[0]
        self.assertIn("api.openai.com", url_arg)

    def test_openai_compat_raises_on_empty_choices(self):
        client = MagicMock()
        client.post.return_value = _ok_resp({"choices": []})
        with patch.object(mod.settings, "LLM_API_KEY", "k"):
            with self.assertRaises(ValueError) as cm:
                mod._direct_call(client, "openai", "m", "s", "u")
        self.assertIn("No choices", str(cm.exception))


# ---------------------------------------------------------------------------
# NLUDirectClient
# ---------------------------------------------------------------------------


class NLUDirectClientInitTests(unittest.TestCase):
    def test_defaults_pulled_from_settings(self):
        with patch.object(mod.settings, "LLM_PROVIDER", "Wiro"), \
             patch.object(mod.settings, "LLM_NLU_MODEL", "m"), \
             patch.object(mod.settings, "LLM_NLU_TIMEOUT_SECONDS", 2.5):
            c = mod.NLUDirectClient()
            try:
                self.assertEqual(c.provider, "wiro")  # lowercased
                self.assertEqual(c.model, "m")
                self.assertEqual(c.timeout, 2.5)
            finally:
                c.close()

    def test_explicit_overrides_win(self):
        c = mod.NLUDirectClient(provider="OPENAI", model="x", timeout=0.5)
        try:
            self.assertEqual(c.provider, "openai")
            self.assertEqual(c.model, "x")
            self.assertEqual(c.timeout, 0.5)
        finally:
            c.close()


class NLUDirectClientCallTests(unittest.TestCase):
    def test_wiro_path_end_to_end(self):
        with patch.object(mod.settings, "LLM_PROVIDER", "wiro"), \
             patch.object(mod.settings, "LLM_NLU_MODEL", "m"), \
             patch.object(mod.settings, "LLM_NLU_TIMEOUT_SECONDS", 2.0):
            c = mod.NLUDirectClient()
        try:
            with patch("app.services.llm_nlu_client._wiro_submit", return_value="tok"), \
                 patch(
                    "app.services.llm_nlu_client._wiro_poll",
                    return_value={"debugoutput": "  reply  "},
                 ), \
                 patch("app.services.llm_nlu_client.redact_pii", side_effect=lambda x: x):
                text, in_tok, out_tok = c.call("sys", "user")
            self.assertEqual(text, "reply")
            self.assertEqual((in_tok, out_tok), (0, 0))
        finally:
            c.close()

    def test_google_path_uses_direct_call(self):
        c = mod.NLUDirectClient(provider="google", model="m", timeout=1.0)
        try:
            with patch(
                "app.services.llm_nlu_client._direct_call",
                return_value=("ok", 4, 2),
            ), patch("app.services.llm_nlu_client.redact_pii", side_effect=lambda x: x):
                text, in_tok, out_tok = c.call("s", "u")
            self.assertEqual((text, in_tok, out_tok), ("ok", 4, 2))
        finally:
            c.close()

    def test_unknown_provider_raises_value_error(self):
        c = mod.NLUDirectClient(provider="llama", model="m", timeout=1.0)
        try:
            with patch("app.services.llm_nlu_client.redact_pii", side_effect=lambda x: x):
                with self.assertRaises(ValueError) as cm:
                    c.call("s", "u")
            self.assertIn("Unsupported LLM_PROVIDER", str(cm.exception))
        finally:
            c.close()

    def test_transient_error_retries_once_then_raises(self):
        c = mod.NLUDirectClient(provider="google", model="m", timeout=1.0)
        try:
            with patch(
                "app.services.llm_nlu_client._direct_call",
                side_effect=httpx.ConnectError("net down"),
            ), patch("app.services.llm_nlu_client.redact_pii", side_effect=lambda x: x), \
                 patch("app.services.llm_nlu_client.time.sleep", return_value=None):
                with self.assertRaises(httpx.ConnectError):
                    c.call("s", "u")
        finally:
            c.close()

    def test_transient_error_then_success_on_retry(self):
        c = mod.NLUDirectClient(provider="google", model="m", timeout=1.0)
        try:
            call_history = {"n": 0}

            def flaky(client, provider, model, system, user):
                call_history["n"] += 1
                if call_history["n"] == 1:
                    raise httpx.TimeoutException("slow")
                return "ok", 1, 1

            with patch(
                "app.services.llm_nlu_client._direct_call",
                side_effect=flaky,
            ), patch("app.services.llm_nlu_client.redact_pii", side_effect=lambda x: x), \
                 patch("app.services.llm_nlu_client.time.sleep", return_value=None):
                out = c.call("s", "u")
            self.assertEqual(out, ("ok", 1, 1))
            self.assertEqual(call_history["n"], 2)
        finally:
            c.close()

    def test_http_status_error_not_retried(self):
        c = mod.NLUDirectClient(provider="google", model="m", timeout=1.0)
        try:
            fake_resp = MagicMock(status_code=429, request=MagicMock())
            err = httpx.HTTPStatusError("429", request=fake_resp.request, response=fake_resp)
            with patch(
                "app.services.llm_nlu_client._direct_call",
                side_effect=err,
            ), patch("app.services.llm_nlu_client.redact_pii", side_effect=lambda x: x):
                with self.assertRaises(httpx.HTTPStatusError):
                    c.call("s", "u")
        finally:
            c.close()

    def test_pii_redaction_applied_before_dispatch(self):
        c = mod.NLUDirectClient(provider="google", model="m", timeout=1.0)
        try:
            captured = {}

            def cap(client, provider, model, system, user):
                captured["user"] = user
                return "ok", 0, 0

            with patch(
                "app.services.llm_nlu_client._direct_call",
                side_effect=cap,
            ), patch(
                "app.services.llm_nlu_client.redact_pii",
                side_effect=lambda s: "<REDACTED>",
            ):
                c.call("sys", "secret-pii-email@example.com")
            self.assertEqual(captured["user"], "<REDACTED>")
        finally:
            c.close()


# ---------------------------------------------------------------------------
# get_nlu_client singleton
# ---------------------------------------------------------------------------


class SingletonTests(unittest.TestCase):
    def test_returns_same_instance_on_repeat_calls(self):
        # Clear singleton first.
        mod._nlu_client = None
        a = mod.get_nlu_client()
        b = mod.get_nlu_client()
        try:
            self.assertIs(a, b)
            self.assertIsInstance(a, mod.NLUDirectClient)
        finally:
            a.close()
            mod._nlu_client = None


if __name__ == "__main__":
    unittest.main()
