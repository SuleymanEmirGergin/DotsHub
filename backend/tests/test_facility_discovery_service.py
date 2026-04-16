"""Tests for app.services.facility_discovery."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import httpx

from app.services.facility_discovery import _haversine_km, discover_facilities


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_get(city_rows, facility_rows):
    """Return a fake httpx client .get() callable.

    Distinguishes city-lookup requests from facility-search requests by
    inspecting the 'q' query param: facility searches contain one of the
    known amenity keywords ('hospital', 'clinic', 'hastane').
    """
    def fake_get(url, params=None, headers=None, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        q = (params or {}).get("q", "")
        if any(kw in q.lower() for kw in ["hospital", "clinic", "hastane"]):
            resp.json.return_value = facility_rows
        else:
            resp.json.return_value = city_rows
        return resp

    return fake_get


def _fake_facility_row(name: str = "Test Hospital", lat: float = 41.01, lon: float = 29.01):
    return {
        "display_name": f"{name}, Kadikoy, Istanbul",
        "name": name,
        "class": "amenity",
        "type": "hospital",
        "lat": str(lat),
        "lon": str(lon),
    }


# ---------------------------------------------------------------------------
# Class 1: disabled feature flag
# ---------------------------------------------------------------------------

class FacilityDiscoveryDisabledTests(unittest.TestCase):
    def test_returns_empty_when_disabled(self):
        with patch("app.services.facility_discovery.settings") as mock_settings:
            mock_settings.FACILITY_DISCOVERY_ENABLED = False
            mock_settings.FACILITY_DISCOVERY_TIMEOUT_SECONDS = 2.5
            result = discover_facilities("Istanbul", "neurology")
        self.assertEqual(result["items"], [])


# ---------------------------------------------------------------------------
# Class 2: empty specialty key
# ---------------------------------------------------------------------------

class FacilityDiscoveryEmptySpecialtyTests(unittest.TestCase):
    def test_empty_specialty_key_returns_empty(self):
        with patch("app.services.facility_discovery.settings") as mock_settings:
            mock_settings.FACILITY_DISCOVERY_ENABLED = True
            mock_settings.FACILITY_DISCOVERY_TIMEOUT_SECONDS = 2.5
            result = discover_facilities("Istanbul", "")
        self.assertEqual(result["items"], [])


# ---------------------------------------------------------------------------
# Class 3: city lookup network failure
# ---------------------------------------------------------------------------

class FacilityDiscoveryCityLookupFailureTests(unittest.TestCase):
    def test_httpx_timeout_returns_empty_not_raises(self):
        def raising_get(url, params=None, headers=None, **kwargs):
            raise httpx.TimeoutException("timeout")

        with patch("app.services.facility_discovery.settings") as mock_settings, \
             patch("app.services.facility_discovery.httpx.Client") as mock_cls:
            mock_settings.FACILITY_DISCOVERY_ENABLED = True
            mock_settings.FACILITY_DISCOVERY_TIMEOUT_SECONDS = 2.5

            mock_client = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_client
            mock_cls.return_value.__exit__.return_value = False
            mock_client.get.side_effect = raising_get

            result = discover_facilities("Istanbul", "neurology", lat=None, lon=None)

        self.assertEqual(result["items"], [])


# ---------------------------------------------------------------------------
# Class 4: success / integration-style
# ---------------------------------------------------------------------------

class FacilityDiscoverySuccessTests(unittest.TestCase):

    def _run_with_mocks(self, city_rows, facility_rows, **kwargs):
        fake_get = _make_fake_get(city_rows, facility_rows)
        with patch("app.services.facility_discovery.settings") as mock_settings, \
             patch("app.services.facility_discovery.httpx.Client") as mock_cls:
            mock_settings.FACILITY_DISCOVERY_ENABLED = True
            mock_settings.FACILITY_DISCOVERY_TIMEOUT_SECONDS = 2.5

            mock_client = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_client
            mock_cls.return_value.__exit__.return_value = False
            mock_client.get.side_effect = fake_get

            return discover_facilities(**kwargs)

    def test_results_include_distance_when_coords_provided(self):
        city_rows = [_fake_facility_row("City", lat=41.0, lon=29.0)]
        facility_rows = [_fake_facility_row("Test Hospital", lat=41.01, lon=29.01)]
        result = self._run_with_mocks(
            city_rows,
            facility_rows,
            city="Istanbul",
            specialty_key="neurology",
            lat=41.0,
            lon=29.0,
        )
        self.assertGreater(len(result["items"]), 0)
        self.assertIn("distance_km", result["items"][0])

    def test_deduplication_prevents_duplicate_entries(self):
        city_rows = [_fake_facility_row("City", lat=41.0, lon=29.0)]
        # Two identical rows
        dup_row = _fake_facility_row("Test Hospital", lat=41.01, lon=29.01)
        facility_rows = [dup_row, dup_row]
        result = self._run_with_mocks(
            city_rows,
            facility_rows,
            city="Istanbul",
            specialty_key="neurology",
        )
        self.assertLessEqual(len(result["items"]), 1)

    def test_limit_respected(self):
        city_rows = [_fake_facility_row("City", lat=41.0, lon=29.0)]
        # 10 distinct rows
        facility_rows = [
            _fake_facility_row(f"Hospital {i}", lat=41.0 + i * 0.01, lon=29.0 + i * 0.01)
            for i in range(10)
        ]
        result = self._run_with_mocks(
            city_rows,
            facility_rows,
            city="Istanbul",
            specialty_key="neurology",
            limit=3,
        )
        self.assertLessEqual(len(result["items"]), 3)

    def test_empty_nominatim_response_returns_empty(self):
        result = self._run_with_mocks(
            [],
            [],
            city="Istanbul",
            specialty_key="neurology",
        )
        self.assertEqual(result["items"], [])


# ---------------------------------------------------------------------------
# Class 5: haversine unit tests
# ---------------------------------------------------------------------------

class HaversineTests(unittest.TestCase):
    def test_same_point_is_zero(self):
        dist = _haversine_km(41.0, 29.0, 41.0, 29.0)
        self.assertAlmostEqual(dist, 0.0, places=5)

    def test_istanbul_ankara_approx_352km(self):
        dist = _haversine_km(41.015, 28.979, 39.920, 32.854)
        self.assertGreater(dist, 300)
        self.assertLess(dist, 400)


if __name__ == "__main__":
    unittest.main()
