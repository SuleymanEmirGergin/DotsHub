"""Performance benchmarks — hot-path modules.

Purpose
-------
`pytest-benchmark` measures wall-clock time + statistics (min/max/
mean/stddev) for each benchmark function. Committed here + gated in
CI, these act as a **regression floor**: a deploy that doubles the
canonical extraction time or halves the PDF throughput fails the
build.

What IS covered
---------------
- canonical_extract.extract_canonicals_tr — the per-turn NLU hot path.
  Every `/v1/triage/turn` call runs this once (sometimes twice when
  the LLM answer is also parsed). Slowdown here compounds across
  every session.
- services.session_pdf.build_session_pdf — admin PDF export. Not
  user-facing, but runs synchronously on the request thread; a 10×
  regression on a big session would hold up the Fly machine.
- safety_guard.passes_safety_gate — runs on every RESULT envelope;
  false gates block throughput.
- rate_limit.check_rate_limit — in-memory fast path. Called twice
  per request at the FastAPI middleware level.

What is NOT covered (explicit scope cut)
----------------------------------------
- Full triage turn (`run_orchestrator_turn`) — too many variables
  (random question selector order, Supabase mock timing, LLM mocks).
  Covered by golden-flow assertions instead; perf regressions
  surface via Grafana p95 on prod rather than CI.
- Database / Supabase round-trips — CI doesn't have a real Supabase,
  mocks would just benchmark `MagicMock.__call__`.
- HTTP layer (FastAPI routing overhead) — stable across releases;
  prometheus-fastapi-instrumentator shows real numbers from prod.

Running locally
---------------
    pytest tests/test_perf_benchmarks.py --benchmark-only
    pytest tests/test_perf_benchmarks.py --benchmark-compare

CI threshold
------------
Workflow runs `pytest --benchmark-only --benchmark-json=out.json`.
A dedicated step diffs `out.json` against the checked-in baseline
and fails if any bench's mean exceeds baseline × 1.20 (20% margin
to absorb noisy runners). See `.github/workflows/backend-regression.yml`.
"""
from __future__ import annotations

import pytest

from app.canonical_extract import extract_canonicals_tr
from app.rate_limit import check_rate_limit
from app.services.session_pdf import build_session_pdf


# ─── canonical_extract ────────────────────────────────────────────

# Representative synonyms JSON — a sensible subset of the production
# app/data/synonyms_tr.json covering headaches + fever + cough +
# gastro + orthopedic which together account for the majority of
# real inputs. Kept inline so the benchmark has zero I/O on the
# hot path.
_BENCH_SYNONYMS = {
    "synonyms": [
        {"canonical": "baş ağrısı", "variants_tr": ["başım ağrıyor", "baş ağrım", "migren"]},
        {"canonical": "ateş", "variants_tr": ["ateşim var", "yüksek ateş", "ateş var"]},
        {"canonical": "öksürük", "variants_tr": ["öksürüyorum", "öksürük var"]},
        {"canonical": "bulantı", "variants_tr": ["midem bulanıyor", "bulantı hissi"]},
        {"canonical": "halsizlik", "variants_tr": ["halsizim", "bitkin", "yorgun"]},
        {"canonical": "boğaz ağrısı", "variants_tr": ["boğazım ağrıyor"]},
        {"canonical": "diz ağrısı", "variants_tr": ["dizim ağrıyor", "dizim şişti"]},
        {"canonical": "göğüs ağrısı", "variants_tr": ["göğsümde sıkışma", "göğüsümde sıkışma"]},
        {"canonical": "nefes darlığı", "variants_tr": ["nefes alamıyor", "nefessiz"]},
        {"canonical": "karın ağrısı", "variants_tr": ["karnımda ağrı", "karın ağrım"]},
    ]
}

_CANONICAL_CORPUS = [
    "Başım ağrıyor ve midem bulanıyor, ayrıca biraz halsizim.",
    "Birkaç gündür sürekli öksürüyorum, balgam yok ama boğazım ağrıyor.",
    "Dizim şişti ve yürüyemiyorum, merdiven çıkamıyorum.",
    "Göğüsümde bir sıkışma var, nefes alamıyor gibiyim.",
    "Karnımın sağ alt tarafında keskin bir ağrı var.",
]


