#!/usr/bin/env python3
"""Validate Kaggle symptom mapping quality and emit a guardrail report."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
DEFAULT_DATA_DIR = BACKEND_DIR / "app" / "data"
DEFAULT_CONFIG_PATH = BACKEND_DIR.parent / "config" / "kaggle_mapping_guardrails.json"
DEFAULT_REPORTS_DIR = BACKEND_DIR / "reports"


DEFAULT_GUARDRAILS: Dict[str, Any] = {
    "null_allowlist": [],
    "coverage": {
        "min_total_symptoms": 3,
        "min_non_null_ratio_critical": 0.6,
    },
    "canonical_reachability": {
        "require_any_source": ["synonyms", "question_bank", "specialty_keywords"],
    },
    "collapse": {
        "max_en_symptoms_per_canonical_warning": 4,
        "min_non_null_symptoms_for_disease_check": 3,
        "max_single_canonical_share_warning": 0.75,
    },
}


def _load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def _merge_dict(defaults: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(defaults)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_guardrails(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return DEFAULT_GUARDRAILS
    cfg = _load_json(path)
    if not isinstance(cfg, dict):
        return DEFAULT_GUARDRAILS
    return _merge_dict(DEFAULT_GUARDRAILS, cfg)


def _collect_dataset_symptoms(disease_symptoms: Dict[str, List[str]]) -> Set[str]:
    symptoms: Set[str] = set()
    for disease_syms in disease_symptoms.values():
        for symptom in disease_syms:
            symptom_key = _normalize(symptom)
            if symptom_key:
                symptoms.add(symptom_key)
    return symptoms


def _collect_synonym_canonicals(synonyms_json: Dict[str, Any]) -> Set[str]:
    out: Set[str] = set()
    for row in synonyms_json.get("synonyms", []):
        canonical = _normalize(row.get("canonical"))
        if canonical:
            out.add(canonical)
    return out


def _collect_question_canonicals(question_bank: Dict[str, Any]) -> Set[str]:
    out: Set[str] = set()
    for row in question_bank.get("questions", []):
        canonical = _normalize(row.get("canonical_symptom"))
        if canonical:
            out.add(canonical)
    return out


def _collect_specialty_terms(specialty_keywords: Dict[str, Any]) -> Set[str]:
    out: Set[str] = set()
    for specialty in specialty_keywords.get("specialties", []):
        for key in ("keywords_tr", "negative_keywords_tr"):
            for term in specialty.get(key, []):
                normalized = _normalize(term)
                if normalized:
                    out.add(normalized)
    return out


def _is_non_null_mapping(value: Any) -> bool:
    return isinstance(value, str) and bool(_normalize(value))


def _summarize_issue(check: str, message: str, details: Optional[Any] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"check": check, "message": message}
    if details is not None:
        payload["details"] = details
    return payload


def run_validation(
    data_dir: Path,
    guardrails_config_path: Path,
    reports_dir: Path,
) -> Tuple[Dict[str, Any], int, Path]:
    disease_symptoms_path = data_dir / "kaggle_cache" / "disease_symptoms.json"
    mapping_path = data_dir / "kaggle_cache" / "kaggle_to_canonical.json"
    synonyms_path = data_dir / "synonyms_tr.json"
    question_bank_path = data_dir / "symptom_question_bank_tr.json"
    specialty_keywords_path = data_dir / "specialty_keywords_tr.json"

    required_paths = [
        disease_symptoms_path,
        mapping_path,
        synonyms_path,
        question_bank_path,
        specialty_keywords_path,
    ]
    missing_paths = [str(path) for path in required_paths if not path.exists()]
    if missing_paths:
        report = {
            "generated_at": _now_iso(),
            "status": "fail",
            "summary": {
                "critical_count": 1,
                "warning_count": 0,
            },
            "critical_violations": [
                _summarize_issue(
                    "required_files",
                    "Required input files are missing.",
                    {"missing_paths": missing_paths},
                )
            ],
            "warnings": [],
        }
        reports_dir.mkdir(parents=True, exist_ok=True)
        out_path = reports_dir / f"kaggle_mapping_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report, 2, out_path

    guardrails = _load_guardrails(guardrails_config_path)

    disease_symptoms_raw = _load_json(disease_symptoms_path)
    mapping_raw = _load_json(mapping_path)
    synonyms_json = _load_json(synonyms_path)
    question_bank_json = _load_json(question_bank_path)
    specialty_keywords_json = _load_json(specialty_keywords_path)

    disease_symptoms: Dict[str, List[str]] = {}
    for disease, syms in disease_symptoms_raw.items():
        normalized = [_normalize(symptom) for symptom in syms]
        disease_symptoms[disease] = [symptom for symptom in normalized if symptom]

    mapping: Dict[str, Any] = {}
    for symptom_key, canonical in mapping_raw.items():
        key = _normalize(symptom_key)
        if not key:
            continue
        mapping[key] = canonical

    dataset_symptom_keys = _collect_dataset_symptoms(disease_symptoms)
    mapping_keys = set(mapping.keys())
    missing_map_keys = sorted(dataset_symptom_keys - mapping_keys)

    null_allowlist = {
        _normalize(item) for item in guardrails.get("null_allowlist", [])
        if _normalize(item)
    }
    null_map_keys = sorted(
        key for key, value in mapping.items()
        if value is None
    )
    unexpected_null_keys = sorted(set(null_map_keys) - null_allowlist)

    coverage_cfg = guardrails.get("coverage", {})
    min_total_for_coverage = int(coverage_cfg.get("min_total_symptoms", 3))
    min_non_null_ratio_critical = float(coverage_cfg.get("min_non_null_ratio_critical", 0.6))

    per_disease_coverage: List[Dict[str, Any]] = []
    low_coverage_diseases: List[Dict[str, Any]] = []
    mapped_non_null_total = 0
    mapped_total = 0
    dataset_total = 0

    for disease, symptoms in disease_symptoms.items():
        total = len(symptoms)
        if total == 0:
            continue
        dataset_total += total
        mapped_total += sum(1 for symptom in symptoms if symptom in mapping)
        mapped_non_null = sum(
            1 for symptom in symptoms
            if _is_non_null_mapping(mapping.get(symptom))
        )
        mapped_non_null_total += mapped_non_null
        ratio = mapped_non_null / total
        row = {
            "disease_label": disease,
            "total_symptoms": total,
            "mapped_non_null": mapped_non_null,
            "coverage_ratio": round(ratio, 4),
        }
        per_disease_coverage.append(row)
        if total >= min_total_for_coverage and ratio < min_non_null_ratio_critical:
            low_coverage_diseases.append(row)

    canonical_from_mapping = sorted({
        _normalize(value)
        for value in mapping.values()
        if _is_non_null_mapping(value)
    })

    synonyms_canonicals = _collect_synonym_canonicals(synonyms_json)
    question_canonicals = _collect_question_canonicals(question_bank_json)
    specialty_terms = _collect_specialty_terms(specialty_keywords_json)

    unreachable_canonicals: List[str] = []
    reachability_rows: List[Dict[str, Any]] = []
    for canonical in canonical_from_mapping:
        in_sources = []
        if canonical in synonyms_canonicals:
            in_sources.append("synonyms")
        if canonical in question_canonicals:
            in_sources.append("question_bank")
        if canonical in specialty_terms:
            in_sources.append("specialty_keywords")

        reachability_rows.append({
            "canonical": canonical,
            "sources": in_sources,
        })
        if not in_sources:
            unreachable_canonicals.append(canonical)

    collapse_cfg = guardrails.get("collapse", {})
    max_en_per_canonical_warning = int(
        collapse_cfg.get("max_en_symptoms_per_canonical_warning", 4)
    )
    min_non_null_for_disease_collapse = int(
        collapse_cfg.get("min_non_null_symptoms_for_disease_check", 3)
    )
    max_single_canonical_share_warning = float(
        collapse_cfg.get("max_single_canonical_share_warning", 0.75)
    )

    canonical_to_en: Dict[str, List[str]] = defaultdict(list)
    for symptom_key, canonical in mapping.items():
        canonical_norm = _normalize(canonical)
        if canonical_norm:
            canonical_to_en[canonical_norm].append(symptom_key)

    global_collapse_hotspots: List[Dict[str, Any]] = []
    for canonical, en_list in sorted(canonical_to_en.items()):
        if len(en_list) > max_en_per_canonical_warning:
            global_collapse_hotspots.append({
                "canonical": canonical,
                "en_symptom_count": len(en_list),
                "en_symptoms": sorted(en_list),
            })

    disease_collapse_warnings: List[Dict[str, Any]] = []
    for disease, symptoms in disease_symptoms.items():
        mapped_canonicals = [
            _normalize(mapping.get(symptom))
            for symptom in symptoms
            if _is_non_null_mapping(mapping.get(symptom))
        ]
        mapped_canonicals = [c for c in mapped_canonicals if c]
        non_null_total = len(mapped_canonicals)
        if non_null_total < min_non_null_for_disease_collapse:
            continue
        counts = Counter(mapped_canonicals)
        top_canonical, top_count = counts.most_common(1)[0]
        share = top_count / non_null_total
        if share > max_single_canonical_share_warning:
            disease_collapse_warnings.append({
                "disease_label": disease,
                "mapped_non_null": non_null_total,
                "top_canonical": top_canonical,
                "top_canonical_share": round(share, 4),
                "distribution": dict(counts),
            })

    critical_violations: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    if missing_map_keys:
        critical_violations.append(
            _summarize_issue(
                "mapping_completeness",
                "Some disease_symptoms keys are missing in kaggle_to_canonical.",
                {"missing_keys": missing_map_keys[:50], "missing_count": len(missing_map_keys)},
            )
        )

    if unexpected_null_keys:
        critical_violations.append(
            _summarize_issue(
                "null_allowlist",
                "Found null mappings outside allowlist.",
                {"unexpected_null_keys": unexpected_null_keys},
            )
        )

    if low_coverage_diseases:
        critical_violations.append(
            _summarize_issue(
                "disease_coverage",
                "One or more diseases are below non-null coverage threshold.",
                {
                    "threshold_ratio": min_non_null_ratio_critical,
                    "diseases": low_coverage_diseases[:50],
                    "count": len(low_coverage_diseases),
                },
            )
        )

    if unreachable_canonicals:
        critical_violations.append(
            _summarize_issue(
                "canonical_reachability",
                "Some canonicals are unreachable from synonyms/question bank/specialty keywords.",
                {"unreachable_canonicals": unreachable_canonicals},
            )
        )

    if global_collapse_hotspots:
        warnings.append(
            _summarize_issue(
                "collapse_global",
                "Many EN symptoms collapse to the same canonical.",
                {
                    "threshold_count": max_en_per_canonical_warning,
                    "hotspots": global_collapse_hotspots,
                },
            )
        )

    if disease_collapse_warnings:
        warnings.append(
            _summarize_issue(
                "collapse_per_disease",
                "High single-canonical share detected in some diseases.",
                {
                    "threshold_share": max_single_canonical_share_warning,
                    "diseases": disease_collapse_warnings[:50],
                    "count": len(disease_collapse_warnings),
                },
            )
        )

    overall_non_null_ratio = (mapped_non_null_total / dataset_total) if dataset_total else 1.0
    overall_map_presence_ratio = (mapped_total / dataset_total) if dataset_total else 1.0

    report: Dict[str, Any] = {
        "generated_at": _now_iso(),
        "status": "fail" if critical_violations else "pass",
        "inputs": {
            "data_dir": str(data_dir),
            "guardrails_config": str(guardrails_config_path),
        },
        "summary": {
            "dataset_symptom_key_count": len(dataset_symptom_keys),
            "mapping_key_count": len(mapping_keys),
            "mapping_null_count": len(null_map_keys),
            "mapping_non_null_count": len(mapping_keys) - len(null_map_keys),
            "unique_canonical_count": len(canonical_from_mapping),
            "overall_mapped_ratio": round(overall_map_presence_ratio, 4),
            "overall_non_null_ratio": round(overall_non_null_ratio, 4),
            "critical_count": len(critical_violations),
            "warning_count": len(warnings),
        },
        "checks": {
            "mapping_completeness": {
                "missing_keys": missing_map_keys,
            },
            "null_allowlist": {
                "null_allowlist": sorted(null_allowlist),
                "null_keys": null_map_keys,
                "unexpected_null_keys": unexpected_null_keys,
            },
            "disease_coverage": {
                "threshold_ratio": min_non_null_ratio_critical,
                "rows": sorted(
                    per_disease_coverage,
                    key=lambda row: row["coverage_ratio"],
                ),
                "low_coverage": low_coverage_diseases,
            },
            "canonical_reachability": {
                "sources": {
                    "synonyms_canonical_count": len(synonyms_canonicals),
                    "question_canonical_count": len(question_canonicals),
                    "specialty_keyword_term_count": len(specialty_terms),
                },
                "rows": reachability_rows,
                "unreachable_canonicals": unreachable_canonicals,
            },
            "collapse": {
                "global_hotspots": global_collapse_hotspots,
                "disease_hotspots": disease_collapse_warnings,
            },
        },
        "critical_violations": critical_violations,
        "warnings": warnings,
    }

    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = reports_dir / f"kaggle_mapping_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    exit_code = 2 if critical_violations else 0
    return report, exit_code, out_path


def _print_human_summary(report: Dict[str, Any], report_path: Path) -> None:
    summary = report.get("summary", {})
    print("Kaggle mapping validation summary")
    print(f"  status: {report.get('status')}")
    print(
        "  coverage (non-null): "
        f"{summary.get('overall_non_null_ratio', 0.0):.2%}"
    )
    print(
        "  critical: "
        f"{summary.get('critical_count', 0)}"
        f", warnings: {summary.get('warning_count', 0)}"
    )

    for issue in report.get("critical_violations", []):
        print(f"  [CRITICAL] {issue.get('check')}: {issue.get('message')}")

    for issue in report.get("warnings", []):
        print(f"  [WARNING]  {issue.get('check')}: {issue.get('message')}")

    print(f"  report: {report_path}")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Kaggle mapping quality against guardrails.",
    )
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="Path to backend/app/data directory.",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to guardrail config JSON.",
    )
    parser.add_argument(
        "--reports-dir",
        default=str(DEFAULT_REPORTS_DIR),
        help="Output directory for validation reports.",
    )
    parser.add_argument(
        "--json-out",
        default=None,
        help="Optional explicit JSON report output path.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    report, exit_code, default_report_path = run_validation(
        data_dir=Path(args.data_dir),
        guardrails_config_path=Path(args.config),
        reports_dir=Path(args.reports_dir),
    )

    report_path = default_report_path
    if args.json_out:
        report_path = Path(args.json_out)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    _print_human_summary(report, report_path)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
