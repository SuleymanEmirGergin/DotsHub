"""Unit tests for app/services/facility_discovery.py — Nominatim
(OpenStreetMap) hospital/clinic lookup.

facility_discovery powers the ResultScreen "yakınındaki hastaneler"
list + the `GET /v1/facilities` endpoint. Prior coverage was 14.29%,
which meant every network-failure branch, every dedupe-key collision,
every distance-sort regression could have shipped silently.

Tests cover four layers:
  1. Pure math (`_haversine_km`) — known-value sanity checks.
  2. Pure parsing (`_parse_coord`, `_load_specialty_facility_map`).
  3. Internal HTTP wrapper (`_query_nominatim`) — covers the
     try/except that maps network failures to `query_failed=True`.
  4. End-to-end orchestrator (`discover_facilities`) — covers the
     settings gate, empty-specialty short-circuit, city-geocode
     fallback, tag filtering, dedupe, distance sort, and limit.

httpx is mocked via `patch("app.services.facility_discovery.httpx.Client")`
so no network calls happen in CI — Nominatim is rate-limited (1 rps)
and the tests run hundreds of times per day.
"""

from __future__ import annotations

import math
import unittest
from unittest.mock import MagicMock, patch

from app.services import facility_discovery as fd


def _mock_client_context(responses_by_query):
    """Return a patched httpx.Client that serves canned rows per `q`.

    `responses_by_query` is a dict {query_str: (rows_list, status_code)}.
    Any query not in the dict returns an empty list with 200. If status
    is 500 we raise to exercise the exception branch.
    """

    def _get(url, params=None, headers=None):
        q = (params or {}).get("q", "")
        rows, status = responses_by_query.get(q, ([], 200))
        resp = MagicMock()
        resp.json.return_value = rows
        resp.status_code = status
        if status >= 500:
            resp.raise_for_status.side_effect = RuntimeError(f"HTTP {status}")
        else:
            resp.raise_for_status.return_value = None
        return resp

    client = MagicMock()
    client.get.side_effect = _get
    ctx = MagicMock()
    ctx.__enter__.return_value = client
    ctx.__exit__.return_value = False
    return ctx, client


# ─── _haversine_km ──────────────────────────────────────────────────


class HaversineTests(unittest.TestCase):
    """Great-circle distance calculator. Pure math — if this drifts,
    every 'nearest facility' sort is wrong."""

    def test_zero_distance_for_identical_points(self):
        self.assertAlmostEqual(
            fd._haversine_km(41.015, 28.979, 41.015, 28.979), 0.0, places=3
        )

    def test_istanbul_to_ankara_approx_350km(self):
        # Istanbul (41.015, 28.979) → Ankara (39.925, 32.866).
        # Great-circle distance ≈ 349 km (±2 km tolerance for float math).
        d = fd._haversine_km(41.015, 28.979, 39.925, 32.866)
        self.assertTrue(348 < d < 352, f"unexpected distance: {d}")

    def test_symmetric_in_endpoints(self):
        a = fd._haversine_km(41.0, 29.0, 40.0, 28.0)
        b = fd._haversine_km(40.0, 28.0, 41.0, 29.0)
        self.assertAlmostEqual(a, b, places=6)

    def test_antipodal_points_near_half_earth_circumference(self):
        # (0,0) to (0,180) should give ≈ π × R = ~20015 km.
        d = fd._haversine_km(0, 0, 0, 180)
        self.assertAlmostEqual(d, math.pi * 6371.0, places=0)


# ─── _parse_coord ───────────────────────────────────────────────────


class ParseCoordTests(unittest.TestCase):
    """Defensive coord-parser: Nominatim may return strings, missing
    fields, or garbage — all must produce `None` not a crash."""

    def test_valid_string_coords(self):
        self.assertEqual(
            fd._parse_coord({"lat": "41.015", "lon": "28.979"}),
            (41.015, 28.979),
        )

    def test_valid_float_coords(self):
        self.assertEqual(
            fd._parse_coord({"lat": 41.0, "lon": 29.0}), (41.0, 29.0)
        )

    def test_missing_lat_returns_none(self):
        self.assertIsNone(fd._parse_coord({"lon": 29.0}))

    def test_missing_lon_returns_none(self):
        self.assertIsNone(fd._parse_coord({"lat": 41.0}))

    def test_non_numeric_returns_none(self):
        self.assertIsNone(fd._parse_coord({"lat": "abc", "lon": "xyz"}))

    def test_empty_dict_returns_none(self):
        self.assertIsNone(fd._parse_coord({}))


