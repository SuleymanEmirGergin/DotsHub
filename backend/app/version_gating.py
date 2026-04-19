"""Client-capability gating for triage envelopes.

The protocol is declarative: the client advertises what payload shapes it
can handle via `X-Client-Capabilities`, a comma-separated token list.
The server strips any field whose capability token the client did not
advertise. Missing/empty header → the minimal-baseline (nothing
gated-in), so the oldest imaginable client always sees a payload it can
parse.

Why capabilities, not semver: mobile/app.config.ts has shipped at
"1.0.0" across many feature iterations, so a version number is not a
reliable discriminator. Capabilities are explicit, additive, and let us
ship new backend fields without a coordinated client release.

The module is deliberately pure so tests don't need a FastAPI app: one
parser, one filter, and one middleware wrapper that calls them.
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterable, FrozenSet, Mapping, MutableMapping

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# ─── Capability registry ─────────────────────────────────────────────
#
# Add a new token here when a new response field needs gating. The
# filter function below consults these constants, so touching this
# registry is the only place that changes when a new field ships.

CAP_CURATED_META = "curated_meta"
CAP_EMERGENCY_SPECIALTY = "emergency_specialty"

KNOWN_CAPABILITIES: FrozenSet[str] = frozenset({
    CAP_CURATED_META,
    CAP_EMERGENCY_SPECIALTY,
})

# Fields within `Envelope.payload.top_conditions[*]` that are only safe
# to emit if the client advertises `curated_meta`. Everything else on a
# top-condition entry (disease_label, score_0_1) stays visible.
CURATED_TOP_CONDITION_FIELDS: FrozenSet[str] = frozenset({
    "disease_description",
    "disease_description_tr",
    "source_type",
    "disclaimer_tr",
    "icd10",
    "doktora_sorulacak_sorular_tr",
    "izlenecek_belirtiler_tr",
    "ne_zaman_tekrar_basvur_tr",
    "self_care_tr",
    "aciliyet_notu_tr",
})

# Paths that participate in gating; anything else passes through.
_GATED_PATH_PREFIXES: tuple[str, ...] = ("/v1/",)


# ─── Parser ──────────────────────────────────────────────────────────

def parse_capabilities(header_value: str | None) -> FrozenSet[str]:
    """Parse the `X-Client-Capabilities` header into a set of tokens.

    Unknown tokens are dropped (forward-compat — clients may advertise
    capabilities the current server doesn't recognise yet). Whitespace
    and empty commas are tolerated.
    """
    if not header_value:
        return frozenset()
    tokens = {tok.strip().lower() for tok in header_value.split(",")}
    tokens.discard("")
    return frozenset(tokens & KNOWN_CAPABILITIES)


# ─── Filter ──────────────────────────────────────────────────────────

def filter_envelope(data: Any, caps: FrozenSet[str]) -> Any:
    """Return `data` with capability-gated fields removed.

    Only the triage-envelope shape is inspected:
      - `Envelope.payload.top_conditions[*].<curated>` → gated by
        `CAP_CURATED_META`.
      - `Envelope.payload.recommended_specialty` (EMERGENCY only) →
        gated by `CAP_EMERGENCY_SPECIALTY`.

    Non-envelope JSON (e.g. `/v1/config/features`) is returned as-is.
    """
    if not isinstance(data, Mapping):
        return data

    envelope_type = data.get("type")
    payload = data.get("payload")
    if not isinstance(payload, Mapping) or envelope_type not in {"RESULT", "EMERGENCY", "QUESTION", "ERROR"}:
        # Not a triage envelope — skip entirely so arbitrary response
        # shapes aren't accidentally mangled.
        return data

    new_payload: MutableMapping[str, Any] = dict(payload)

    if CAP_CURATED_META not in caps:
        top = new_payload.get("top_conditions")
        if isinstance(top, list):
            new_payload["top_conditions"] = [
                _strip_top_condition(item) for item in top
            ]

    if CAP_EMERGENCY_SPECIALTY not in caps and envelope_type == "EMERGENCY":
        new_payload.pop("recommended_specialty", None)

    out = dict(data)
    out["payload"] = new_payload
    return out


def _strip_top_condition(item: Any) -> Any:
    if not isinstance(item, Mapping):
        return item
    return {k: v for k, v in item.items() if k not in CURATED_TOP_CONDITION_FIELDS}


# ─── Middleware ──────────────────────────────────────────────────────

class CapabilityGateMiddleware(BaseHTTPMiddleware):
    """Rewrites JSON responses on `/v1/*` to strip gated fields.

    Non-JSON responses, non-`/v1/` paths, and responses whose client
    already advertises every known capability are passed through
    without re-serialisation. Errors during JSON decode are logged to
    the response as-is rather than failing the request — the server
    stays correct even when the response isn't a triage envelope.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        if not self._should_filter(request, response):
            return response

        caps = parse_capabilities(request.headers.get("x-client-capabilities"))
        if caps >= KNOWN_CAPABILITIES:
            # Fully-capable client — nothing to strip.
            return response

        body = await _read_body(response.body_iterator)
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return _passthrough(response, body)

        filtered = filter_envelope(data, caps)
        if filtered is data:
            return _passthrough(response, body)

        new_body = json.dumps(filtered, ensure_ascii=False).encode("utf-8")

        # One INFO-level line per actual strip so adoption can be read
        # straight from production logs without a separate telemetry
        # pipeline. Structured fields (request_id when available,
        # original vs. filtered byte-size, the missing token set, the
        # envelope type we filtered) land in the JSON log record as-is.
        envelope_type = data.get("type") if isinstance(data, Mapping) else None
        logger.info(
            "capability_gate.filtered",
            extra={
                "path": request.scope.get("path", ""),
                "method": request.method,
                "envelope_type": envelope_type,
                "client_version": request.headers.get("x-client-version", ""),
                "request_id": request.headers.get("x-request-id", ""),
                "caps_received": sorted(caps),
                "caps_missing": sorted(KNOWN_CAPABILITIES - caps),
                "bytes_before": len(body),
                "bytes_after": len(new_body),
            },
        )
        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers["content-length"] = str(len(new_body))
        return Response(
            content=new_body,
            status_code=response.status_code,
            headers=headers,
            media_type="application/json",
        )

    @staticmethod
    def _should_filter(request: Request, response: Response) -> bool:
        path = request.scope.get("path", "")
        if not path.startswith(_GATED_PATH_PREFIXES):
            return False
        content_type = response.headers.get("content-type", "")
        return content_type.startswith("application/json")


async def _read_body(iterator: AsyncIterable[bytes]) -> bytes:
    chunks: list[bytes] = []
    async for chunk in iterator:
        chunks.append(chunk)
    return b"".join(chunks)


def _passthrough(response: Response, body: bytes) -> Response:
    headers = dict(response.headers)
    headers.pop("content-length", None)
    headers["content-length"] = str(len(body))
    return Response(
        content=body,
        status_code=response.status_code,
        headers=headers,
        media_type=response.media_type,
    )
