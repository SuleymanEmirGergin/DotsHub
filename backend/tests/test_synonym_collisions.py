"""CI gate: synonyms_tr.json bütünlük ve collision testleri.

Testler:
1. JSON yüklenebilmeli ve şema geçerli olmalı
2. Her canonical unique olmalı (duplicate canonical yok)
3. Her variant unique olmalı — aynı variant iki farklı canonical'a ait olamaz (collision)
4. Variant'lar canonical adıyla çakışmamalı (öz-referans)
5. Her canonical en az 1 variant içermeli
6. Variant'lar boş string içermemeli
7. Longest-first sort kontrolü: multi-word variant'lar önce gelmeli (runtime match koruması)
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from collections import defaultdict


SYNONYMS_PATH = Path(__file__).resolve().parents[1] / "app" / "data" / "synonyms_tr.json"


def _load_synonyms() -> dict:
    with open(SYNONYMS_PATH, encoding="utf-8") as f:
        return json.load(f)


class SynonymSchemaTests(unittest.TestCase):
    """JSON şema ve temel yapı kontrolleri."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_synonyms()
        cls.synonyms: list[dict] = cls.data["synonyms"]

    def test_file_loads(self):
        self.assertIsInstance(self.data, dict)
        self.assertIn("synonyms", self.data)

    def test_required_fields(self):
        for entry in self.synonyms:
            with self.subTest(canonical=entry.get("canonical")):
                self.assertIn("canonical", entry, "canonical alanı eksik")
                self.assertIn("type", entry, "type alanı eksik")
                self.assertIn("variants_tr", entry, "variants_tr alanı eksik")
                self.assertIsInstance(entry["variants_tr"], list, "variants_tr liste olmalı")

    def test_valid_types(self):
        valid_types = {"symptom", "red_flag"}
        for entry in self.synonyms:
            with self.subTest(canonical=entry.get("canonical")):
                self.assertIn(
                    entry.get("type"),
                    valid_types,
                    f"Geçersiz type '{entry.get('type')}' — beklenen: {valid_types}",
                )

    def test_at_least_one_variant(self):
        for entry in self.synonyms:
            with self.subTest(canonical=entry["canonical"]):
                self.assertGreater(
                    len(entry["variants_tr"]),
                    0,
                    f"'{entry['canonical']}' canonical'ı hiç variant içermiyor",
                )

    def test_no_empty_variants(self):
        for entry in self.synonyms:
            for variant in entry["variants_tr"]:
                with self.subTest(canonical=entry["canonical"], variant=variant):
                    self.assertTrue(
                        variant.strip(),
                        f"'{entry['canonical']}' içinde boş variant: '{variant}'",
                    )


class SynonymUniquenessTests(unittest.TestCase):
    """Duplicate ve collision kontrolleri — bu testler CI gate'tir."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_synonyms()
        cls.synonyms: list[dict] = cls.data["synonyms"]

    def test_no_duplicate_canonicals(self):
        """Aynı canonical adı iki kez tanımlanamaz."""
        seen: dict[str, int] = {}
        duplicates = []
        for i, entry in enumerate(self.synonyms):
            canon = entry["canonical"].strip().lower()
            if canon in seen:
                duplicates.append(
                    f"'{entry['canonical']}' satır {seen[canon]} ve {i} içinde duplicate"
                )
            else:
                seen[canon] = i
        self.assertFalse(
            duplicates,
            "Duplicate canonical'lar tespit edildi:\n" + "\n".join(duplicates),
        )

    def test_no_variant_collisions(self):
        """Aynı variant string iki farklı canonical'a ait olamaz.

        Bu test A7 variant expansion için CI gate'tir.
        Bir variant collision bulunursa yeni variant eklenmez — önce çakışma giderilir.
        """
        variant_to_canonicals: dict[str, list[str]] = defaultdict(list)
        for entry in self.synonyms:
            canon = entry["canonical"]
            for variant in entry["variants_tr"]:
                key = variant.strip().lower()
                variant_to_canonicals[key].append(canon)

        collisions = {
            v: canons
            for v, canons in variant_to_canonicals.items()
            if len(canons) > 1
        }

        if collisions:
            lines = []
            for variant, canons in sorted(collisions.items()):
                lines.append(f"  '{variant}' → {canons}")
            self.fail(
                f"{len(collisions)} variant collision tespit edildi:\n" + "\n".join(lines)
            )

    def test_variants_dont_equal_canonical(self):
        """Variant, kendi canonical'ıyla birebir eşleşmemeli (öz-referans)."""
        problems = []
        for entry in self.synonyms:
            canon_lower = entry["canonical"].strip().lower()
            for variant in entry["variants_tr"]:
                if variant.strip().lower() == canon_lower:
                    problems.append(
                        f"'{entry['canonical']}' canonical'ı kendi adını variant olarak içeriyor"
                    )
        self.assertFalse(
            problems,
            "Öz-referans variant'lar:\n" + "\n".join(problems),
        )

    def test_no_cross_canonical_variant_substring(self):
        """Bir canonical'ın variant'ı başka bir canonical adının tam substring'i olmamalı
        (örn. 'ağrı' → birden fazla canonical'ı gölgeleyebilir).

        Bu test WARNING üretir, FAIL değil — tam collision değil, öncelik riski.
        Sadece tam eşleşme (==) kontrol edilir, substring değil.
        """
        canonical_names = {e["canonical"].strip().lower() for e in self.synonyms}
        warnings = []
        for entry in self.synonyms:
            for variant in entry["variants_tr"]:
                v = variant.strip().lower()
                if v in canonical_names and v != entry["canonical"].strip().lower():
                    warnings.append(
                        f"'{variant}' (in '{entry['canonical']}') "
                        f"başka bir canonical adıyla çakışıyor"
                    )
        # Sadece warning — test fail etmez ama output'a yazar
        if warnings:
            import warnings as w
            w.warn(
                "Cross-canonical variant/canonical name çakışması:\n"
                + "\n".join(warnings),
                UserWarning,
                stacklevel=2,
            )


