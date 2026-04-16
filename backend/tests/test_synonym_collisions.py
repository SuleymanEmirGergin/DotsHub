"""Collision guards for ``app/data/synonyms_tr.json``.

Purpose
-------
The matcher in ``app.canonical_extract`` adds *every* canonical whose variant
(or the canonical itself) matches the normalized input text. If the same
variant string (after TR normalization) appears under two different
canonicals, the user silently gets both canonicals tagged. Expansion
sessions (A2–A6) could introduce this class of bug by accident — this test
file prevents that at CI level.

What this file covers:
  1. Data hygiene   — canonical labels unique, variants well-formed
  2. Collision    — no variant is shared across canonicals
  3. Expansion guard — none of the A1-planned canonicals in
                       ``backend/scripts/coverage_expected.json`` collide
                       with existing variants
  4. Matcher sanity — longest-first ordering survives, negation works,
                      deterministic output

Invariants enforced:
  - Top-level JSON has ``synonyms`` list
  - Each entry has non-empty ``canonical`` and list-type ``variants_tr``
  - ``canonical`` values are unique (after TR normalization)
  - A variant (normalized) is NOT used in two different canonicals
  - A canonical's label (normalized) is NOT used as a variant of a
    different canonical
  - ``variants_tr`` contains no duplicates, no empty strings, no non-strings
  - The expected A1 canonicals do not clash with existing variants
  - ``extract_canonicals_tr`` is deterministic and honors negation
"""

from __future__ import annotations

import json
import unittest
from collections import defaultdict
from pathlib import Path

from app.canonical_extract import (
    build_synonym_patterns,
    extract_canonicals_tr,
    normalize_text_tr,
)

# ── Paths ────────────────────────────────────────────────────────────────────

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_SYNONYMS_PATH = _BACKEND_ROOT / "app" / "data" / "synonyms_tr.json"
_EXPECTED_PATH = _BACKEND_ROOT / "scripts" / "coverage_expected.json"


