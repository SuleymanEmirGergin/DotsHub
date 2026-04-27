"""unittest-style coverage for app.version_gating.

Why this file exists:
    The richer pytest-style suite `test_version_gating.py` is only
    discovered by pytest — `unittest discover` silently skips its
    function-level tests. The hot-path coverage gate
    (`scripts/check_hotpath_coverage.py`) runs the full test corpus
    under unittest, so any code path exercised only by pytest tests
    does not count towards that gate. Without this file, the
    Prometheus observability helpers
    (`_inc_triage_envelope`, `_inc_gate_counters`) and several
    defensive branches in `filter_envelope` / the middleware land as
    uncovered under unittest and trip the 90% floor for
    `app/version_gating.py`.

    Keep this file cheap: it's not trying to re-test the happy
    middleware flow — that lives in the pytest file. It exists purely
    so every executable line of `version_gating.py` is reachable when
    the coverage gate runs `unittest discover`.
"""
from __future__ import annotations

import json
import unittest

from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.testclient import TestClient

from app.version_gating import (
    CAP_CURATED_META,
    CAP_EMERGENCY_SPECIALTY,
    CapabilityGateMiddleware,
    KNOWN_CAPABILITIES,
    _inc_gate_counters,
    _inc_triage_envelope,
    _strip_top_condition,
    filter_envelope,
    parse_capabilities,
)


class IncTriageEnvelopeTests(unittest.TestCase):
    """`_inc_triage_envelope` must no-op on unknown envelope types and
    not raise on known ones — the Prometheus import is lazy and
    silent."""

    def test_unknown_envelope_type_is_no_op(self):
        # No raise, no side effect; also hits the early-return branch
        # that bounds counter cardinality.
        _inc_triage_envelope(None)
        _inc_triage_envelope("UNKNOWN")
        _inc_triage_envelope("")

    def test_valid_envelope_type_does_not_raise(self):
        # Importing the counter + calling .labels().inc() is a
        # side-effect we don't assert on here (no registry snapshot);
        # the contract is that it stays silent and doesn't raise when
        # prometheus_client is importable.
        for etype in ("RESULT", "EMERGENCY", "QUESTION", "ERROR"):
            _inc_triage_envelope(etype)


class IncGateCountersTests(unittest.TestCase):
    """`_inc_gate_counters` has three early-return branches before
    touching Prometheus: bad envelope type, non-positive bytes_saved,
    and (in principle) ImportError. The first two are testable."""

    def test_unknown_envelope_type_is_no_op(self):
        _inc_gate_counters(None, frozenset({CAP_CURATED_META}), 100)
        _inc_gate_counters("SOMETHING_ELSE", frozenset({CAP_CURATED_META}), 100)

    def test_zero_or_negative_bytes_saved_is_no_op(self):
        # The strip path can produce 0 bytes saved when the client
        # lacks a cap but the payload didn't carry that field; we
        # must not inflate the gate metric with synthetic strips.
        _inc_gate_counters("RESULT", frozenset({CAP_CURATED_META}), 0)
        _inc_gate_counters("RESULT", frozenset({CAP_CURATED_META}), -5)

    def test_real_strip_increments_without_raising(self):
        # Every terminal path of the function runs at least once.
        _inc_gate_counters(
            "RESULT", frozenset({CAP_CURATED_META}), 1
        )
        _inc_gate_counters(
            "EMERGENCY",
            frozenset({CAP_CURATED_META, CAP_EMERGENCY_SPECIALTY}),
            42,
        )


