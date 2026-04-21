"""Unit tests for app.core.llm_client.LLMClient (async Wiro client).

Covers:
  - __init__ + _auth_headers (legacy + HMAC)
  - _build_prompt (json vs text)
  - _run_task / _get_task_detail / _wait_for_task_completion
  - _extract_task_text / _extract_text_from_output_urls
  - Static helpers: _strip_markdown_code_fence, _extract_json_block
  - chat / chat_json (happy + retry + JSON-recovery paths)

Uses asyncio.run(...) directly — matches the pattern in
test_rate_limit_branches.py.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.core import llm_client as mod


def _async_resp(json_body, text: str = ""):
    """Build a response-like object with json() returning the given body."""
    r = MagicMock(spec=httpx.Response)
    r.json.return_value = json_body
    r.raise_for_status.return_value = None
    r.text = text
    r.status_code = 200
    return r


def _fresh_client():
    """LLMClient instance with .client replaced by a plain MagicMock."""
    c = mod.LLMClient(api_key="k", model="m", temperature=0.1)
    # Replace httpx.AsyncClient with a controllable mock.
    c.client = MagicMock()
    c.client.post = AsyncMock()
    c.client.get = AsyncMock()
    return c


# ---------------------------------------------------------------------------
# Init / auth / prompt
# ---------------------------------------------------------------------------


class InitTests(unittest.TestCase):
    def test_defaults_pulled_from_settings(self):
        with patch.object(mod.settings, "LLM_MODEL", "gp"), \
             patch.object(mod.settings, "TEMPERATURE", 0.3), \
             patch.object(mod.settings, "WIRO_API_KEY", "wk"), \
             patch.object(mod.settings, "WIRO_BASE_URL", "https://w/"):
            c = mod.LLMClient()
        self.assertEqual(c.model, "gp")
        self.assertEqual(c.temperature, 0.3)
        self.assertEqual(c.api_key, "wk")
        self.assertEqual(c.base_url, "https://w")  # trailing slash stripped

    def test_explicit_overrides(self):
        c = mod.LLMClient(api_key="x", model="y", temperature=0.9)
        self.assertEqual(c.api_key, "x")
        self.assertEqual(c.model, "y")
        self.assertEqual(c.temperature, 0.9)


class AuthHeadersTests(unittest.TestCase):
    def test_legacy_when_no_secret(self):
        c = mod.LLMClient(api_key="k")
        with patch.object(mod.settings, "WIRO_API_SECRET", ""):
            h = c._auth_headers()
        self.assertEqual(h, {"x-api-key": "k"})

    def test_hmac_when_secret_set(self):
        c = mod.LLMClient(api_key="k")
        with patch.object(mod.settings, "WIRO_API_SECRET", "s"), \
             patch("app.core.llm_client.time.time", return_value=42):
            h = c._auth_headers()
        self.assertEqual(h["x-api-key"], "k")
        self.assertEqual(h["x-nonce"], "42")
        expected = hmac.new(b"k", b"s42", hashlib.sha256).hexdigest()
        self.assertEqual(h["x-signature"], expected)

    def test_raises_when_no_api_key_at_all(self):
        c = mod.LLMClient(api_key=None)
        with patch.object(mod.settings, "WIRO_API_KEY", ""):
            with self.assertRaises(ValueError) as cm:
                c._auth_headers()
        self.assertIn("Missing WIRO_API_KEY", str(cm.exception))


class BuildPromptTests(unittest.TestCase):
    def test_plain_text_format(self):
        c = mod.LLMClient(api_key="k")
        p = c._build_prompt("SYS", "USR", "text")
        self.assertIn("SYS", p)
        self.assertIn("USR", p)
        self.assertNotIn("JSON", p)

    def test_json_format_appends_json_hint(self):
        c = mod.LLMClient(api_key="k")
        p = c._build_prompt("SYS", "USR", "json")
        self.assertIn("valid JSON object", p)


# ---------------------------------------------------------------------------
# Static helpers
# ---------------------------------------------------------------------------


class StripMarkdownTests(unittest.TestCase):
    def test_strips_triple_backtick_fence(self):
        fenced = "```json\n{\"a\":1}\n```"
        self.assertEqual(
            mod.LLMClient._strip_markdown_code_fence(fenced),
            '{"a":1}',
        )

    def test_leaves_plain_json_untouched(self):
        self.assertEqual(
            mod.LLMClient._strip_markdown_code_fence('{"a":1}'),
            '{"a":1}',
        )

    def test_unmatched_fence_left_untouched(self):
        s = "```json\nno closing"
        self.assertEqual(mod.LLMClient._strip_markdown_code_fence(s), s)


class ExtractJsonBlockTests(unittest.TestCase):
    def test_extracts_object_from_text_prefix(self):
        self.assertEqual(
            mod.LLMClient._extract_json_block('garbage {"a":1} trailing'),
            '{"a":1}',
        )

    def test_extracts_array_when_no_object(self):
        self.assertEqual(
            mod.LLMClient._extract_json_block('pre [1,2,3] post'),
            '[1,2,3]',
        )

    def test_empty_string_returns_none(self):
        self.assertIsNone(mod.LLMClient._extract_json_block("   "))

    def test_no_json_returns_none(self):
        self.assertIsNone(mod.LLMClient._extract_json_block("just text"))


# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------


class RunTaskTests(unittest.TestCase):
    def test_returns_token_on_success(self):
        c = _fresh_client()
        c.client.post.return_value = _async_resp({
            "result": True,
            "socketaccesstoken": "tt",
        })
        with patch.object(mod.settings, "WIRO_REASONING", "off"), \
             patch.object(mod.settings, "WIRO_WEB_SEARCH", False), \
             patch.object(mod.settings, "WIRO_VERBOSITY", "low"), \
             patch.object(mod.settings, "WIRO_API_SECRET", ""):
            token = asyncio.run(c._run_task("p"))
        self.assertEqual(token, "tt")

    def test_raises_when_result_false(self):
        c = _fresh_client()
        c.client.post.return_value = _async_resp({
            "result": False, "errors": "nope",
        })
        with patch.object(mod.settings, "WIRO_REASONING", "off"), \
             patch.object(mod.settings, "WIRO_WEB_SEARCH", False), \
             patch.object(mod.settings, "WIRO_VERBOSITY", "low"), \
             patch.object(mod.settings, "WIRO_API_SECRET", ""):
            with self.assertRaises(RuntimeError) as cm:
                asyncio.run(c._run_task("p"))
        self.assertIn("Wiro run failed", str(cm.exception))

    def test_raises_when_token_missing(self):
        c = _fresh_client()
        c.client.post.return_value = _async_resp({"result": True})
        with patch.object(mod.settings, "WIRO_REASONING", "off"), \
             patch.object(mod.settings, "WIRO_WEB_SEARCH", False), \
             patch.object(mod.settings, "WIRO_VERBOSITY", "low"), \
             patch.object(mod.settings, "WIRO_API_SECRET", ""):
            with self.assertRaises(RuntimeError) as cm:
                asyncio.run(c._run_task("p"))
        self.assertIn("missing task token", str(cm.exception))


class GetTaskDetailTests(unittest.TestCase):
    def test_returns_first_task(self):
        c = _fresh_client()
        c.client.post.return_value = _async_resp({
            "result": True,
            "tasklist": [{"status": "running"}],
        })
        with patch.object(mod.settings, "WIRO_API_SECRET", ""):
            task = asyncio.run(c._get_task_detail("tt"))
        self.assertEqual(task, {"status": "running"})

    def test_raises_when_result_false(self):
        c = _fresh_client()
        c.client.post.return_value = _async_resp({
            "result": False, "errors": "down",
        })
        with patch.object(mod.settings, "WIRO_API_SECRET", ""):
            with self.assertRaises(RuntimeError) as cm:
                asyncio.run(c._get_task_detail("tt"))
        self.assertIn("task detail failed", str(cm.exception))

    def test_raises_on_empty_tasklist(self):
        c = _fresh_client()
        c.client.post.return_value = _async_resp({
            "result": True, "tasklist": [],
        })
        with patch.object(mod.settings, "WIRO_API_SECRET", ""):
            with self.assertRaises(RuntimeError) as cm:
                asyncio.run(c._get_task_detail("tt"))
        self.assertIn("missing tasklist", str(cm.exception))


class WaitForTaskCompletionTests(unittest.TestCase):
    def test_returns_task_on_terminal_success(self):
        c = _fresh_client()
        with patch.object(c, "_get_task_detail", AsyncMock(return_value={
            "status": "task_end", "debugoutput": "done",
        })), patch.object(mod.settings, "WIRO_POLL_TIMEOUT_SECONDS", 2), \
             patch.object(mod.settings, "WIRO_POLL_INTERVAL_SECONDS", 0.01):
            task = asyncio.run(c._wait_for_task_completion("tt"))
        self.assertEqual(task["status"], "task_end")

    def test_raises_on_terminal_error(self):
        c = _fresh_client()
        with patch.object(c, "_get_task_detail", AsyncMock(return_value={
            "status": "task_error", "debugerror": "boom",
        })), patch.object(mod.settings, "WIRO_POLL_TIMEOUT_SECONDS", 2), \
             patch.object(mod.settings, "WIRO_POLL_INTERVAL_SECONDS", 0.01):
            with self.assertRaises(RuntimeError) as cm:
                asyncio.run(c._wait_for_task_completion("tt"))
        self.assertIn("task failed with status=task_error", str(cm.exception))

    def test_raises_timeout_after_deadline(self):
        c = _fresh_client()
        with patch.object(c, "_get_task_detail", AsyncMock(return_value={
            "status": "running",
        })), patch.object(mod.settings, "WIRO_POLL_TIMEOUT_SECONDS", 0), \
             patch.object(mod.settings, "WIRO_POLL_INTERVAL_SECONDS", 0.001):
            with self.assertRaises(TimeoutError) as cm:
                asyncio.run(c._wait_for_task_completion("tt"))
        self.assertIn("timed out", str(cm.exception))

    def test_polls_until_success(self):
        c = _fresh_client()
        calls = {"n": 0}

        async def detail(_tt):
            calls["n"] += 1
            if calls["n"] < 3:
                return {"status": "running"}
            return {"status": "task_postprocess_end", "debugoutput": "x"}

        with patch.object(c, "_get_task_detail", detail), \
             patch.object(mod.settings, "WIRO_POLL_TIMEOUT_SECONDS", 5), \
             patch.object(mod.settings, "WIRO_POLL_INTERVAL_SECONDS", 0.001):
            task = asyncio.run(c._wait_for_task_completion("tt"))
        self.assertEqual(task["debugoutput"], "x")
        self.assertEqual(calls["n"], 3)


class ExtractTextFromOutputUrlsTests(unittest.TestCase):
    def test_returns_text_for_text_contenttype(self):
        c = _fresh_client()
        c.client.get.return_value = _async_resp({}, text="remote\n")
        task = {"outputs": [{"contenttype": "text/plain", "url": "https://x"}]}
        out = asyncio.run(c._extract_text_from_output_urls(task))
        self.assertEqual(out, "remote")

    def test_returns_text_for_json_contenttype(self):
        c = _fresh_client()
        c.client.get.return_value = _async_resp({}, text='{"a":1}')
        task = {"outputs": [{"contenttype": "application/json", "url": "https://x"}]}
        out = asyncio.run(c._extract_text_from_output_urls(task))
        self.assertEqual(out, '{"a":1}')

    def test_skips_non_text_contenttype(self):
        c = _fresh_client()
        task = {"outputs": [{"contenttype": "image/png", "url": "https://x"}]}
        out = asyncio.run(c._extract_text_from_output_urls(task))
        self.assertIsNone(out)

    def test_skips_entries_without_url(self):
        c = _fresh_client()
        task = {"outputs": [{"contenttype": "text/plain"}]}
        out = asyncio.run(c._extract_text_from_output_urls(task))
        self.assertIsNone(out)

    def test_fetch_failure_falls_through(self):
        c = _fresh_client()
        c.client.get.side_effect = httpx.ConnectError("x")
        task = {"outputs": [{"contenttype": "text/plain", "url": "https://x"}]}
        out = asyncio.run(c._extract_text_from_output_urls(task))
        self.assertIsNone(out)


class ExtractTaskTextTests(unittest.TestCase):
    def test_returns_debugoutput_first(self):
        c = _fresh_client()
        out = asyncio.run(c._extract_task_text({"debugoutput": "  hi  "}))
        self.assertEqual(out, "hi")

    def test_falls_back_to_outputs_inline_text(self):
        c = _fresh_client()
        task = {"outputs": [{"text": "from-output"}]}
        out = asyncio.run(c._extract_task_text(task))
        self.assertEqual(out, "from-output")

    def test_falls_back_to_urls_when_no_inline(self):
        c = _fresh_client()
        c.client.get.return_value = _async_resp({}, text="remote")
        task = {"outputs": [{"contenttype": "text/plain", "url": "u"}]}
        out = asyncio.run(c._extract_task_text(task))
        self.assertEqual(out, "remote")

    def test_raises_when_no_text_anywhere(self):
        c = _fresh_client()
        with self.assertRaises(RuntimeError) as cm:
            asyncio.run(c._extract_task_text({"outputs": []}))
        self.assertIn("no textual output", str(cm.exception))


# ---------------------------------------------------------------------------
# chat / chat_json
# ---------------------------------------------------------------------------


class ChatTests(unittest.TestCase):
    def test_happy_path_returns_stripped_content(self):
        c = _fresh_client()
        with patch.object(c, "_run_task", AsyncMock(return_value="tok")), \
             patch.object(c, "_wait_for_task_completion",
                          AsyncMock(return_value={"debugoutput": "```json\n{\"a\":1}\n```"})):
            out = asyncio.run(c.chat("sys", "user"))
        self.assertEqual(out, '{"a":1}')

    def test_empty_content_raises(self):
        c = _fresh_client()
        with patch.object(c, "_run_task", AsyncMock(return_value="tok")), \
             patch.object(c, "_wait_for_task_completion",
                          AsyncMock(return_value={"debugoutput": "   "})):
            # Empty after strip → "" → raises in chat, then tenacity retries.
            # tenacity retries 3x then raises RetryError wrapping ValueError.
            with patch("app.core.llm_client.logger.warning"):
                with self.assertRaises(Exception) as cm:
                    asyncio.run(c.chat("sys", "user"))
        # The RetryError chains to ValueError, but from user perspective we just
        # want "something failed".
        self.assertIsNotNone(cm.exception)


class ChatJsonTests(unittest.TestCase):
    def test_returns_parsed_dict(self):
        c = _fresh_client()
        with patch.object(c, "chat", AsyncMock(return_value='{"key":"val"}')):
            out = asyncio.run(c.chat_json("s", "u"))
        self.assertEqual(out, {"key": "val"})

    def test_extracts_json_from_surrounding_text(self):
        c = _fresh_client()
        with patch.object(c, "chat", AsyncMock(return_value='prefix {"k":1} suffix')):
            out = asyncio.run(c.chat_json("s", "u"))
        self.assertEqual(out, {"k": 1})

    def test_uses_ast_literal_eval_fallback_for_py_dict(self):
        c = _fresh_client()
        # json.loads fails on single-quoted "dict", ast.literal_eval succeeds.
        with patch.object(c, "chat", AsyncMock(return_value="{'k': 1}")):
            out = asyncio.run(c.chat_json("s", "u"))
        self.assertEqual(out, {"k": 1})

    def test_invalid_json_raises_value_error(self):
        c = _fresh_client()
        with patch.object(c, "chat", AsyncMock(return_value="not json at all")):
            with self.assertRaises(ValueError):
                asyncio.run(c.chat_json("s", "u"))

    def test_non_dict_json_array_raises_value_error(self):
        c = _fresh_client()
        # Returns valid JSON but an array, not object.  chat_json must reject.
        with patch.object(c, "chat", AsyncMock(return_value="[1,2,3]")):
            with self.assertRaises(ValueError):
                asyncio.run(c.chat_json("s", "u"))


if __name__ == "__main__":
    unittest.main()
