"""Coverage audit script for the Dotshub triage data layer.

Produces a report (human-readable or JSON) comparing the current state of
backend/app/data/*, config/*, and tests/golden_flows/* against the baseline
and targets captured in `coverage_expected.json` (A1 session output).

Usage:
    python backend/scripts/audit_coverage.py            # human report to stdout
    python backend/scripts/audit_coverage.py --json     # structured JSON
    python backend/scripts/audit_coverage.py --fail-on-critical  # exit 1 if critical gaps

Intended use:
    - Local dev: `make audit-coverage` before committing content changes
    - CI: .github/workflows/audit-coverage.yml runs on every PR touching data/
    - Expansion sessions (A2-A10): run after each session to verify progress
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DATA = REPO_ROOT / "backend" / "app" / "data"
KAGGLE_CACHE = BACKEND_DATA / "kaggle_cache"
CONFIG_DIR = REPO_ROOT / "config"
GOLDEN_FLOWS_DIR = REPO_ROOT / "tests" / "golden_flows"
EXPECTED_FILE = Path(__file__).resolve().parent / "coverage_expected.json"


# ── Utilities ──────────────────────────────────────────────────────────────

def _load_json(path: Path) -> Any:
    """Load a JSON file, returning {} if missing and a descriptive error otherwise."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[audit_coverage] Invalid JSON in {path}: {exc}")


def _count_keyword_items(spec: dict) -> tuple[int, int, int]:
    """Return (phrase_count, keyword_count, negative_count) for a specialty entry."""
    phrases = len(spec.get("phrases_tr") or [])
    keywords = len(spec.get("keywords_tr") or [])
    negatives = len(spec.get("negative_keywords_tr") or [])
    return phrases, keywords, negatives


# ── Audit sections ─────────────────────────────────────────────────────────

@dataclass
class SpecialtyRow:
    id: str
    phrases: int
    keywords: int
    negatives: int
    diseases: int
    status: str  # "ok" | "orphan_no_disease" | "missing_keywords"


def audit_specialties() -> dict:
    """Compare keywords-per-specialty against disease-mapping count."""
    keywords_data = _load_json(BACKEND_DATA / "specialty_keywords_tr.json") or {}
    disease_map = _load_json(BACKEND_DATA / "disease_to_specialty.json") or {}

    specialties_raw = keywords_data.get("specialties") or keywords_data
    if isinstance(specialties_raw, dict):
        specialties = specialties_raw
    elif isinstance(specialties_raw, list):
        specialties = {s.get("id", ""): s for s in specialties_raw if isinstance(s, dict)}
    else:
        specialties = {}

    # Count diseases per specialty. The file format uses {"map": [...]} where each
    # entry is {"disease_label": ..., "specialty_id": ..., ...}. Older variants
    # used "entries" — both are accepted.
    disease_counts: Counter[str] = Counter()
    entries = None
    if isinstance(disease_map, dict):
        entries = disease_map.get("map") or disease_map.get("entries")
    if isinstance(entries, list):
        for entry in entries:
            sid = (entry or {}).get("specialty_id")
            if sid:
                disease_counts[sid] += 1

    rows: list[SpecialtyRow] = []
    for sid, spec in specialties.items():
        p, k, n = _count_keyword_items(spec if isinstance(spec, dict) else {})
        dcount = disease_counts.get(sid, 0)
        if p + k == 0 and dcount == 0:
            status = "missing_keywords"
        elif dcount == 0:
            status = "orphan_no_disease"
        else:
            status = "ok"
        rows.append(SpecialtyRow(id=sid, phrases=p, keywords=k, negatives=n, diseases=dcount, status=status))

    # Discover specialties that appear in disease_map but have no keyword entry
    for sid in disease_counts:
        if sid not in specialties:
            rows.append(SpecialtyRow(id=sid, phrases=0, keywords=0, negatives=0, diseases=disease_counts[sid], status="missing_keywords"))

    orphans = sorted(r.id for r in rows if r.status == "orphan_no_disease")
    missing = sorted(r.id for r in rows if r.status == "missing_keywords")

    return {
        "total": len(rows),
        "orphans": orphans,
        "missing": missing,
        "rows": [asdict(r) for r in sorted(rows, key=lambda r: r.id)],
    }


