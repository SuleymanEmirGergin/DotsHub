"""Regression guard for runtime config resolution.

Before the cwd-path fix, load_runtime() resolved "config/" relative to
os.getcwd(), so CI (which cd's into backend/) silently loaded 0
emergency rules — every specialized emergency rule (suicidal-plan,
DKA, infant-fever, sudden-vision-loss, ectopic, etc.) became dead
code. This suite pins three contracts:

  1. load_runtime() loads the 19 curated emergency rules regardless
     of the caller's cwd.
  2. Missing config surfaces as a WARNING — never silently swallowed.
  3. PRETRIAGE_CONFIG_DIR env var overrides the __file__-derived path
     (so deployments can relocate config without code changes).
"""

from __future__ import annotations

import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.runtime import load_runtime, _resolve_config_dir


# Resolve the real data dir once — tests below do not depend on cwd.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_DATA_DIR = str(_BACKEND_DIR / "app" / "data")


class ResolveConfigDirTests(unittest.TestCase):
    """_resolve_config_dir() must be cwd-invariant."""

    def test_default_points_at_repo_root_config(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PRETRIAGE_CONFIG_DIR", None)
            resolved = _resolve_config_dir()
        # repo_root / config — three parents up from backend/app/runtime.py
        expected = _BACKEND_DIR.parent / "config"
        self.assertEqual(resolved.resolve(), expected.resolve())

    def test_env_override_wins(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"PRETRIAGE_CONFIG_DIR": td}):
                resolved = _resolve_config_dir()
        self.assertEqual(str(resolved), str(Path(td).resolve()))

    def test_resolve_is_cwd_independent(self):
        """Call from an unrelated pre-existing cwd — result must not change.

        Uses Path.home() instead of tempfile.TemporaryDirectory because
        Python 3.14 on Windows still races on chdir'd-into temp dir cleanup
        even with ignore_cleanup_errors. Any stable pre-existing dir works
        for proving cwd independence.
        """
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PRETRIAGE_CONFIG_DIR", None)
            original_cwd = os.getcwd()
            try:
                os.chdir(Path.home())
                resolved = _resolve_config_dir()
            finally:
                os.chdir(original_cwd)
        expected = _BACKEND_DIR.parent / "config"
        self.assertEqual(resolved.resolve(), expected.resolve())


class LoadRuntimeEmergencyRulesTests(unittest.TestCase):
    """The P0 regression guard: emergency rules must reach the runtime."""

    def test_loads_emergency_rules_from_backend_cwd(self):
        """This is the exact scenario the bug broke: cwd = backend/."""
        original_cwd = os.getcwd()
        try:
            os.chdir(_BACKEND_DIR)
            rt = load_runtime(data_dir="app/data")
        finally:
            os.chdir(original_cwd)
        rules = rt.emergency_rules_cfg.get("rules", [])
        self.assertGreater(
            len(rules),
            10,
            f"Expected >10 emergency rules from backend/ cwd, got {len(rules)}. "
            "If this fails, the cwd-path regression has returned — CI will "
            "silently ship with dead emergency rules.",
        )

    def test_loads_emergency_rules_from_repo_root_cwd(self):
        original_cwd = os.getcwd()
        try:
            os.chdir(_BACKEND_DIR.parent)
            rt = load_runtime(data_dir=_DATA_DIR)
        finally:
            os.chdir(original_cwd)
        self.assertGreater(len(rt.emergency_rules_cfg.get("rules", [])), 10)

    def test_loads_emergency_rules_from_unrelated_cwd(self):
        """From an unrelated pre-existing cwd — config resolves via __file__."""
        original_cwd = os.getcwd()
        try:
            os.chdir(Path.home())
            rt = load_runtime(data_dir=_DATA_DIR)
        finally:
            os.chdir(original_cwd)
        self.assertGreater(len(rt.emergency_rules_cfg.get("rules", [])), 10)

    def test_key_safety_critical_rules_are_present(self):
        """Pin the specific rule ids the triage triage doc calls out as P0."""
        rt = load_runtime(data_dir=_DATA_DIR)
        ids = {r.get("id") for r in rt.emergency_rules_cfg.get("rules", [])}
        required = {
            "psychiatric_emergency_active_plan",  # suicidal plan
            "infant_fever_under3months",
            "sudden_vision_loss",
            "acute_glaucoma_crisis",
            "dka_suspect",
            "ectopic_pregnancy_suspect",
            "febrile_seizure_active",
            "acute_appendicitis_suspect",
        }
        missing = required - ids
        self.assertFalse(
            missing,
            f"Safety-critical rules missing from loaded config: {missing}",
        )


class LoadRuntimeMissingConfigTests(unittest.TestCase):
    """A missing config file must produce a WARNING, not a silent pass."""

    def test_missing_config_dir_logs_warning(self):
        with tempfile.TemporaryDirectory() as empty_dir:
            with patch.dict(os.environ, {"PRETRIAGE_CONFIG_DIR": empty_dir}):
                with self.assertLogs("app.runtime", level="WARNING") as log_ctx:
                    rt = load_runtime(data_dir=_DATA_DIR)
        self.assertEqual(rt.emergency_rules_cfg, {})
        joined = "\n".join(log_ctx.output)
        self.assertIn("emergency_rules.json not found", joined)


if __name__ == "__main__":
    unittest.main()
