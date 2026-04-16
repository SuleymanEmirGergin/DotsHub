"""Tests for multi-tenant resolution (Faz 1: triage = default, admin = key → tenant)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app import tenant
from app import admin_auth


class TenantTriageTests(unittest.TestCase):
    """Triage always uses default tenant in Faz 1."""

    def test_get_default_tenant_id_returns_default(self):
        with patch("app.tenant.settings.DEFAULT_TENANT_ID", "default"):
            self.assertEqual(tenant.get_default_tenant_id(), "default")

    def test_get_tenant_id_for_triage_returns_default(self):
        with patch("app.tenant.settings.DEFAULT_TENANT_ID", "default"):
            self.assertEqual(tenant.get_tenant_id_for_triage(), "default")

    def test_get_default_tenant_id_fallback_when_empty(self):
        with patch("app.tenant.settings.DEFAULT_TENANT_ID", ""):
            self.assertEqual(tenant.get_default_tenant_id(), "default")


class AdminKeyTenantTests(unittest.TestCase):
    """Admin key → tenant_id resolution."""

    def test_require_admin_key_single_key_returns_tenant_default(self):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch("app.admin_auth._tenant_admin_keys_map", return_value={}),
        ):
            out = admin_auth.require_admin_key("secret")
            self.assertEqual(out["user_id"], "admin_api_key")
            self.assertEqual(out["tenant_id"], "default")

    def test_require_admin_key_single_key_custom_default_tenant(self):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch("app.admin_auth.settings.DEFAULT_TENANT_ID", "org1"),
            patch("app.admin_auth._tenant_admin_keys_map", return_value={}),
        ):
            out = admin_auth.require_admin_key("secret")
            self.assertEqual(out["tenant_id"], "org1")

    def test_require_admin_key_tenant_map_valid_key(self):
        with patch("app.admin_auth._tenant_admin_keys_map", return_value={"key_a": "tenant_a", "key_b": "tenant_b"}):
            out = admin_auth.require_admin_key("key_a")
            self.assertEqual(out["tenant_id"], "tenant_a")
            out2 = admin_auth.require_admin_key("key_b")
            self.assertEqual(out2["tenant_id"], "tenant_b")

    def test_require_admin_key_tenant_map_invalid_key_raises(self):
        with patch("app.admin_auth._tenant_admin_keys_map", return_value={"key_a": "tenant_a"}):
            from fastapi import HTTPException
            with self.assertRaises(HTTPException) as ctx:
                admin_auth.require_admin_key("wrong_key")
            self.assertEqual(ctx.exception.status_code, 401)

    def test_require_admin_key_none_raises(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            admin_auth.require_admin_key(None)
        self.assertEqual(ctx.exception.status_code, 401)


class GetTenantIdFromAdminKeyTests(unittest.TestCase):
    """get_tenant_id_from_admin_key (no auth, for rate limit)."""

    def test_returns_none_when_key_empty(self):
        self.assertIsNone(admin_auth.get_tenant_id_from_admin_key(None))
        self.assertIsNone(admin_auth.get_tenant_id_from_admin_key(""))

    def test_returns_tenant_when_map_has_key(self):
        with patch("app.admin_auth._tenant_admin_keys_map", return_value={"k1": "t1"}):
            self.assertEqual(admin_auth.get_tenant_id_from_admin_key("k1"), "t1")

    def test_returns_none_when_map_key_invalid(self):
        with patch("app.admin_auth._tenant_admin_keys_map", return_value={"k1": "t1"}):
            self.assertIsNone(admin_auth.get_tenant_id_from_admin_key("other"))

    def test_returns_default_when_single_admin_key_matches(self):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch("app.admin_auth._tenant_admin_keys_map", return_value={}),
        ):
            self.assertEqual(admin_auth.get_tenant_id_from_admin_key("secret"), "default")

    def test_returns_none_when_single_admin_key_wrong(self):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch("app.admin_auth._tenant_admin_keys_map", return_value={}),
        ):
            self.assertIsNone(admin_auth.get_tenant_id_from_admin_key("wrong"))


if __name__ == "__main__":
    unittest.main()
