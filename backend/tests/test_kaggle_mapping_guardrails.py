from __future__ import annotations

import json
from pathlib import Path
from shutil import rmtree
import unittest
from uuid import uuid4

from scripts.validate_kaggle_mapping import run_validation


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_minimal_data_tree(tmp_path: Path) -> Path:
    data_dir = tmp_path / "app" / "data"
    _write_json(
        data_dir / "synonyms_tr.json",
        {
            "synonyms": [
                {"canonical": "c1", "variants_tr": ["v1"]},
                {"canonical": "c2", "variants_tr": ["v2"]},
            ]
        },
    )
    _write_json(
        data_dir / "symptom_question_bank_tr.json",
        {
            "questions": [
                {"canonical_symptom": "c1"},
                {"canonical_symptom": "c2"},
            ]
        },
    )
    _write_json(
        data_dir / "specialty_keywords_tr.json",
        {
            "specialties": [
                {
                    "id": "internal",
                    "keywords_tr": ["c1", "c2"],
                    "negative_keywords_tr": [],
                }
            ]
        },
    )
    return data_dir


class KaggleMappingGuardrailTests(unittest.TestCase):
    def _mk_workspace_tmp(self) -> Path:
        base = Path("reports") / ".tmp_guardrails"
        base.mkdir(parents=True, exist_ok=True)
        case_path = base / f"case_{uuid4().hex}"
        case_path.mkdir(parents=True, exist_ok=False)
        return case_path

    def test_guardrails_fail_on_unexpected_null(self):
        tmp_path = self._mk_workspace_tmp()
        try:
            data_dir = _build_minimal_data_tree(tmp_path)
            _write_json(
                data_dir / "kaggle_cache" / "disease_symptoms.json",
                {"DiseaseA": ["s1", "s2", "s3"]},
            )
            _write_json(
                data_dir / "kaggle_cache" / "kaggle_to_canonical.json",
                {"s1": "c1", "s2": None, "s3": "c2"},
            )
            _write_json(
                tmp_path / "config" / "kaggle_mapping_guardrails.json",
                {
                    "null_allowlist": [],
                    "coverage": {
                        "min_total_symptoms": 3,
                        "min_non_null_ratio_critical": 0.6,
                    },
                },
            )

            report, exit_code, report_path = run_validation(
                data_dir=data_dir,
                guardrails_config_path=tmp_path / "config" / "kaggle_mapping_guardrails.json",
                reports_dir=tmp_path / "reports",
            )

            self.assertEqual(exit_code, 2)
            self.assertEqual(report["status"], "fail")
            self.assertTrue(report_path.exists())
            checks = [x["check"] for x in report["critical_violations"]]
            self.assertIn("null_allowlist", checks)
        finally:
            rmtree(tmp_path, ignore_errors=True)

    def test_guardrails_warn_on_collapse_but_pass(self):
        tmp_path = self._mk_workspace_tmp()
        try:
            data_dir = _build_minimal_data_tree(tmp_path)
            _write_json(
                data_dir / "kaggle_cache" / "disease_symptoms.json",
                {"DiseaseA": ["s1", "s2", "s3", "s4"]},
            )
            _write_json(
                data_dir / "kaggle_cache" / "kaggle_to_canonical.json",
                {"s1": "c1", "s2": "c1", "s3": "c1", "s4": "c1"},
            )
            _write_json(
                tmp_path / "config" / "kaggle_mapping_guardrails.json",
                {
                    "null_allowlist": [],
                    "coverage": {
                        "min_total_symptoms": 3,
                        "min_non_null_ratio_critical": 0.6,
                    },
                    "collapse": {
                        "max_en_symptoms_per_canonical_warning": 2,
                        "min_non_null_symptoms_for_disease_check": 3,
                        "max_single_canonical_share_warning": 0.75,
                    },
                },
            )

            report, exit_code, report_path = run_validation(
                data_dir=data_dir,
                guardrails_config_path=tmp_path / "config" / "kaggle_mapping_guardrails.json",
                reports_dir=tmp_path / "reports",
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(report["status"], "pass")
            self.assertTrue(report_path.exists())
            self.assertGreater(report["summary"]["warning_count"], 0)
        finally:
            rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