def audit_diseases() -> dict:
    """Compare disease_to_specialty.json with disease_symptoms.json; flag orphans."""
    disease_map = _load_json(BACKEND_DATA / "disease_to_specialty.json") or {}
    disease_symptoms = _load_json(KAGGLE_CACHE / "disease_symptoms.json") or {}

    entries = None
    if isinstance(disease_map, dict):
        entries = disease_map.get("map") or disease_map.get("entries")
    if not isinstance(entries, list):
        entries = []

    mapped_labels = {(e or {}).get("disease_label") for e in entries if isinstance(e, dict)}
    mapped_labels.discard(None)
    mapped_labels.discard("")

    symptom_labels = set(disease_symptoms.keys()) if isinstance(disease_symptoms, dict) else set()

    orphan_in_symptoms = sorted(symptom_labels - mapped_labels)
    orphan_in_mapping = sorted(mapped_labels - symptom_labels)

    return {
        "mapping_total": len(mapped_labels),
        "symptoms_total": len(symptom_labels),
        "orphan_in_symptoms_only": orphan_in_symptoms,
        "orphan_in_mapping_only": orphan_in_mapping,
    }


def audit_canonicals(expected: dict) -> dict:
    """Count canonicals + variants; compare against expected-per-specialty list."""
    syns = _load_json(BACKEND_DATA / "synonyms_tr.json") or {}
    canonical_entries = syns.get("synonyms") if isinstance(syns, dict) else []
    if not isinstance(canonical_entries, list):
        canonical_entries = []

    total_canonicals = len(canonical_entries)
    variants_count: list[int] = []
    all_canonical_labels: set[str] = set()
    weak: list[dict] = []

    for entry in canonical_entries:
        if not isinstance(entry, dict):
            continue
        label = entry.get("canonical_tr") or entry.get("canonical") or ""
        all_canonical_labels.add(label.lower())
        variants = entry.get("variants_tr") or entry.get("variants") or []
        vcount = len(variants) if isinstance(variants, list) else 0
        variants_count.append(vcount)
        if vcount <= 4:
            weak.append({"canonical": label, "variants": vcount})

    variants_total = sum(variants_count)
    variants_avg = round(variants_total / total_canonicals, 2) if total_canonicals else 0

    # Expected-per-specialty check
    expected_by_spec = expected.get("expected_canonicals_by_specialty") or {}
    coverage_by_spec: dict[str, dict] = {}
    for sid, wanted_list in expected_by_spec.items():
        if sid.startswith("_") or not isinstance(wanted_list, list):
            continue
        present, missing = [], []
        for w in wanted_list:
            w_lower = w.lower().strip()
            # Exact match only — substring matching produced false positives
            # (e.g. "yüksek ateş çocuk" matched "ateş"). If fuzzy matching is
            # needed later, add it as a separate pass.
            if w_lower in all_canonical_labels:
                present.append(w)
            else:
                missing.append(w)
        coverage_by_spec[sid] = {
            "expected": len(wanted_list),
            "present": len(present),
            "missing": missing,
            "coverage_pct": round(100 * len(present) / len(wanted_list), 1) if wanted_list else 100.0,
        }

    return {
        "canonicals_total": total_canonicals,
        "variants_total": variants_total,
        "variants_avg": variants_avg,
        "weak_spots_count": len(weak),
        "weak_spots": weak[:10],  # cap for readability
        "expected_by_specialty": coverage_by_spec,
    }


def audit_kaggle_mapping() -> dict:
    """How many Kaggle symptoms map to TR canonicals?"""
    mapping = _load_json(KAGGLE_CACHE / "kaggle_to_canonical.json") or {}
    disease_symptoms = _load_json(KAGGLE_CACHE / "disease_symptoms.json") or {}

    all_kaggle_symptoms: set[str] = set()
    if isinstance(disease_symptoms, dict):
        for symptoms in disease_symptoms.values():
            if isinstance(symptoms, list):
                all_kaggle_symptoms.update(s for s in symptoms if isinstance(s, str))

    mapped_keys = set(mapping.keys()) if isinstance(mapping, dict) else set()
    unmapped = sorted(all_kaggle_symptoms - mapped_keys)

    total = len(all_kaggle_symptoms)
    mapped_count = len(all_kaggle_symptoms & mapped_keys)

    return {
        "kaggle_symptoms_total": total,
        "mapped_count": mapped_count,
        "unmapped_count": len(unmapped),
        "coverage_pct": round(100 * mapped_count / total, 1) if total else 0,
        "unmapped_sample": unmapped[:10],
    }