def _load_synonyms() -> dict:
    with open(_SYNONYMS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_expected_canonicals() -> list[str]:
    """Flatten ``expected_canonicals_by_specialty`` into one list."""
    if not _EXPECTED_PATH.exists():
        return []
    with open(_EXPECTED_PATH, encoding="utf-8") as f:
        data = json.load(f)
    bucket = data.get("expected_canonicals_by_specialty", {})
    out: list[str] = []
    for key, val in bucket.items():
        if key.startswith("_"):
            continue
        if isinstance(val, list):
            out.extend(str(x) for x in val)
    return out


# ── 1. Data hygiene ───────────────────────────────────────────────────────

class DataHygieneTests(unittest.TestCase):
    """Baseline structural invariants over synonyms_tr.json."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.data = _load_synonyms()
        cls.entries = cls.data.get("synonyms", [])

    def test_top_level_has_synonyms_list(self):
        self.assertIsInstance(self.data.get("synonyms"), list,
                              "synonyms_tr.json must have a top-level 'synonyms' list")
        self.assertGreater(len(self.entries), 0,
                           "synonyms list cannot be empty")

    def test_every_entry_has_non_empty_canonical_string(self):
        bad = []
        for i, entry in enumerate(self.entries):
            c = entry.get("canonical")
            if not isinstance(c, str) or not c.strip():
                bad.append((i, entry))
        self.assertEqual(bad, [],
                         f"Entries with invalid canonical: {bad!r}")

    def test_every_entry_has_list_variants(self):
        bad = []
        for i, entry in enumerate(self.entries):
            v = entry.get("variants_tr")
            if not isinstance(v, list):
                bad.append((i, entry.get("canonical"), type(v).__name__))
        self.assertEqual(bad, [],
                         f"Entries with non-list variants_tr: {bad!r}")

    def test_all_variants_are_non_empty_strings(self):
        bad = []
        for entry in self.entries:
            c = entry.get("canonical")
            for j, v in enumerate(entry.get("variants_tr", [])):
                if not isinstance(v, str) or not v.strip():
                    bad.append((c, j, v))
        self.assertEqual(bad, [],
                         f"Variants that are empty/whitespace/non-string: {bad!r}")

    def test_no_duplicate_variants_within_canonical(self):
        """After TR normalization, a canonical cannot repeat the same variant."""
        offenders: list[tuple[str, str]] = []
        for entry in self.entries:
            c = entry.get("canonical")
            seen: set[str] = set()
            for v in entry.get("variants_tr", []):
                vn = normalize_text_tr(v)
                if not vn:
                    continue
                if vn in seen:
                    offenders.append((c, vn))
                else:
                    seen.add(vn)
        self.assertEqual(offenders, [],
                         f"Duplicate variants within a canonical: {offenders!r}")

    def test_type_field_is_valid_when_present(self):
        allowed = {"symptom", "red_flag"}
        bad = []
        for entry in self.entries:
            t = entry.get("type")
            if t is not None and t not in allowed:
                bad.append((entry.get("canonical"), t))
        self.assertEqual(bad, [],
                         f"Entries with unrecognized 'type' field: {bad!r}")


# ── 2. Collision ────────────────────────────────────────────────────────────

class CollisionTests(unittest.TestCase):
    """Ensure no variant (or canonical label) is ambiguously shared."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.data = _load_synonyms()
        cls.entries = cls.data.get("synonyms", [])

    def test_canonical_labels_are_unique_after_normalization(self):
        seen: dict[str, str] = {}
        dupes: list[tuple[str, str]] = []
        for entry in self.entries:
            raw = entry.get("canonical", "")
            norm = normalize_text_tr(raw)
            if norm in seen:
                dupes.append((seen[norm], raw))
            else:
                seen[norm] = raw
        self.assertEqual(dupes, [],
                         f"Canonical label collisions (normalized): {dupes!r}")

    def test_no_variant_is_shared_across_canonicals(self):
        """The key CI guard: a single normalized variant → at most one canonical."""
        variant_owners: dict[str, list[str]] = defaultdict(list)
        for entry in self.entries:
            c = entry.get("canonical", "")
            for v in entry.get("variants_tr", []):
                vn = normalize_text_tr(v)
                if vn:
                    variant_owners[vn].append(c)
        shared = {v: owners for v, owners in variant_owners.items() if len(set(owners)) > 1}
        self.assertEqual(shared, {},
                         f"Variants shared across canonicals (would silently double-tag): {shared!r}")

    def test_canonical_label_not_used_as_variant_of_different_canonical(self):
        """
        If canonical A's label (normalized) appears as a variant of canonical B,
        the matcher will silently tag both whenever A's phrase is in the text.
        """
        labels = {normalize_text_tr(e.get("canonical", "")): e.get("canonical", "")
                  for e in self.entries}
        offenders: list[tuple[str, str]] = []  # (canonical_B, label_of_A)
        for entry in self.entries:
            c = entry.get("canonical", "")
            cn = normalize_text_tr(c)
            for v in entry.get("variants_tr", []):
                vn = normalize_text_tr(v)
                if vn and vn != cn and vn in labels:
                    offenders.append((c, labels[vn]))
        self.assertEqual(offenders, [],
                         f"Canonical label used as variant of another canonical: {offenders!r}")


# ── 3. Expansion guard (A1 coverage_expected.json) ─────────────────────────

class ExpectedCanonicalExpansionGuardTests(unittest.TestCase):
    """
    A1 enumerated 39 canonicals that Stream A will add. Verify that none of
    them would collide with existing variants when merged. This is the gate
    for A2–A6 expansion PRs.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.data = _load_synonyms()
        cls.expected = _load_expected_canonicals()
        cls.existing_variants: dict[str, str] = {}
        for entry in cls.data.get("synonyms", []):
            c = entry.get("canonical", "")
            for v in entry.get("variants_tr", []):
                vn = normalize_text_tr(v)
                if vn:
                    cls.existing_variants[vn] = c

    def test_expected_canonicals_list_not_empty(self):
        self.assertGreater(len(self.expected), 0,
                           "coverage_expected.json must list expected canonicals "
                           "(check expected_canonicals_by_specialty section)")

    def test_no_expected_canonical_collides_with_existing_variant(self):
        """
        If an A1-expected canonical string (normalized) already appears as a
        variant under a *different* canonical, adding it would silently
        double-tag. Flag it so the expansion author can choose: rename,
        relocate the variant, or merge the canonicals.
        """
        hits: list[tuple[str, str]] = []
        for new_c in self.expected:
            nn = normalize_text_tr(new_c)
            if nn in self.existing_variants:
                hits.append((new_c, self.existing_variants[nn]))
        self.assertEqual(hits, [],
                         f"Expected canonicals collide with existing variants "
                         f"(new_canonical -> existing_canonical_owning_it): {hits!r}")


# ── 4. Matcher sanity ──────────────────────────────────────────────────────

class MatcherSanityTests(unittest.TestCase):
    """Runtime behaviour: determinism, negation, pattern ordering."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.data = _load_synonyms()

    def test_extract_canonicals_is_deterministic(self):
        """Same input → identical output over many calls."""
        text = "göğsümde baskı var, soluk alamıyorum, ateşim yükseldi"
        first = extract_canonicals_tr(text, {}, self.data)
        for _ in range(50):
            self.assertEqual(extract_canonicals_tr(text, {}, self.data), first)

    def test_negation_suppresses_match(self):
        """'ateşim yok' must not yield 'ateş'."""
        pos = extract_canonicals_tr("ateşim var", {}, self.data)
        neg = extract_canonicals_tr("ateşim yok", {}, self.data)
        self.assertIn("ateş", pos)
        self.assertNotIn("ateş", neg)

    def test_patterns_sorted_longest_first(self):
        """
        ``build_synonym_patterns`` is the only guarantee we have that longer
        variants are considered before shorter ones. Re-assert it here so a
        future refactor doesn't silently drop the sort.

        We compare *phrase* lengths (not raw pattern-string lengths), because
        ``re.escape`` inserts backslashes for non-alphanumeric characters
        (spaces in particular) which would skew raw-string length comparison.
        """
        import re as _re

        def _phrase_of(pat) -> str:
            s = pat.pattern
            # Strip leading \b and trailing \b (each is 2 chars in the source form)
            if s.startswith(r"\b"):
                s = s[2:]
            if s.endswith(r"\b"):
                s = s[:-2]
            # Reverse re.escape: \X -> X (single-backslash escape for any char)
            return _re.sub(r"\\(.)", r"\1", s)

        patterns = build_synonym_patterns(self.data)
        phrase_lengths = [len(_phrase_of(pat)) for _, pat in patterns]
        self.assertEqual(
            phrase_lengths, sorted(phrase_lengths, reverse=True),
            "Synonym patterns must be sorted by descending phrase length "
            "(longest-first) so more specific variants are preferred.",
        )


if __name__ == "__main__":
    unittest.main()
