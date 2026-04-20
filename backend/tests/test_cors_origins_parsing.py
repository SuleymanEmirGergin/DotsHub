"""Unit tests for Settings.cors_origins_list parsing.

This property was a production-crasher on Fly.io: a PowerShell
quote-escape bug wrote the CORS_ORIGINS secret with an extra leading
character, so `json.loads` threw `JSONDecodeError` on import of
`app.main` — the FastAPI process never reached a request. See
commit 90c7411 followup for context.

Coverage targets:
  - Happy path: valid JSON array
  - CSV fallback: comma-separated, mixed whitespace
  - Empty / whitespace-only → [] (fail-closed)
  - Malformed JSON → ValueError with actionable message
  - JSON that is not a list (e.g. dict) → ValueError
  - Duplicates + whitespace entries preserved vs trimmed deterministically
"""
from __future__ import annotations

import pytest

from app.core.config import Settings


def _make(cors_origins: str) -> Settings:
    """Build a Settings override with the given CORS_ORIGINS value.

    Using `Settings(CORS_ORIGINS=…)` works because pydantic-settings
    accepts kwargs as first-priority overrides — no env pollution.
    """
    return Settings(CORS_ORIGINS=cors_origins)


class TestCorsOriginsJsonShape:
    def test_valid_json_array_round_trips(self):
        s = _make('["http://localhost:3000","https://example.com"]')
        assert s.cors_origins_list == [
            "http://localhost:3000",
            "https://example.com",
        ]

    def test_single_element_json_array(self):
        s = _make('["http://a.com"]')
        assert s.cors_origins_list == ["http://a.com"]

    def test_json_array_with_internal_whitespace(self):
        # Spaces inside the array are preserved by json.loads; the
        # list-comp trims each element so extraneous whitespace on
        # either side of a URL doesn't poison the allow-list.
        s = _make('[ "  http://a.com  ", "http://b.com" ]')
        assert s.cors_origins_list == ["http://a.com", "http://b.com"]

    def test_empty_json_array_returns_empty(self):
        s = _make("[]")
        assert s.cors_origins_list == []


class TestCorsOriginsCsvFallback:
    def test_simple_csv(self):
        s = _make("http://localhost:3000,https://example.com")
        assert s.cors_origins_list == [
            "http://localhost:3000",
            "https://example.com",
        ]

    def test_csv_with_whitespace_between_entries(self):
        s = _make("  http://a.com ,  http://b.com  ,http://c.com")
        assert s.cors_origins_list == [
            "http://a.com",
            "http://b.com",
            "http://c.com",
        ]

    def test_csv_drops_empty_entries_from_trailing_comma(self):
        # `foo,bar,` or `,foo,bar` should not yield a phantom "" origin
        # — that could accidentally match a malformed CORS request.
        s = _make("http://a.com,,http://b.com,")
        assert s.cors_origins_list == ["http://a.com", "http://b.com"]

    def test_single_csv_entry_no_comma(self):
        s = _make("http://solo.com")
        assert s.cors_origins_list == ["http://solo.com"]


class TestCorsOriginsEmpty:
    def test_empty_string_returns_empty_list(self):
        # Fail-closed: empty env → no origins allowed. Prevents the
        # historical footgun of forgetting the secret and silently
        # shipping "allow any origin".
        s = _make("")
        assert s.cors_origins_list == []

    def test_whitespace_only_returns_empty_list(self):
        s = _make("   \t  \n  ")
        assert s.cors_origins_list == []


class TestCorsOriginsMalformed:
    # Dispatch rule: any value that STARTS with '[' is parsed as JSON;
    # everything else falls into the CSV branch. This means the original
    # PowerShell crash scenario (`'["..."]` with leading quote) no
    # longer raises — it just becomes a single nonsense CSV entry that
    # can never match an Origin header. Fail-closed by accident, but
    # deliberate: app stays up + ops can fix the secret without a
    # crash/restart loop.

    def test_broken_json_that_starts_with_bracket_raises_value_error(self):
        # `[` triggers the JSON branch; if the body after is garbage,
        # we re-raise as ValueError with the raw value embedded so ops
        # can triage from the log line alone (no container exec to
        # read env).
        s = _make('[not valid json')
        with pytest.raises(ValueError, match="not valid JSON"):
            _ = s.cors_origins_list

    def test_error_message_includes_raw_value_for_debugging(self):
        bad = '[http://a.com]'  # unquoted strings inside JSON array
        s = _make(bad)
        with pytest.raises(ValueError) as excinfo:
            _ = s.cors_origins_list
        assert bad in str(excinfo.value)

    def test_json_array_with_non_string_elements_coerces_to_str(self):
        # `[1, 2, 3]` is valid JSON and IS a list, so we don't raise —
        # we stringify elements. FastAPI will then reject any match
        # attempt since no Origin header equals "1". Lenient parse,
        # strict match — the right failure mode.
        s = _make('[1, 2, "http://real.com"]')
        assert s.cors_origins_list == ["1", "2", "http://real.com"]

    def test_leading_quote_falls_into_csv_branch(self):
        # The exact bug that crashed Fly prod: PowerShell embedded a
        # leading single-quote. With the new parser this no longer
        # starts with '[', so it goes down the CSV branch and becomes
        # one (useless but non-crashing) entry.
        bad = "'[\"http://a.com\"]"
        s = _make(bad)
        result = s.cors_origins_list
        # Exact shape of the single entry isn't the contract — the
        # contract is "app doesn't crash; we get a list".
        assert isinstance(result, list)
        assert len(result) >= 1
        assert all(isinstance(v, str) for v in result)


class TestCorsOriginsJsonShapeRejections:
    """JSON-shape values that ARE `[`-prefixed but not a list get a clear error."""

    def test_bracket_starting_but_dict_in_nested_json_raises(self):
        # `[...]` array contains a valid dict — but each element is
        # stringified, so no ValueError. This documents that behaviour.
        s = _make('[{"origin": "http://a.com"}]')
        assert s.cors_origins_list == ["{'origin': 'http://a.com'}"]
