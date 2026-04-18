"""C1 multi-tenant catalog loading — pin the tenant-specific lookup.

Before C1, curated_conditions.json was single-tenant. Hospitals with
different clinical labeling (A hastanesi vs B hastanesi) couldn't
customize their catalog without forking the entire data directory.

After C1, load_runtime(tenant_id=...) looks for
curated_conditions.<tenant>.json first and falls back to the default
when the tenant file is absent. These tests lock in both paths and
confirm that the per-tenant injection label set is derived live.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from app.runtime import load_runtime
from app.triage_engine import _curated_injected_labels


_DATA_DIR = str(Path(__file__).resolve().parent.parent / "app" / "data")


class DefaultTenantTests(unittest.TestCase):
    """The implicit default path — current production behaviour."""

    def test_default_tenant_loads_default_catalog(self):
        rt = load_runtime(data_dir=_DATA_DIR)
        conditions = (rt.curated_conditions or {}).get("conditions", {})
        self.assertGreater(
            len(conditions),
            5,
            "Default tenant should load the 8-condition default catalog",
        )
        desc = conditions.get("Panik Bozukluk", {}).get("disease_description_tr", "")
        self.assertNotIn(
            "[DEMO TENANT]",
            desc,
            "Default catalog must not contain demo-hospital markers",
        )

    def test_default_tenant_explicit_param_matches_implicit(self):
        rt_implicit = load_runtime(data_dir=_DATA_DIR)
        rt_explicit = load_runtime(data_dir=_DATA_DIR, tenant_id="default")
        self.assertEqual(
            (rt_implicit.curated_conditions or {}).get("conditions", {}).keys(),
            (rt_explicit.curated_conditions or {}).get("conditions", {}).keys(),
        )


class TenantSpecificCatalogTests(unittest.TestCase):
    """demo_hospital ships a tenant-specific catalog as a test fixture."""

    def test_demo_hospital_loads_tenant_specific_catalog(self):
        rt = load_runtime(data_dir=_DATA_DIR, tenant_id="demo_hospital")
        conditions = (rt.curated_conditions or {}).get("conditions", {})
        self.assertEqual(
            set(conditions.keys()),
            {"Panik Bozukluk"},
            "demo_hospital tenant has only Panik Bozukluk in its catalog",
        )
        desc = conditions["Panik Bozukluk"]["disease_description_tr"]
        self.assertIn(
            "[DEMO TENANT]",
            desc,
            "Tenant-specific description must come from the tenant file",
        )

    def test_tenant_specific_tenant_scope_field(self):
        rt = load_runtime(data_dir=_DATA_DIR, tenant_id="demo_hospital")
        self.assertEqual(
            rt.curated_conditions.get("tenant_scope"),
            "demo_hospital",
        )

    def test_unknown_tenant_falls_back_to_default(self):
        """Missing tenant file → default catalog, no crash."""
        rt = load_runtime(data_dir=_DATA_DIR, tenant_id="no_such_hospital")
        conditions = (rt.curated_conditions or {}).get("conditions", {})
        # Default catalog has 8 labels; tenant-specific has 1.
        self.assertGreater(
            len(conditions),
            5,
            "Unknown tenant must fall back to default, not load an empty catalog",
        )


class InjectedLabelsDerivationTests(unittest.TestCase):
    """_curated_injected_labels(runtime) must follow the tenant's catalog."""

    def test_default_tenant_injection_labels_span_catalog(self):
        rt = load_runtime(data_dir=_DATA_DIR)
        labels = _curated_injected_labels(rt)
        catalog_keys = set((rt.curated_conditions or {}).get("conditions", {}).keys())
        self.assertEqual(
            labels,
            catalog_keys,
            "Injected labels must match the tenant's catalog keys",
        )
        self.assertIn("Panik Bozukluk", labels)
        self.assertIn("Bronşiolit", labels)

    def test_demo_hospital_injection_labels_only_cover_tenant_catalog(self):
        rt = load_runtime(data_dir=_DATA_DIR, tenant_id="demo_hospital")
        labels = _curated_injected_labels(rt)
        self.assertEqual(
            labels,
            frozenset({"Panik Bozukluk"}),
            "demo_hospital injection set must be scoped to its catalog",
        )
        # Confirm labels that are curated in default are NOT curated here.
        self.assertNotIn("Bronşiolit", labels)
        self.assertNotIn("Majör Depresyon", labels)


if __name__ == "__main__":
    unittest.main()