def audit_rules() -> dict:
    """Emergency + same-day + red-flag counts."""
    emergency = _load_json(CONFIG_DIR / "emergency_rules.json") or {}
    sameday = _load_json(CONFIG_DIR / "sameday_rules.json") or {}
    red_flag = _load_json(BACKEND_DATA / "red_flag_questions.json") or {}

    def _count_rules(data: Any) -> int:
        if isinstance(data, dict):
            rules = data.get("rules")
            if isinstance(rules, list):
                return len(rules)
        if isinstance(data, list):
            return len(data)
        return 0

    red_flag_count = 0
    if isinstance(red_flag, dict):
        qs = red_flag.get("questions")
        if isinstance(qs, list):
            red_flag_count = len(qs)
        else:
            red_flag_count = sum(len(v) for v in red_flag.values() if isinstance(v, list))
    elif isinstance(red_flag, list):
        red_flag_count = len(red_flag)

    return {
        "emergency_rules": _count_rules(emergency),
        "sameday_rules": _count_rules(sameday),
        "red_flag_questions": red_flag_count,
    }


def audit_data_quality(expected: dict) -> dict:
    """Check if known data quality issues (A1 section 3.2) are still present."""
    disease_map = _load_json(BACKEND_DATA / "disease_to_specialty.json") or {}
    entries = None
    if isinstance(disease_map, dict):
        entries = disease_map.get("map") or disease_map.get("entries")
    if not isinstance(entries, list):
        entries = []

    all_labels = [e.get("disease_label", "") for e in entries if isinstance(e, dict)]
    all_labels_set = set(all_labels)

    issues = expected.get("data_quality_issues") or {}
    findings: dict[str, list[str]] = {}
    for issue_type, watchlist in issues.items():
        if issue_type.startswith("_") or not isinstance(watchlist, list):
            continue
        still_present = [label for label in watchlist if label in all_labels_set]
        findings[issue_type] = still_present

    # Additional scan: trailing spaces anywhere
    trailing = [label for label in all_labels if label != label.strip()]
    if trailing:
        findings.setdefault("detected_trailing_spaces", []).extend(trailing)

    return findings


def audit_golden_flows() -> dict:
    """Count golden flow scenarios + specialties covered."""
    if not GOLDEN_FLOWS_DIR.exists():
        return {"total": 0, "specialties_covered": [], "scenarios": []}

    scenarios = []
    specialties_covered: set[str] = set()
    for path in sorted(GOLDEN_FLOWS_DIR.glob("*.json")):
        scenarios.append(path.name)
        data = _load_json(path) or {}
        expected_result = data.get("expected") if isinstance(data, dict) else None
        if isinstance(expected_result, dict):
            # Golden flow files use `recommended_specialty` (current convention);
            # older files may use `specialty_id` or `specialty`.
            spec = (
                expected_result.get("recommended_specialty")
                or expected_result.get("specialty_id")
                or expected_result.get("specialty")
            )
            if isinstance(spec, str):
                specialties_covered.add(spec)

    return {
        "total": len(scenarios),
        "specialties_covered": sorted(specialties_covered),
        "scenarios": scenarios,
    }


# ── Report rendering ───────────────────────────────────────────────────────

@dataclass
class Report:
    generated_at: str
    specialties: dict
    diseases: dict
    canonicals: dict
    kaggle: dict
    rules: dict
    data_quality: dict
    golden_flows: dict
    progress: dict = field(default_factory=dict)


def compute_progress(report: Report, expected: dict) -> dict:
    """Compare current counts to A1 baseline + targets."""
    baseline = expected.get("baseline") or {}
    targets = expected.get("targets") or {}

    current = {
        "canonicals": report.canonicals["canonicals_total"],
        "variants_total": report.canonicals["variants_total"],
        "variants_avg": report.canonicals["variants_avg"],
        "specialties_total": report.specialties["total"],
        "specialties_orphan_count": len(report.specialties["orphans"]),
        "diseases": report.diseases["mapping_total"],
        "emergency_rules": report.rules["emergency_rules"],
        "sameday_rules": report.rules["sameday_rules"],
        "red_flag_questions": report.rules["red_flag_questions"],
        "golden_flows": report.golden_flows["total"],
    }

    def _pct(cur: float, tgt: float) -> float:
        return round(100.0 * cur / tgt, 1) if tgt else 0.0

    progress = {
        "canonicals": {
            "current": current["canonicals"],
            "baseline": baseline.get("canonicals_total"),
            "target": targets.get("canonicals_min"),
            "pct_of_target": _pct(current["canonicals"], targets.get("canonicals_min", 0)),
        },
        "variants_total": {
            "current": current["variants_total"],
            "baseline": baseline.get("variants_total_approx"),
            "target": targets.get("variants_total_min"),
            "pct_of_target": _pct(current["variants_total"], targets.get("variants_total_min", 0)),
        },
        "diseases": {
            "current": current["diseases"],
            "baseline": baseline.get("diseases_total"),
            "target": targets.get("diseases_min"),
            "pct_of_target": _pct(current["diseases"], targets.get("diseases_min", 0)),
        },
        "emergency_rules": {
            "current": current["emergency_rules"],
            "baseline": baseline.get("emergency_rules"),
            "target": targets.get("emergency_rules_min"),
        },
        "sameday_rules": {
            "current": current["sameday_rules"],
            "baseline": baseline.get("sameday_rules"),
            "target": targets.get("sameday_rules_min"),
        },
        "red_flag_questions": {
            "current": current["red_flag_questions"],
            "baseline": baseline.get("red_flag_questions"),
            "target": targets.get("red_flag_questions_min"),
        },
        "golden_flows": {
            "current": current["golden_flows"],
            "baseline": baseline.get("golden_flows"),
            "target": targets.get("golden_flows_min"),
        },
        "orphan_specialties": {
            "current": report.specialties["orphans"],
            "baseline_list": baseline.get("specialties_orphan", []),
            "target": targets.get("specialties_orphan_max", 0),
        },
    }
    return progress