class FilterEnvelopeEarlyReturnsTests(unittest.TestCase):
    """`filter_envelope` has three early-return paths that pass the
    input through unchanged. Exercise each one."""

    def test_non_mapping_input_returned_unchanged(self):
        # `filter_envelope` is called on an arbitrary JSON shape; lists,
        # strings, numbers should all short-circuit.
        self.assertEqual(filter_envelope([1, 2, 3], frozenset()), [1, 2, 3])
        self.assertEqual(filter_envelope("plain", frozenset()), "plain")
        self.assertEqual(filter_envelope(42, frozenset()), 42)
        self.assertIsNone(filter_envelope(None, frozenset()))

    def test_mapping_without_envelope_type_passes_through(self):
        # A dict that is NOT a triage envelope (e.g. /v1/config/features)
        # must not be mutated.
        data = {"llm_nlu_enabled": True, "unrelated": [1, 2]}
        self.assertEqual(filter_envelope(data, frozenset()), data)

    def test_mapping_with_non_mapping_payload_passes_through(self):
        data = {"type": "RESULT", "payload": "oops not a dict"}
        self.assertEqual(filter_envelope(data, frozenset()), data)


class StripTopConditionTests(unittest.TestCase):
    """`_strip_top_condition` is a tiny helper; cover both branches."""

    def test_non_mapping_item_returned_as_is(self):
        # Upstream the list may contain a stray non-dict; we must not
        # crash the whole strip.
        self.assertEqual(_strip_top_condition("oops"), "oops")
        self.assertEqual(_strip_top_condition(None), None)
        self.assertEqual(_strip_top_condition(42), 42)

    def test_mapping_removes_curated_fields_only(self):
        item = {
            "disease_label": "Migren",
            "score_0_1": 0.8,
            "icd10": "G43",
            "disease_description": "...",
            "self_care_tr": "...",
        }
        stripped = _strip_top_condition(item)
        self.assertIn("disease_label", stripped)
        self.assertIn("score_0_1", stripped)
        self.assertNotIn("icd10", stripped)
        self.assertNotIn("disease_description", stripped)
        self.assertNotIn("self_care_tr", stripped)


class MiddlewareNonV1PathPassThroughTests(unittest.TestCase):
    """The middleware must bail out early on non-`/v1/*` paths —
    hitting `_should_filter` → False."""

    def test_root_path_bypasses_filter(self):
        app = FastAPI()
        app.add_middleware(CapabilityGateMiddleware)

        @app.get("/")
        def root():
            return JSONResponse({"type": "RESULT", "payload": {"whatever": True}})

        client = TestClient(app)
        resp = client.get("/")
        # Path did not start with /v1/ → envelope is returned as-is
        # even without any capability header.
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"type": "RESULT", "payload": {"whatever": True}})


class MiddlewareJsonDecodeFallbackTests(unittest.TestCase):
    """When a /v1/* route returns invalid JSON body but claims
    application/json content-type, the middleware must pass the raw
    bytes through rather than raise."""

    def test_invalid_json_body_is_passed_through(self):
        app = FastAPI()
        app.add_middleware(CapabilityGateMiddleware)

        @app.get("/v1/broken")
        def broken():
            # Claim JSON but emit garbage bytes.
            return PlainTextResponse(
                content="not { valid json }",
                media_type="application/json",
            )

        client = TestClient(app)
        # Client signals partial caps → middleware WILL try to filter.
        resp = client.get("/v1/broken", headers={"x-client-capabilities": ""})
        self.assertEqual(resp.status_code, 200)
        # Raw body preserved — that's the contract.
        self.assertEqual(resp.text, "not { valid json }")


class ParseCapabilitiesSmokeTests(unittest.TestCase):
    """Minimal parse_capabilities smoke — the pytest file has the
    richer param-sweep, but we want this covered under unittest too."""

    def test_empty_header_is_empty_set(self):
        self.assertEqual(parse_capabilities(None), frozenset())
        self.assertEqual(parse_capabilities(""), frozenset())

    def test_known_tokens_flow_through(self):
        out = parse_capabilities(
            ",".join(sorted(KNOWN_CAPABILITIES))
        )
        self.assertEqual(out, KNOWN_CAPABILITIES)

    def test_unknown_tokens_dropped(self):
        out = parse_capabilities("curated_meta, something_new_in_2030")
        self.assertEqual(out, frozenset({CAP_CURATED_META}))


if __name__ == "__main__":
    unittest.main()
