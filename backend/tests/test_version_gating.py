"""Branch coverage for app.version_gating.

Covers three layers:
  - `parse_capabilities` — header → frozenset[str]
  - `filter_envelope` — pure payload rewrite (every branch)
  - `CapabilityGateMiddleware` — end-to-end via FastAPI TestClient so
    integration wiring (JSON decode, path/content-type gate, header
    handling, passthrough) is exercised.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.testclient import TestClient

from app.version_gating import (
    CAP_CURATED_META,
    CAP_EMERGENCY_SPECIALTY,
    CURATED_TOP_CONDITION_FIELDS,
    CapabilityGateMiddleware,
    KNOWN_CAPABILITIES,
    filter_envelope,
    parse_capabilities,
)


# ─── parse_capabilities ──────────────────────────────────────────────

@pytest.mark.parametrize("raw", [None, "", "   ", ",,,"])
def test_parse_capabilities_empty_inputs_return_empty_set(raw):
    assert parse_capabilities(raw) == frozenset()


def test_parse_capabilities_known_tokens_pass_through():
    got = parse_capabilities("curated_meta,emergency_specialty")
    assert got == frozenset({CAP_CURATED_META, CAP_EMERGENCY_SPECIALTY})


def test_parse_capabilities_drops_unknown_tokens():
    got = parse_capabilities("curated_meta,future_feature,some_other")
    assert got == frozenset({CAP_CURATED_META})


def test_parse_capabilities_normalises_case_and_whitespace():
    got = parse_capabilities("  CURATED_META , Emergency_Specialty ")
    assert got == frozenset({CAP_CURATED_META, CAP_EMERGENCY_SPECIALTY})


# ─── filter_envelope ─────────────────────────────────────────────────

def _result_envelope(top: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "RESULT",
        "session_id": "s1",
        "payload": {
            "urgency": "ROUTINE",
            "recommended_specialty": {"id": "internal_gi", "name_tr": "Dahiliye"},
            "top_conditions": top,
        },
        "meta": {"disclaimer_tr": "x", "timestamp": "2026-04-18T10:00:00Z"},
    }


def _emergency_envelope() -> dict[str, Any]:
    return {
        "type": "EMERGENCY",
        "session_id": "s2",
        "payload": {
            "urgency": "EMERGENCY",
            "reason_tr": "Şiddetli göğüs ağrısı",
            "instructions_tr": ["112"],
            "recommended_specialty": {"id": "emergency", "name_tr": "Acil Tıp"},
        },
        "meta": {"disclaimer_tr": "x", "timestamp": "2026-04-18T10:00:00Z"},
    }


def test_filter_envelope_non_mapping_passes_through():
    assert filter_envelope(None, frozenset()) is None
    assert filter_envelope([1, 2, 3], frozenset()) == [1, 2, 3]
    assert filter_envelope("not-a-dict", frozenset()) == "not-a-dict"


def test_filter_envelope_unknown_type_passes_through():
    # Arbitrary JSON with a "type" field that isn't a triage envelope
    # is returned untouched.
    data = {"type": "CUSTOM", "payload": {"top_conditions": [{"icd10": "x"}]}}
    assert filter_envelope(data, frozenset()) is data


def test_filter_envelope_non_mapping_payload_passes_through():
    # Missing payload → skip rewrite.
    data = {"type": "RESULT", "payload": "not-a-dict"}
    assert filter_envelope(data, frozenset()) is data


def test_filter_envelope_strips_curated_fields_without_cap():
    env = _result_envelope([
        {
            "disease_label": "Peptik ülser",
            "score_0_1": 0.71,
            "icd10": "K27",
            "disease_description_tr": "desc",
            "self_care_tr": ["care"],
        }
    ])
    out = filter_envelope(env, frozenset())
    item = out["payload"]["top_conditions"][0]
    assert item == {"disease_label": "Peptik ülser", "score_0_1": 0.71}
    # original untouched (pure function)
    assert "icd10" in env["payload"]["top_conditions"][0]


def test_filter_envelope_keeps_curated_fields_with_cap():
    env = _result_envelope([
        {"disease_label": "X", "score_0_1": 0.5, "icd10": "K27"}
    ])
    out = filter_envelope(env, frozenset({CAP_CURATED_META}))
    assert out["payload"]["top_conditions"][0]["icd10"] == "K27"


def test_filter_envelope_non_list_top_conditions_unchanged():
    # Defensive: if some path emits an object instead of a list, don't crash.
    env = _result_envelope([])
    env["payload"]["top_conditions"] = {"oops": True}
    out = filter_envelope(env, frozenset())
    assert out["payload"]["top_conditions"] == {"oops": True}


def test_filter_envelope_non_mapping_item_in_top_conditions_unchanged():
    env = _result_envelope(["not-a-dict", {"disease_label": "y", "icd10": "z"}])
    out = filter_envelope(env, frozenset())
    assert out["payload"]["top_conditions"][0] == "not-a-dict"
    assert "icd10" not in out["payload"]["top_conditions"][1]


def test_filter_envelope_strips_emergency_specialty_without_cap():
    env = _emergency_envelope()
    out = filter_envelope(env, frozenset())
    assert "recommended_specialty" not in out["payload"]
    # routing/urgency/reason stay
    assert out["payload"]["urgency"] == "EMERGENCY"
    assert out["payload"]["reason_tr"].startswith("Şiddetli")


def test_filter_envelope_keeps_emergency_specialty_with_cap():
    env = _emergency_envelope()
    out = filter_envelope(env, frozenset({CAP_EMERGENCY_SPECIALTY}))
    assert out["payload"]["recommended_specialty"]["id"] == "emergency"


def test_filter_envelope_does_not_strip_specialty_on_result_path():
    # RESULT envelopes keep `recommended_specialty` regardless of caps —
    # routing info the old client needs.
    env = _result_envelope([])
    out = filter_envelope(env, frozenset())
    assert out["payload"]["recommended_specialty"]["name_tr"] == "Dahiliye"


def test_filter_envelope_returns_new_object_not_mutating_input():
    env = _result_envelope([{"disease_label": "x", "icd10": "k"}])
    original_payload_id = id(env["payload"])
    out = filter_envelope(env, frozenset())
    assert id(out["payload"]) != original_payload_id
    assert "icd10" in env["payload"]["top_conditions"][0]


def test_curated_fields_registry_covers_known_new_keys():
    # Smoke test so adding a new curated field without updating the
    # registry is loud.
    assert "icd10" in CURATED_TOP_CONDITION_FIELDS
    assert "disease_description" in CURATED_TOP_CONDITION_FIELDS
    assert "disclaimer_tr" in CURATED_TOP_CONDITION_FIELDS


def test_known_capabilities_registry_stable():
    assert {CAP_CURATED_META, CAP_EMERGENCY_SPECIALTY} == set(KNOWN_CAPABILITIES)


# ─── CapabilityGateMiddleware via FastAPI TestClient ─────────────────

def _build_app() -> FastAPI:
    """Isolated app that only mounts the middleware + a few test endpoints."""
    app = FastAPI()
    app.add_middleware(CapabilityGateMiddleware)

    @app.get("/v1/result")
    async def result_endpoint():
        return _result_envelope([
            {
                "disease_label": "X",
                "score_0_1": 0.6,
                "icd10": "I20",
                "disease_description_tr": "desc",
            }
        ])

    @app.get("/v1/emergency")
    async def emergency_endpoint():
        return _emergency_envelope()

    @app.get("/v1/plain")
    async def plain_endpoint():
        return PlainTextResponse("hello")

    @app.get("/v1/bad-json")
    async def bad_json_endpoint():
        return Response(
            content=b"\xff\xfe not-json",
            media_type="application/json",
        )

    @app.get("/other/result")
    async def other_prefix_endpoint():
        return JSONResponse(_result_envelope([
            {"disease_label": "X", "score_0_1": 0.5, "icd10": "K27"}
        ]))

    return app


# Lazy import so test doesn't error before version_gating is present.
from starlette.responses import Response  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(_build_app())


def test_middleware_strips_curated_fields_when_header_missing(client: TestClient):
    r = client.get("/v1/result")
    body = r.json()
    item = body["payload"]["top_conditions"][0]
    assert "icd10" not in item
    assert "disease_description_tr" not in item
    assert item["disease_label"] == "X"


def test_middleware_keeps_curated_fields_with_full_caps(client: TestClient):
    r = client.get(
        "/v1/result",
        headers={"X-Client-Capabilities": "curated_meta,emergency_specialty"},
    )
    body = r.json()
    assert body["payload"]["top_conditions"][0]["icd10"] == "I20"


def test_middleware_strips_specialty_in_emergency_without_cap(client: TestClient):
    r = client.get("/v1/emergency")
    body = r.json()
    assert "recommended_specialty" not in body["payload"]
    assert body["payload"]["urgency"] == "EMERGENCY"


def test_middleware_keeps_specialty_in_emergency_with_cap(client: TestClient):
    r = client.get(
        "/v1/emergency",
        headers={"X-Client-Capabilities": "emergency_specialty"},
    )
    assert r.json()["payload"]["recommended_specialty"]["id"] == "emergency"


def test_middleware_skips_non_json_responses(client: TestClient):
    r = client.get("/v1/plain")
    assert r.status_code == 200
    assert r.text == "hello"


def test_middleware_passthroughs_invalid_json(client: TestClient):
    # When content-type claims JSON but body isn't parseable, the
    # middleware must not explode — it hands the original bytes back.
    r = client.get("/v1/bad-json")
    assert r.status_code == 200
    # bytes preserved (not re-serialised)
    assert r.content == b"\xff\xfe not-json"


def test_middleware_ignores_paths_outside_v1_prefix(client: TestClient):
    r = client.get("/other/result")
    body = r.json()
    # Path is not gated, so curated fields are present without a cap.
    assert body["payload"]["top_conditions"][0]["icd10"] == "K27"


def test_middleware_fast_path_when_all_caps_present(client: TestClient):
    # Exercises the "caps >= KNOWN_CAPABILITIES" early return branch.
    r = client.get(
        "/v1/result",
        headers={"X-Client-Capabilities": "curated_meta,emergency_specialty"},
    )
    assert r.status_code == 200
    # behaviourally equivalent to the slow path
    assert r.json()["payload"]["top_conditions"][0]["icd10"] == "I20"


def test_middleware_recomputes_content_length_after_rewrite(client: TestClient):
    r = client.get("/v1/result")
    assert int(r.headers["content-length"]) == len(r.content)


def test_middleware_passthroughs_non_envelope_json(client: TestClient):
    # Custom app that returns JSON without the envelope shape — the
    # filter should no-op, and the middleware should pass it through
    # unchanged (no content-length drift either).
    app = FastAPI()
    app.add_middleware(CapabilityGateMiddleware)

    @app.get("/v1/unrelated")
    async def unrelated():
        return {"foo": "bar", "nested": {"ok": True}}

    c = TestClient(app)
    r = c.get("/v1/unrelated")
    assert r.json() == {"foo": "bar", "nested": {"ok": True}}
    assert int(r.headers["content-length"]) == len(r.content)