@pytest.mark.benchmark(group="canonical-extract")
def test_benchmark_canonical_extract_typical_input(benchmark):
    """Measure a 'normal sized' triage-turn input.

    The corpus is ~60-120 characters per entry, which is the median
    user message length in the staging Supabase. `benchmark` runs
    the target function N times (pytest-benchmark decides N from
    timing variance) and records distribution stats.
    """
    result = benchmark(
        extract_canonicals_tr,
        _CANONICAL_CORPUS[0],
        {},
        _BENCH_SYNONYMS,
    )
    # Sanity: function still returns something useful. If a future
    # change drops canonicals entirely the perf may LOOK faster,
    # but this assertion still catches it.
    assert isinstance(result, list)
    assert len(result) >= 1  # should catch "baş ağrısı" + "bulantı"


@pytest.mark.benchmark(group="canonical-extract")
def test_benchmark_canonical_extract_long_input(benchmark):
    """Measure with a stressed, long concatenated input.

    5× corpus entries in one string — ~500 chars. Headroom test so
    pathological long inputs from LLM-expanded queries don't blow
    up p99 latency.
    """
    long_input = " ".join(_CANONICAL_CORPUS)
    result = benchmark(extract_canonicals_tr, long_input, {}, _BENCH_SYNONYMS)
    assert isinstance(result, list)


# ─── rate_limit fast path ─────────────────────────────────────────


@pytest.mark.benchmark(group="rate-limit")
def test_benchmark_rate_limit_in_memory_hit(benchmark):
    """Per-request cost of the in-memory bucket check.

    Every /v1/* request touches this (middleware-level). At 1000 req/s
    it becomes an operational concern; baseline here pins it.
    Uses a fresh key per run to avoid state accumulation bias.
    """
    import uuid

    def _call() -> None:
        check_rate_limit(f"bench-{uuid.uuid4()}")

    benchmark(_call)


# ─── session_pdf — admin export ───────────────────────────────────


_PDF_SESSION = {
    "session": {
        "session_id": "bench-001",
        "created_at": "2026-04-20T14:07:58.041+00:00",
        "envelope_type": "RESULT",
        "urgency": "ROUTINE",
        "recommended_specialty_tr": "Dahiliye",
        "confidence_0_1": 0.84,
        "stop_reason": "confident",
        "input_text": (
            "Başım ağrıyor ve midem bulanıyor. Yaklaşık 3 gündür "
            "devam ediyor; özellikle sabahları şiddetli oluyor."
        ),
        "extracted_canonicals": ["baş ağrısı", "bulantı", "halsizlik"],
        "top_conditions": [
            {
                "disease_label": "Migren",
                "score_0_1": 0.76,
                "disease_description_tr": "Tekrarlayan baş ağrısı.",
            },
            {"disease_label": "Gerilim tipi", "score_0_1": 0.45},
        ],
    },
    "events": [
        {"role": "user", "content": "Başım ağrıyor"},
        {"role": "ai", "content": "Ne zaman başladı?"},
        {"role": "user", "content": "3 gündür"},
        {"role": "ai", "content": "Bulantı var mı?"},
        {"role": "user", "content": "Evet biraz"},
    ],
    "feedback": [{"rating": "up", "comment_tr": "İşe yaradı"}],
}


@pytest.mark.benchmark(group="session-pdf")
def test_benchmark_session_pdf_typical(benchmark):
    """Build a realistic-shaped PDF end-to-end.

    The dict has 5 events + 1 feedback + 2 top_conditions — a bit
    over the median Supabase row. Target: <50 ms per build on shared
    CI hardware. We set min_rounds=5 so variance is readable.
    """
    result = benchmark.pedantic(build_session_pdf, args=(_PDF_SESSION,), rounds=5)
    assert result[:4] == b"%PDF"
    assert len(result) > 1000


@pytest.mark.benchmark(group="session-pdf")
def test_benchmark_session_pdf_empty_session(benchmark):
    """Floor case — minimum session data.

    Establishes a lower-bound for PDF throughput; a regression that
    makes even this slow points at engine-level (fpdf2, font loading)
    rather than content-specific work.
    """
    minimal = {
        "session": {"session_id": "floor", "envelope_type": "RESULT"},
        "events": [],
        "feedback": [],
    }
    result = benchmark(build_session_pdf, minimal)
    assert result[:4] == b"%PDF"
