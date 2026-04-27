"""Unit tests for scripts/check_openapi_drift.py.

The script is the OpenAPI ↔ FastAPI route contract gate. These tests
exercise its parsing helpers and end-to-end behavior:
    * spec parser — extracts top-level path keys
    * internal-path filter — matches prefixes + exact-path "/"
    * full run — script returns 0 when in sync against the live app

We don't mock FastAPI; the script's whole point is comparing the real
route registry to the real spec, so a mocked app would give the gate
zero teeth.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_openapi_drift.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location(
        "check_openapi_drift", SCRIPT_PATH
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@pytest.fixture(scope="module")
def drift_script():
    return _load_script_module()


# ─── Spec parser ─────────────────────────────────────────────────────


def test_spec_parser_extracts_known_paths(drift_script, tmp_path):
    spec = tmp_path / "tiny.yaml"
    spec.write_text(
        "openapi: 3.1.0\n"
        "info:\n"
        "  title: x\n"
        "  version: 0\n"
        "paths:\n"
        "  /v1/triage/turn:\n"
        "    post:\n"
        "      summary: x\n"
        "  /v1/triage/feedback:\n"
        "    post:\n"
        "      summary: y\n"
        "components:\n"
        "  schemas: {}\n",
        encoding="utf-8",
    )
    out = drift_script._load_spec_paths(spec)
    assert out == {"/v1/triage/turn", "/v1/triage/feedback"}


def test_spec_parser_returns_empty_on_no_paths_block(drift_script, tmp_path):
    spec = tmp_path / "no_paths.yaml"
    spec.write_text("openapi: 3.1.0\ninfo:\n  title: x\n", encoding="utf-8")
    assert drift_script._load_spec_paths(spec) == set()


# ─── Internal-path filter ────────────────────────────────────────────


def test_is_internal_matches_admin_prefix(drift_script):
    assert drift_script._is_internal("/v1/admin/sessions")
    assert drift_script._is_internal("/v1/admin/feedback/123")


def test_is_internal_matches_health_metrics_docs(drift_script):
    for p in ("/health", "/metrics", "/docs", "/redoc", "/openapi.json"):
        assert drift_script._is_internal(p), p


def test_is_internal_matches_root_exact_path(drift_script):
    # Root must be exact-match — startswith("/") would swallow every
    # API path. Regression test for the original bug.
    assert drift_script._is_internal("/")


def test_is_internal_does_not_match_public_v1_paths(drift_script):
    for p in (
        "/v1/triage/turn",
        "/v1/triage/stream",
        "/v1/triage/feedback",
        "/v1/facilities",
        "/v1/config/features",
        "/v1/config/capabilities",
    ):
        assert not drift_script._is_internal(p), p


def test_is_internal_matches_legacy_session_prefix(drift_script):
    assert drift_script._is_internal("/v1/session/start")
    assert drift_script._is_internal("/v1/session/abc/message")


# ─── End-to-end main() against the live app ─────────────────────────


def test_main_returns_zero_when_in_sync(drift_script, capsys):
    """The current state of the repo must be in sync — if this fails,
    either the spec is missing a route or a route is missing from
    INTERNAL_PATH_PREFIXES. Either way it's a real CI signal."""
    rc = drift_script.main()
    captured = capsys.readouterr()
    assert rc == 0, f"drift detected:\nstdout={captured.out}\nstderr={captured.err}"
    assert "in sync" in captured.out


def test_main_returns_one_when_spec_missing(drift_script, tmp_path, monkeypatch):
    """A missing spec file must fail the gate — silent-pass would mask
    a real configuration error."""
    monkeypatch.setattr(drift_script, "SPEC_PATH", tmp_path / "missing.yaml")
    rc = drift_script.main()
    assert rc == 1
