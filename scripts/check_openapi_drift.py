#!/usr/bin/env python3
"""OpenAPI ↔ FastAPI route drift gate.

Compares the path set in ``docs/openapi_orchestrator.yaml`` (the
public API contract) against the path set FastAPI actually exposes
via ``app.main:app``. Fails (exit 1) when either side has a path the
other doesn't.

Why this exists
    Adding a new public endpoint without documenting it (or renaming
    a documented one without updating the spec) silently breaks every
    third-party integration relying on the contract — and we've shipped
    such drift before. The CI gate makes the spec a hard contract: code
    and yaml move together or the PR is blocked.

What's NOT compared
    - HTTP method, request/response shape, parameters — those are
      separate concerns and a path-only diff is what catches the most
      common mistake (adding a route, forgetting the spec).
    - Internal paths (admin, health probes, metrics) listed in
      ``INTERNAL_PATH_PREFIXES`` below — these are not part of the
      public contract and don't belong in the spec.

Usage
    python scripts/check_openapi_drift.py
    Exit 0 → in sync. Exit 1 → drift, with a per-side report on stdout.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Iterable, Set

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = REPO_ROOT / "docs" / "openapi_orchestrator.yaml"

# Paths that are intentionally NOT in the public contract. Admin and
# internal probes are out-of-scope for partner integrations, so they
# don't need OpenAPI entries. Anything matching one of these prefixes
# is silently dropped from the FastAPI side of the diff.
INTERNAL_PATH_PREFIXES = (
    "/v1/admin/",
    "/v1/session",  # legacy multi-step endpoints; superseded by /v1/triage/turn
    "/health",
    "/metrics",
    "/openapi.json",
    "/docs",
    "/redoc",
)
# Note: /v1/me/* (KVKK silme endpoints) are public — they're documented
# in openapi_orchestrator.yaml so partner integrations and the mobile
# client use them directly. Keeping them OUT of INTERNAL_PATH_PREFIXES
# means the drift gate verifies parity between spec and code.
# Exact-match internal paths. The root "/" is handled here, not as a
# prefix, because a startswith("/") check would swallow every API path.
INTERNAL_EXACT_PATHS = frozenset({"/"})


def _load_spec_paths(spec_path: Path) -> Set[str]:
    """Extract the top-level keys of the ``paths:`` block.

    We avoid pulling in PyYAML to keep this script dependency-free —
    the OpenAPI file's structure is regular enough to parse with a
    regex anchored at column zero. Path keys all start with ``  /v1/``
    (two-space indent + slash) directly under the ``paths:`` block.
    """
    text = spec_path.read_text(encoding="utf-8")
    paths: Set[str] = set()
    in_paths_block = False
    for line in text.splitlines():
        if re.match(r"^paths:\s*$", line):
            in_paths_block = True
            continue
        if not in_paths_block:
            continue
        if re.match(r"^\S", line):  # next top-level key — paths block ended
            in_paths_block = False
            continue
        m = re.match(r"^  (/\S+):\s*$", line)
        if m:
            paths.add(m.group(1))
    return paths


def _normalise_fastapi_path(path: str) -> str:
    """FastAPI and OpenAPI both use ``{name}`` placeholders, so they
    line up directly. This indirection exists for the day they don't."""
    return path


def _is_internal(path: str) -> bool:
    if path in INTERNAL_EXACT_PATHS:
        return True
    return any(path.startswith(p) for p in INTERNAL_PATH_PREFIXES)


def _load_app_paths() -> Set[str]:
    """Import ``app.main`` and walk its router for path strings.

    We only count routes that respond to GET/POST/PUT/DELETE/PATCH —
    HEAD/OPTIONS-only routes (mounts, static) aren't part of the API
    surface customers see.
    """
    # Keep the import local so a yaml-only failure doesn't import the
    # whole app and surface unrelated import errors.
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    os.environ.setdefault("APP_ENV", "test")
    from app.main import app  # type: ignore

    public_methods = {"GET", "POST", "PUT", "DELETE", "PATCH"}
    paths: Set[str] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or set()
        if not path or not (methods & public_methods):
            continue
        if _is_internal(path):
            continue
        paths.add(_normalise_fastapi_path(path))
    return paths


def _diff(a: Iterable[str], b: Iterable[str]) -> list[str]:
    return sorted(set(a) - set(b))


def main() -> int:
    if not SPEC_PATH.exists():
        print(f"[openapi-drift] spec missing: {SPEC_PATH}", file=sys.stderr)
        return 1

    spec_paths = _load_spec_paths(SPEC_PATH)
    if not spec_paths:
        print(
            "[openapi-drift] spec parse returned 0 paths — file format "
            "changed? Bailing out so we don't false-pass.",
            file=sys.stderr,
        )
        return 1

    app_paths = _load_app_paths()

    # Apply the same internal filter to the spec side so a path that
    # appears in both can be moved to the internal allowlist without
    # tripping a 1-sided diff.
    spec_public = {p for p in spec_paths if not _is_internal(p)}

    in_spec_not_in_code = _diff(spec_public, app_paths)
    in_code_not_in_spec = _diff(app_paths, spec_public)

    if not in_spec_not_in_code and not in_code_not_in_spec:
        total = len(spec_public)
        print(
            f"[openapi-drift] ok — {total} public paths in sync "
            f"between docs/openapi_orchestrator.yaml and app.main"
        )
        return 0

    print("[openapi-drift] drift detected:", file=sys.stderr)
    if in_spec_not_in_code:
        print(
            "  in spec but missing from FastAPI app:", file=sys.stderr
        )
        for p in in_spec_not_in_code:
            print(f"    - {p}", file=sys.stderr)
    if in_code_not_in_spec:
        print(
            "  in FastAPI app but missing from spec "
            "(add to openapi_orchestrator.yaml or to "
            "INTERNAL_PATH_PREFIXES if intentionally hidden):",
            file=sys.stderr,
        )
        for p in in_code_not_in_spec:
            print(f"    - {p}", file=sys.stderr)
    print(
        "  fix: update whichever side is behind, then rerun this check.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
