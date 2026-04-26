"""Tests for the itinerary engine + POST /v1/quote/itinerary route.

Engine tests are pure-function (no FastAPI). Route tests use TestClient
and exercise the full pipeline (validation → fit-to-travel → engine →
envelope shaping).
"""
from __future__ import annotations

import unittest
from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.services import itinerary_engine


# ─── Engine ──────────────────────────────────────────────────────────


class ItineraryEngineTests(unittest.TestCase):
    def test_unknown_procedure_returns_none(self):
        out = itinerary_engine.generate(
            "nope", "clinic_istanbul_aesthetics_one", date(2026, 5, 15), "tr-TR"
        )
        self.assertIsNone(out)

    def test_unknown_clinic_returns_none(self):
        out = itinerary_engine.generate(
            "fue_hair_transplant", "clinic_does_not_exist",
            date(2026, 5, 15), "tr-TR",
        )
        self.assertIsNone(out)

    def test_clinic_does_not_offer_procedure_returns_none(self):
        # Ankara cardiac clinic doesn't offer LASIK.
        out = itinerary_engine.generate(
            "lasik", "clinic_ankara_cardiac", date(2026, 5, 15), "tr-TR"
        )
        self.assertIsNone(out)

    def test_hair_template_produces_4_day_plan(self):
        out = itinerary_engine.generate(
            "fue_hair_transplant", "clinic_istanbul_aesthetics_one",
            date(2026, 5, 15), "tr-TR",
        )
        self.assertIsNotNone(out)
        # Hair template ends at day 3 → 4 calendar days inclusive.
        self.assertEqual(out.total_days, 4)
        self.assertEqual(out.arrival_date_iso, "2026-05-15")
        self.assertEqual(out.departure_date_iso, "2026-05-18")
        # First activity must be airport pickup.
        self.assertEqual(out.items[0].activity_id, "arrival_transfer")

    def test_items_sorted_by_day_offset(self):
        out = itinerary_engine.generate(
            "rhinoplasty", "clinic_istanbul_full_service",
            date(2026, 5, 15), "tr-TR",
        )
        offsets = [item.day_offset for item in out.items]
        self.assertEqual(offsets, sorted(offsets))

    def test_locale_changes_activity_labels(self):
        out_tr = itinerary_engine.generate(
            "lasik", "clinic_izmir_eye_center", date(2026, 5, 15), "tr-TR"
        )
        out_en = itinerary_engine.generate(
            "lasik", "clinic_izmir_eye_center", date(2026, 5, 15), "en-US"
        )
        # Same activity ids, different localised labels.
        self.assertEqual(
            [i.activity_id for i in out_tr.items],
            [i.activity_id for i in out_en.items],
        )
        self.assertNotEqual(out_tr.items[0].label, out_en.items[0].label)
        self.assertIn("Airport", out_en.items[0].label)
        self.assertIn("Havalimanı", out_tr.items[0].label)

    def test_dates_advance_with_day_offset(self):
        out = itinerary_engine.generate(
            "fue_hair_transplant", "clinic_istanbul_aesthetics_one",
            date(2026, 5, 15), "tr-TR",
        )
        # Day 1 item must be 2026-05-16.
        day1 = next(i for i in out.items if i.day_offset == 1)
        self.assertEqual(day1.date_iso, "2026-05-16")

    def test_min_stay_extends_template_when_template_shorter(self):
        # Procedure metadata may require a longer stay than the
        # template's last day_offset (e.g. clinic insists on extra
        # recovery nights). Engine takes the max.
        out = itinerary_engine.generate(
            "ivf", "clinic_istanbul_fertility", date(2026, 5, 15), "tr-TR"
        )
        # IVF template ends at day 17 → 18 calendar days.
        self.assertGreaterEqual(out.total_days, 18)


# ─── Route ───────────────────────────────────────────────────────────


def _post(client, body, headers=None):
    return client.post("/v1/quote/itinerary", json=body, headers=headers or {})


class ItineraryRouteTests(unittest.TestCase):
    # setUp removed — autouse fixture in conftest.py.

    def test_happy_path_returns_itinerary_envelope(self):
        with TestClient(app) as client:
            r = _post(client, {
                "procedure_id": "fue_hair_transplant",
                "clinic_id": "clinic_istanbul_aesthetics_one",
                "arrival_date": "2026-05-15",
                "profile": {"age": 35},
                "locale": "tr-TR",
            })
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["type"], "ITINERARY")
        p = body["payload"]
        self.assertGreater(len(p["items"]), 0)
        self.assertEqual(p["arrival_date"], "2026-05-15")
        self.assertEqual(p["procedure_id"], "fue_hair_transplant")
        self.assertEqual(p["fit_to_travel_warnings"], [])

    def test_unknown_procedure_returns_error(self):
        with TestClient(app) as client:
            r = _post(client, {
                "procedure_id": "not_real",
                "clinic_id": "clinic_istanbul_aesthetics_one",
                "arrival_date": "2026-05-15",
            })
        self.assertEqual(r.json()["payload"]["code"], "PROCEDURE_UNKNOWN")

    def test_clinic_procedure_mismatch_returns_error(self):
        with TestClient(app) as client:
            r = _post(client, {
                "procedure_id": "lasik",
                "clinic_id": "clinic_ankara_cardiac",
                "arrival_date": "2026-05-15",
            })
        self.assertEqual(
            r.json()["payload"]["code"], "CLINIC_PROCEDURE_MISMATCH"
        )

    def test_invalid_arrival_date_returns_error(self):
        with TestClient(app) as client:
            r = _post(client, {
                "procedure_id": "lasik",
                "clinic_id": "clinic_izmir_eye_center",
                "arrival_date": "tomorrow",
            })
        self.assertEqual(
            r.json()["payload"]["code"], "ARRIVAL_DATE_INVALID"
        )

    def test_fit_to_travel_block_returns_emergency_no_itinerary(self):
        with TestClient(app) as client:
            r = _post(client, {
                "procedure_id": "cabg",
                "clinic_id": "clinic_ankara_cardiac",
                "arrival_date": "2026-05-15",
                "profile": {"unstable_angina": True},
            })
        body = r.json()
        self.assertEqual(body["type"], "EMERGENCY")
        self.assertNotIn("items", body["payload"])
        self.assertTrue(any(
            w["severity"] == "block"
            for w in body["payload"]["fit_to_travel_warnings"]
        ))

    def test_idempotency_repeat_returns_cached(self):
        body = {
            "procedure_id": "fue_hair_transplant",
            "clinic_id": "clinic_istanbul_aesthetics_one",
            "arrival_date": "2026-05-15",
            "profile": {},
            "locale": "tr-TR",
        }
        with TestClient(app) as client:
            r1 = _post(client, body, headers={"Idempotency-Key": "k-itin-1"})
            r2 = _post(client, body, headers={"Idempotency-Key": "k-itin-1"})
        self.assertEqual(r1.json(), r2.json())

    def test_locale_de_localises_activity_labels(self):
        with TestClient(app) as client:
            r = _post(client, {
                "procedure_id": "fue_hair_transplant",
                "clinic_id": "clinic_istanbul_aesthetics_one",
                "arrival_date": "2026-05-15",
                "profile": {},
                "locale": "de-DE",
            })
        labels = [i["label"] for i in r.json()["payload"]["items"]]
        # First activity must be the German pickup label.
        self.assertIn("Flughafen", labels[0])


if __name__ == "__main__":
    unittest.main()