def has_critical_gaps(report: Report) -> bool:
    """Return True if there are critical coverage gaps."""
    if report.specialties["orphans"]:
        return True
    if report.rules["sameday_rules"] == 0:
        return True
    for issues in report.data_quality.values():
        if issues:
            return True
    return False


def render_human(report: Report, expected: dict) -> str:
    lines: list[str] = []

    def hr():
        lines.append("─" * 66)

    def hdr(title: str):
        lines.append("")
        lines.append(f"▶ {title}")
        hr()

    lines.append("╔════════════════════════════════════════════════════════════════╗")
    lines.append("║            DOTSHUB — COVERAGE AUDIT REPORT                     ║")
    lines.append(f"║            Generated: {report.generated_at:<41}║")
    lines.append("╚════════════════════════════════════════════════════════════════╝")

    # Specialties
    hdr("SPECIALTY COVERAGE")
    lines.append(f"{'Specialty':<22} {'Phrases':>8} {'Kywds':>6} {'Neg':>4} {'Diseases':>9}  Status")
    hr()
    status_icon = {"ok": "✓", "orphan_no_disease": "⚠ ORPHAN", "missing_keywords": "⚠ MISSING"}
    for row in report.specialties["rows"]:
        lines.append(
            f"{row['id']:<22} {row['phrases']:>8} {row['keywords']:>6} {row['negatives']:>4} "
            f"{row['diseases']:>9}  {status_icon.get(row['status'], row['status'])}"
        )
    hr()
    lines.append(f"Total: {report.specialties['total']} specialties, "
                 f"{len(report.specialties['orphans'])} orphans, "
                 f"{len(report.specialties['missing'])} missing keywords")

    # Diseases
    hdr("DISEASE COVERAGE")
    lines.append(f"Mapping total: {report.diseases['mapping_total']}")
    lines.append(f"Symptoms total: {report.diseases['symptoms_total']}")
    if report.diseases["orphan_in_symptoms_only"]:
        lines.append(f"Orphan (symptoms only, no specialty): {len(report.diseases['orphan_in_symptoms_only'])}")
        for d in report.diseases["orphan_in_symptoms_only"][:5]:
            lines.append(f"  - {d}")
    if report.diseases["orphan_in_mapping_only"]:
        lines.append(f"Orphan (mapping only, no symptoms): {len(report.diseases['orphan_in_mapping_only'])}")
        for d in report.diseases["orphan_in_mapping_only"][:5]:
            lines.append(f"  - {d}")

    # Canonicals
    hdr("CANONICAL SYMPTOM COVERAGE")
    lines.append(f"Total canonicals: {report.canonicals['canonicals_total']}")
    lines.append(f"Total variants:   {report.canonicals['variants_total']}")
    lines.append(f"Avg variants:     {report.canonicals['variants_avg']}")
    lines.append(f"Weak spots (≤4 variants): {report.canonicals['weak_spots_count']}")
    lines.append("")
    lines.append("Expected canonicals by specialty (from A1 gap analysis):")
    for sid, cov in report.canonicals["expected_by_specialty"].items():
        marker = "✓" if cov["coverage_pct"] >= 80 else ("⚠" if cov["coverage_pct"] >= 30 else "✗")
        lines.append(f"  {marker} {sid:<18} {cov['present']:>2}/{cov['expected']:<2} "
                     f"({cov['coverage_pct']:>5.1f}%)")
        if cov["missing"] and cov["coverage_pct"] < 100:
            preview = ", ".join(cov["missing"][:4])
            if len(cov["missing"]) > 4:
                preview += f", ... (+{len(cov['missing']) - 4} more)"
            lines.append(f"       missing: {preview}")

    # Kaggle mapping
    hdr("KAGGLE ↔ TR MAPPING")
    lines.append(f"Kaggle symptoms total: {report.kaggle['kaggle_symptoms_total']}")
    lines.append(f"Mapped:   {report.kaggle['mapped_count']} ({report.kaggle['coverage_pct']}%)")
    lines.append(f"Unmapped: {report.kaggle['unmapped_count']}")
    if report.kaggle["unmapped_sample"]:
        lines.append("Unmapped sample: " + ", ".join(report.kaggle["unmapped_sample"][:5]))

    # Rules
    hdr("RULES")
    lines.append(f"Emergency rules:       {report.rules['emergency_rules']}")
    if report.rules["sameday_rules"] == 0:
        lines.append(f"Same-day rules:        0  ⚠ EMPTY STUB")
    else:
        lines.append(f"Same-day rules:        {report.rules['sameday_rules']}")
    lines.append(f"Red-flag questions:    {report.rules['red_flag_questions']}")

    # Data quality
    hdr("DATA QUALITY ISSUES (A1 section 3.2)")
    any_issue = False
    for issue_type, items in report.data_quality.items():
        if items:
            any_issue = True
            lines.append(f"⚠ {issue_type}: {len(items)} item(s)")
            for item in items[:5]:
                lines.append(f"    - {item!r}")
    if not any_issue:
        lines.append("✓ No known data quality issues detected.")

    # Golden flows
    hdr("GOLDEN FLOW TEST COVERAGE")
    lines.append(f"Scenarios: {report.golden_flows['total']}")
    lines.append(f"Specialties covered: {len(report.golden_flows['specialties_covered'])}")
    for s in report.golden_flows["specialties_covered"]:
        lines.append(f"  - {s}")

    # Progress
    hdr("PROGRESS vs BASELINE & TARGETS")
    prog = report.progress
    for key in ["canonicals", "variants_total", "diseases",
                "emergency_rules", "sameday_rules", "red_flag_questions", "golden_flows"]:
        if key in prog:
            p = prog[key]
            cur = p.get("current")
            base = p.get("baseline")
            tgt = p.get("target")
            pct = p.get("pct_of_target")
            pct_str = f" ({pct}% of target)" if pct is not None else ""
            lines.append(f"  {key:<22} current={cur:<4}  baseline={base}  target={tgt}{pct_str}")
    op = prog.get("orphan_specialties", {})
    lines.append(f"  orphan_specialties     current={op.get('current')} (target: {op.get('target')})")

    # Summary
    hdr("SUMMARY")
    critical = has_critical_gaps(report)
    if critical:
        lines.append("⚠ CRITICAL GAPS PRESENT")
        if report.specialties["orphans"]:
            lines.append(f"  - {len(report.specialties['orphans'])} orphan specialty (no disease prior): "
                         f"{', '.join(report.specialties['orphans'])}")
        if report.rules["sameday_rules"] == 0:
            lines.append("  - Same-day rules: 0 (empty stub — sameday triage inactive)")
        quality_issue_count = sum(len(v) for v in report.data_quality.values())
        if quality_issue_count:
            lines.append(f"  - {quality_issue_count} known data quality issue(s) unresolved")
    else:
        lines.append("✓ No critical gaps.")
    lines.append("")

    return "\n".join(lines)


def render_json(report: Report) -> str:
    payload = asdict(report)
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ── CLI ────────────────────────────────────────────────────────────────────

def build_report() -> tuple[Report, dict]:
    expected = _load_json(EXPECTED_FILE) or {}
    report = Report(
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z",
        specialties=audit_specialties(),
        diseases=audit_diseases(),
        canonicals=audit_canonicals(expected),
        kaggle=audit_kaggle_mapping(),
        rules=audit_rules(),
        data_quality=audit_data_quality(expected),
        golden_flows=audit_golden_flows(),
    )
    report.progress = compute_progress(report, expected)
    return report, expected


def main() -> int:
    # Force UTF-8 stdout on Windows so box-drawing chars + TR characters render.
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass

    parser = argparse.ArgumentParser(description="Dotshub medical data coverage audit")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable report")
    parser.add_argument("--fail-on-critical", action="store_true",
                        help="Exit 1 if critical gaps are detected (orphan specialties, empty sameday rules, known data quality issues)")
    args = parser.parse_args()

    report, expected = build_report()

    if args.json:
        print(render_json(report))
    else:
        print(render_human(report, expected))

    if args.fail_on_critical and has_critical_gaps(report):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