# ─── _load_specialty_facility_map ────────────────────────────────────


class LoadSpecialtyMapTests(unittest.TestCase):
    """The JSON map ships in `config/specialty_facility_map.json`; the
    loader must produce a {str: [str]} dict regardless of minor shape
    drift."""

    def setUp(self):
        # lru_cache caches across tests; clear to re-exercise the loader.
        fd._load_specialty_facility_map.cache_clear()

    def test_loads_known_specialties(self):
        m = fd._load_specialty_facility_map()
        self.assertIn("cardiology", m)
        self.assertIn("ent", m)
        self.assertIsInstance(m["cardiology"], list)
        for tag in m["cardiology"]:
            self.assertIsInstance(tag, str)

    def test_returns_empty_on_missing_file(self):
        # Simulate a deployment that forgot to ship the JSON.
        fd._load_specialty_facility_map.cache_clear()
        with patch.object(fd.Path, "open", side_effect=FileNotFoundError("x")):
            self.assertEqual(fd._load_specialty_facility_map(), {})
        fd._load_specialty_facility_map.cache_clear()


# ─── _query_nominatim ────────────────────────────────────────────────


class QueryNominatimTests(unittest.TestCase):
    """HTTP wrapper around Nominatim. On network failure / 5xx / JSON
    parse error, the function logs and returns `(empty_list, True)`
    so callers know to bail rather than retry forever."""

    def test_happy_path_returns_rows_and_not_failed(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = [{"name": "A"}, {"name": "B"}]
        resp.raise_for_status.return_value = None
        client = MagicMock()
        client.get.return_value = resp

        rows, failed = fd._query_nominatim(client, "istanbul", limit=2)
        self.assertEqual(rows, [{"name": "A"}, {"name": "B"}])
        self.assertFalse(failed)

    def test_non_list_payload_treated_as_empty(self):
        # Nominatim returning a dict (e.g. error response) must not
        # raise an "iter on dict keys" error downstream.
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"error": "invalid query"}
        resp.raise_for_status.return_value = None
        client = MagicMock()
        client.get.return_value = resp

        rows, failed = fd._query_nominatim(client, "x", limit=1)
        self.assertEqual(rows, [])
        self.assertFalse(failed)

    def test_http_5xx_sets_query_failed_true(self):
        resp = MagicMock()
        resp.raise_for_status.side_effect = RuntimeError("503")
        client = MagicMock()
        client.get.return_value = resp

        rows, failed = fd._query_nominatim(client, "x", limit=1)
        self.assertEqual(rows, [])
        self.assertTrue(failed)

    def test_connection_error_sets_query_failed_true(self):
        client = MagicMock()
        client.get.side_effect = ConnectionError("DNS fail")

        rows, failed = fd._query_nominatim(client, "x", limit=1)
        self.assertEqual(rows, [])
        self.assertTrue(failed)


# ─── discover_facilities ────────────────────────────────────────────


class DiscoverFacilitiesGateTests(unittest.TestCase):
    """Top-level gates before any HTTP work happens."""

    def test_feature_flag_disabled_returns_empty_quickly(self):
        with patch.object(
            fd.settings, "FACILITY_DISCOVERY_ENABLED", False
        ), patch("app.services.facility_discovery.httpx.Client") as client:
            out = fd.discover_facilities("Istanbul", "cardiology", limit=5)
            self.assertEqual(out["items"], [])
            self.assertEqual(out["specialty_id"], "cardiology")
            self.assertEqual(out["city"], "Istanbul")
            self.assertIn("bilgilendirme", out["disclaimer"].lower())
            # Never calls httpx when the flag is off.
            client.assert_not_called()

    def test_empty_specialty_returns_empty_quickly(self):
        with patch.object(
            fd.settings, "FACILITY_DISCOVERY_ENABLED", True
        ), patch("app.services.facility_discovery.httpx.Client") as client:
            out = fd.discover_facilities("Istanbul", "  ", limit=5)
            self.assertEqual(out["items"], [])
            # Empty specialty_id normalized to empty string.
            self.assertEqual(out["specialty_id"], "")
            client.assert_not_called()

    def test_falsy_city_defaults_to_istanbul(self):
        with patch.object(
            fd.settings, "FACILITY_DISCOVERY_ENABLED", False
        ):
            out = fd.discover_facilities("", "cardiology", limit=5)
            self.assertEqual(out["city"], fd.DEFAULT_CITY)


