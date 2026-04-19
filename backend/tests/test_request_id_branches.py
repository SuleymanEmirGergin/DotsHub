"""Branch coverage for app.core.request_id.

Tiny module but threaded through every request + log line — if the
context-var round-trip silently breaks, downstream logs lose their
request_id correlation and debugging gets very confusing.
"""
from __future__ import annotations

import uuid

from app.core.request_id import (
    generate_request_id,
    get_request_id,
    set_request_id,
)


def test_generate_request_id_returns_a_uuid_string():
    value = generate_request_id()
    # Must be parseable as a UUID — that's the whole job.
    uuid.UUID(value)


def test_generate_request_id_is_unique_per_call():
    a = generate_request_id()
    b = generate_request_id()
    assert a != b


def test_default_context_value_is_none():
    # Isolate via a fresh set → None round-trip; can't fully reset the
    # global ContextVar, but we can at least verify None is carried.
    set_request_id(None)
    assert get_request_id() is None


def test_set_and_get_round_trip():
    token = "req-abc-123"
    set_request_id(token)
    assert get_request_id() == token

    # Reset so later tests see a clean slate.
    set_request_id(None)
    assert get_request_id() is None


def test_set_request_id_accepts_none_explicitly():
    set_request_id("something")
    assert get_request_id() == "something"
    set_request_id(None)
    assert get_request_id() is None