class SynonymLongestFirstTests(unittest.TestCase):
    """Longest-first match koruması — çok kelimeli variant'lar önce gelmeli."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_synonyms()
        cls.synonyms: list[dict] = cls.data["synonyms"]

    def test_multiword_variants_before_single_word(self):
        """Her canonical içinde çok kelimeli variant'lar tek kelimeli olanlardan önce gelmeli.

        Runtime'da longest-first match uygulanıyorsa bu sıra kritik değil,
        ama JSON'un bu sırayı koruması önerilen pratiktir.
        """
        violations = []
        for entry in self.synonyms:
            variants = entry["variants_tr"]
            last_multi_idx = -1
            first_single_idx = len(variants)

            for i, v in enumerate(variants):
                word_count = len(v.strip().split())
                if word_count > 1:
                    last_multi_idx = i
                elif word_count == 1:
                    if first_single_idx == len(variants):
                        first_single_idx = i

            if last_multi_idx > first_single_idx and first_single_idx != len(variants):
                violations.append(
                    f"'{entry['canonical']}': tek kelimeli variant (idx={first_single_idx}) "
                    f"çok kelimeli variant'tan (idx={last_multi_idx}) önce geliyor"
                )

        # Soft uyarı — CI'ı kırmaz, ama dikkat çeker
        if violations:
            import warnings as w
            w.warn(
                "Longest-first sırası ihlali (soft):\n" + "\n".join(violations),
                UserWarning,
                stacklevel=2,
            )


class SynonymCoverageTests(unittest.TestCase):
    """Kapsama metrikleri — sayısal eşikler."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_synonyms()
        cls.synonyms: list[dict] = cls.data["synonyms"]

    def test_total_canonical_count(self):
        """Stream A tamamlandığında en az 32 canonical olmalı."""
        self.assertGreaterEqual(
            len(self.synonyms),
            32,
            f"Beklenen ≥32 canonical, mevcut: {len(self.synonyms)}",
        )

    def test_average_variant_count(self):
        """Ortalama variant sayısı ≥4 olmalı (A7 hedefi: 15-25, asgari eşik 4)."""
        total_variants = sum(len(e["variants_tr"]) for e in self.synonyms)
        avg = total_variants / len(self.synonyms) if self.synonyms else 0
        self.assertGreaterEqual(
            avg,
            4.0,
            f"Ortalama variant sayısı düşük: {avg:.1f} (beklenen ≥4.0)",
        )

    def test_no_canonical_below_minimum(self):
        """Hiçbir canonical 1 variant'tan az içermemeli."""
        below_min = [
            e["canonical"]
            for e in self.synonyms
            if len(e["variants_tr"]) < 1
        ]
        self.assertFalse(
            below_min,
            f"Hiç variant'ı olmayan canonical'lar: {below_min}",
        )

    def test_red_flag_canonicals_exist(self):
        """En az 1 red_flag tipinde canonical olmalı."""
        red_flags = [e for e in self.synonyms if e.get("type") == "red_flag"]
        self.assertGreater(
            len(red_flags),
            0,
            "Hiç red_flag tipinde canonical yok",
        )
