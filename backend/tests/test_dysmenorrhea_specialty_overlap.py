"""Pin the dismenore vs ortho/uro tie-breaking for menstrual context.

Before this audit, ``orthopedics_rheum`` and ``urology_internal`` both
listed ``bel ağrısı`` as a positive keyword and only ``urology_internal``
had any menstrual-cue negatives — and even those were too specific to
fire (``adet dönemi kramp`` requires the exact substring). Result: any
dysmenorrhea paraphrase that mentioned back pain tied or beat
``obgyn`` because the ``bel ağrısı`` hit on ortho/uro was uncontested.

Fix audit:
  - ``orthopedics_rheum`` now declares ``adet dönemi``, ``adet ağrısı``,
    ``dismenore``, ``regl``, ``endometriyoz`` as negatives.
  - ``urology_internal`` adds ``adet dönemi``, ``adet ağrısı``,
    ``dismenore``, ``regl`` (plus the existing ``adet dönemi kramp``,
    ``endometriyoz``, ``gebeyim``).
  - ``obgyn`` adds ``adet dönemi`` as a positive keyword so paraphrase
    scenarios without a literal ``dismenore`` variant can still surface
    obgyn (e.g. p3 — "her adet döneminde o kadar şiddetli kramp").

These tests run scoring directly so they fail fast if the negative
list is whittled down or the obgyn keyword is removed. End-to-end
real-corpus coverage stays in ``test_real_corpus``.
"""
from __future__ import annotations

import unittest

from app.runtime import load_runtime
from app.scoring_v2 import score_specialties_deterministic_v2


class DysmenorrheaSpecialtyOverlapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = load_runtime(data_dir="app/data")
        cls.syn = cls.runtime.synonyms
        cls.sk = cls.runtime.specialty_keywords

    def _top(self, text: str) -> str:
        out = score_specialties_deterministic_v2(text, {}, self.syn, self.sk)
        return out["ranked"][0]["id"]

    # ─── dysmenorrhea paraphrases must route to obgyn ─────────────

    def test_dysmenorrhea_p1_obgyn_wins(self):
        text = (
            "Her adet dönemimde çok şiddetli kramp ve bel ağrım oluyor, "
            "okula gidemiyorum."
        )
        self.assertEqual(self._top(text), "obgyn")

    def test_dysmenorrhea_p2_obgyn_wins(self):
        text = (
            "Adet dönemlerimde karnıma bıçak saplanıyormuş gibi ağrı oluyor, "
            "bel ağrısı da eşlik ediyor."
        )
        self.assertEqual(self._top(text), "obgyn")

    def test_dysmenorrhea_p3_obgyn_wins(self):
        # The hardest case: no dismenore variant matches because the
        # phrasing differs from existing variants. obgyn must still win
        # via the bare "adet dönemi" keyword and ortho/uro must drop
        # below zero from their menstrual-cue negatives.
        text = (
            "Her adet döneminde o kadar şiddetli kramp oluyor ki işe "
            "gidemiyorum, bel ağrım da eşlik ediyor."
        )
        self.assertEqual(self._top(text), "obgyn")

    # ─── menstrual-cue negatives must fire on competitors ─────────

    def test_ortho_negative_fires_on_adet_donemi(self):
        out = score_specialties_deterministic_v2(
            "Her adet döneminde bel ağrım var", {}, self.syn, self.sk
        )
        ortho_negs = out["debug"]["orthopedics_rheum"]["negatives"]
        self.assertIn("adet dönemi", ortho_negs)

    def test_uro_negative_fires_on_adet_donemi(self):
        out = score_specialties_deterministic_v2(
            "Her adet döneminde bel ağrım var", {}, self.syn, self.sk
        )
        uro_negs = out["debug"]["urology_internal"]["negatives"]
        self.assertIn("adet dönemi", uro_negs)

    # ─── controls: pure ortho / uro must NOT regress ──────────────

    def test_pure_ortho_no_menstrual_cue_unaffected(self):
        # No menstrual context — ortho's menstrual negatives must NOT
        # fire on plain joint complaints. (Absent debug entry == zero
        # negatives, also acceptable.)
        out = score_specialties_deterministic_v2(
            "diz ağrım var, eklemlerim tutuk", {}, self.syn, self.sk
        )
        ortho_negs = out["debug"].get("orthopedics_rheum", {}).get(
            "negatives", {}
        )
        for forbidden in ("adet dönemi", "dismenore", "regl"):
            self.assertNotIn(forbidden, ortho_negs)

    def test_pure_uro_no_menstrual_cue_unaffected(self):
        out = score_specialties_deterministic_v2(
            "idrar yaparken yanma var, sık tuvalete çıkıyorum",
            {},
            self.syn,
            self.sk,
        )
        uro_negs = out["debug"].get("urology_internal", {}).get(
            "negatives", {}
        )
        for forbidden in ("adet dönemi", "dismenore", "regl"):
            self.assertNotIn(forbidden, uro_negs)


if __name__ == "__main__":
    unittest.main()