class DiscoverFacilitiesQueryTests(unittest.TestCase):
    """Tests that actually run the Nominatim query path. httpx is
    mocked to return canned results keyed by query string."""

    def setUp(self):
        self._settings_patch = patch.object(
            fd.settings, "FACILITY_DISCOVERY_ENABLED", True
        )
        self._timeout_patch = patch.object(
            fd.settings, "FACILITY_DISCOVERY_TIMEOUT_SECONDS", 10
        )
        self._settings_patch.start()
        self._timeout_patch.start()
        fd._load_specialty_facility_map.cache_clear()

    def tearDown(self):
        self._settings_patch.stop()
        self._timeout_patch.stop()
        fd._load_specialty_facility_map.cache_clear()

    def test_happy_path_returns_mapped_items(self):
        # City geocode returns Istanbul center; hospital query returns
        # one matching hospital.
        rows = {
            "Istanbul": ([{"lat": "41.0", "lon": "29.0", "display_name": "Istanbul"}], 200),
            "cardiology hospital Istanbul": (
                [
                    {
                        "name": "Acibadem Maslak",
                        "class": "amenity",
                        "type": "hospital",
                        "display_name": "Acibadem Maslak, Sariyer, Istanbul",
                        "lat": "41.10",
                        "lon": "29.01",
                    }
                ],
                200,
            ),
            "cardiology clinic Istanbul": ([], 200),
        }
        ctx, _ = _mock_client_context(rows)
        with patch("app.services.facility_discovery.httpx.Client", return_value=ctx):
            out = fd.discover_facilities("Istanbul", "cardiology", limit=5)
        self.assertEqual(len(out["items"]), 1)
        item = out["items"][0]
        self.assertEqual(item["name"], "Acibadem Maslak")
        self.assertEqual(item["type"], "hospital")
        self.assertEqual(item["lat"], 41.10)
        self.assertEqual(item["lon"], 29.01)
        self.assertIn("distance_km", item)

    def test_lat_lon_skips_city_geocode_step(self):
        # When caller passes lat/lon, we should never call Nominatim for
        # the city lookup — just the tag queries.
        rows = {
            "cardiology hospital Istanbul": (
                [
                    {
                        "name": "Hosp",
                        "type": "hospital",
                        "display_name": "Hosp, Istanbul",
                        "lat": "41.0",
                        "lon": "29.0",
                    }
                ],
                200,
            ),
            "cardiology clinic Istanbul": ([], 200),
        }
        ctx, client = _mock_client_context(rows)
        with patch("app.services.facility_discovery.httpx.Client", return_value=ctx):
            fd.discover_facilities(
                "Istanbul", "cardiology", limit=5, lat=41.0, lon=29.0
            )
        # None of the client.get calls should have had q=="Istanbul".
        queries = [c.kwargs["params"]["q"] for c in client.get.call_args_list]
        self.assertNotIn("Istanbul", queries)

    def test_city_geocode_failure_short_circuits(self):
        # Nominatim unreachable on city lookup → bail with empty items.
        # Simulate by making the city query raise.
        from unittest.mock import MagicMock

        def _get(url, params=None, headers=None):
            raise ConnectionError("DNS fail")

        client = MagicMock()
        client.get.side_effect = _get
        ctx = MagicMock()
        ctx.__enter__.return_value = client
        ctx.__exit__.return_value = False

        with patch("app.services.facility_discovery.httpx.Client", return_value=ctx):
            out = fd.discover_facilities("Istanbul", "cardiology", limit=5)
        self.assertEqual(out["items"], [])
        self.assertIn("bilgilendirme", out["disclaimer"].lower())

    def test_tag_mismatch_rows_are_filtered(self):
        # A row whose class/type/display_name contains none of the tag
        # words (e.g. 'hospital' / 'clinic') must be rejected.
        rows = {
            "Istanbul": ([{"lat": "41.0", "lon": "29.0"}], 200),
            "cardiology hospital Istanbul": (
                [
                    {
                        "name": "Mercan Restoran",
                        "class": "amenity",
                        "type": "restaurant",
                        "display_name": "Mercan Restoran, Beyoglu, Istanbul",
                        "lat": "41.1",
                        "lon": "29.0",
                    },
                    {
                        "name": "Real Medical Center",
                        "class": "amenity",
                        "type": "hospital",
                        "display_name": "Real Medical Center, Istanbul",
                        "lat": "41.2",
                        "lon": "29.1",
                    },
                ],
                200,
            ),
            "cardiology clinic Istanbul": ([], 200),
        }
        ctx, _ = _mock_client_context(rows)
        with patch("app.services.facility_discovery.httpx.Client", return_value=ctx):
            out = fd.discover_facilities("Istanbul", "cardiology", limit=5)
        names = [i["name"] for i in out["items"]]
        self.assertIn("Real Medical Center", names)
        self.assertNotIn("Mercan Restoran", names)

    def test_duplicate_rows_are_deduped_by_name_plus_address(self):
        dup_row = {
            "name": "Acibadem",
            "class": "amenity",
            "type": "hospital",
            "display_name": "Acibadem, Maslak, Istanbul",
            "lat": "41.1",
            "lon": "29.0",
        }
        rows = {
            "Istanbul": ([{"lat": "41.0", "lon": "29.0"}], 200),
            "cardiology hospital Istanbul": ([dup_row, dup_row, dup_row], 200),
            "cardiology clinic Istanbul": ([dup_row], 200),
        }
        ctx, _ = _mock_client_context(rows)
        with patch("app.services.facility_discovery.httpx.Client", return_value=ctx):
            out = fd.discover_facilities("Istanbul", "cardiology", limit=10)
        self.assertEqual(len(out["items"]), 1)

    def test_results_sorted_by_distance_when_coords_present(self):
        rows = {
            "Istanbul": ([{"lat": "41.0", "lon": "29.0"}], 200),
            "cardiology hospital Istanbul": (
                [
                    {
                        "name": "Far",
                        "type": "hospital",
                        "display_name": "Far, Istanbul",
                        "lat": "41.5",  # ~55 km north
                        "lon": "29.0",
                    },
                    {
                        "name": "Near",
                        "type": "hospital",
                        "display_name": "Near, Istanbul",
                        "lat": "41.05",  # ~5 km north
                        "lon": "29.0",
                    },
                ],
                200,
            ),
            "cardiology clinic Istanbul": ([], 200),
        }
        ctx, _ = _mock_client_context(rows)
        with patch("app.services.facility_discovery.httpx.Client", return_value=ctx):
            out = fd.discover_facilities("Istanbul", "cardiology", limit=5)
        self.assertEqual(out["items"][0]["name"], "Near")
        self.assertEqual(out["items"][1]["name"], "Far")
        self.assertLess(
            out["items"][0]["distance_km"], out["items"][1]["distance_km"]
        )

    def test_limit_caps_total_items(self):
        rows_list = [
            {
                "name": f"Hospital {i}",
                "type": "hospital",
                "display_name": f"Hospital {i}, Istanbul",
                "lat": f"41.{i:02d}",
                "lon": "29.0",
            }
            for i in range(10)
        ]
        rows = {
            "Istanbul": ([{"lat": "41.0", "lon": "29.0"}], 200),
            "cardiology hospital Istanbul": (rows_list, 200),
            "cardiology clinic Istanbul": (rows_list, 200),
        }
        ctx, _ = _mock_client_context(rows)
        with patch("app.services.facility_discovery.httpx.Client", return_value=ctx):
            out = fd.discover_facilities("Istanbul", "cardiology", limit=3)
        self.assertEqual(len(out["items"]), 3)

    def test_unknown_specialty_uses_default_tags(self):
        # "unmapped_specialty" is not in specialty_facility_map.json →
        # falls back to DEFAULT_TAGS ("hospital", "clinic"). Issuing
        # both queries means we hit the right fallback tags.
        rows = {
            "Istanbul": ([{"lat": "41.0", "lon": "29.0"}], 200),
            "unmapped_specialty hospital Istanbul": ([], 200),
            "unmapped_specialty clinic Istanbul": ([], 200),
        }
        ctx, client = _mock_client_context(rows)
        with patch("app.services.facility_discovery.httpx.Client", return_value=ctx):
            out = fd.discover_facilities("Istanbul", "unmapped_specialty", limit=5)
        queries = [c.kwargs["params"]["q"] for c in client.get.call_args_list]
        self.assertIn("unmapped_specialty hospital Istanbul", queries)
        self.assertIn("unmapped_specialty clinic Istanbul", queries)
        self.assertEqual(out["items"], [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
