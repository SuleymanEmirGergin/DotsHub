"""Deterministic canonical extraction from Turkish free text.

Features:
  - Phrase-first matching (longer phrases have priority)
  - Word-boundary aware (regex), with Turkish suffix tolerance at the
    trailing edge of each phrase (handles possessive, locative, ablative,
    and other agglutinative suffixes the user typically attaches).
  - Simple negation window (e.g. "ateş yok" → skip)
  - Works with the actual synonyms_tr.json array format

Adapted to the existing synonyms format:
  {
    "synonyms": [
      { "canonical": "baş ağrısı", "variants_tr": ["başım ağrıyor", ...] },
      ...
    ]
  }
"""

from __future__ import annotations
import re
from typing import Any, Dict, List, Set, Tuple

# Turkish-aware lowercase
TR_LOWER_MAP = str.maketrans({"I": "ı", "İ": "i"})

# Default negation tokens
DEFAULT_NEGATIONS = ["yok", "değil", "hayır", "olmuyor", "olmadı", "değilim"]

# Turkish trailing-suffix tolerance for phrase-end matching.
#
# Why: Turkish is agglutinative — case, possessive, and derivational
# suffixes attach directly to the word stem with no separator. A bare
# `\b` boundary at the end of a canonical phrase fails on natural user
# input like "sağ alt karın bölgemde keskin ağrı": the variant
# "sağ alt karın bölgem" ends at `m` (a `\w`) and the next char `d` is
# also `\w`, so `\b` doesn't fire and the canonical isn't extracted.
#
# Fix: allow an optional Turkish suffix between the phrase end and the
# real word boundary. List is ordered longest-first to make the regex
# engine's backtracking fast — though `(?:…)?\b` is correct regardless
# of order because the engine retries shorter alternatives until `\b`
# succeeds.
#
# Coverage: case markers (loc/abl/dat/acc/gen/ins), possessives (1sg/
# 2sg/3sg + plural), poss+case combos with the 1sg-`m`/3sg-`n` buffer,
# the relative `-ki`, and the most common verbal tense markers (-du,
# -muş) so variants like "ağrıyor" still hit when the user types
# "ağrıyordu".
#
# Regression coverage: tests/test_canonical_extract_turkish_morphology.py
# pins the suffix forms we promise to handle and the idiom-negative
# cases ("karın doyurmak") we promise NOT to match.
_TR_SUFFIX_PATTERN = (
    r"(?:"
    # 6–8 chars: 3sg poss + case + relative-ki, plural + case
    r"sındaki|sindeki|sundaki|sündeki"
    r"|sından|sinden|sundan|sünden"
    r"|larından|lerinden|larında|lerinde"
    r"|lardaki|lerdeki"
    r"|"
    # 5 chars: 3sg poss + case (with vowel), 1sg poss + case (with vowel)
    r"sının|sinin|sunun|sünün"
    r"|sında|sinde|sunda|sünde"
    r"|ından|inden|undan|ünden"
    r"|ımdan|imden|umdan|ümden"
    r"|ndaki|ndeki|mdaki|mdeki"
    r"|"
    # 4 chars: poss+case, plural, locative+ki
    r"daki|deki|taki|teki"
    r"|ları|leri|ların|lerin|larda|lerde|lardan|lerden"
    r"|ında|inde|unda|ünde"
    r"|ımda|imde|umda|ümde"
    r"|ndan|nden|mdan|mden"
    r"|ımız|imiz|umuz|ümüz"
    r"|nızı|nızda|nızdan"
    r"|"
    # 3 chars: short poss+case combos, genitive, plural, ablative, reported past
    r"nda|nde|mda|mde"
    r"|nın|nin|nun|nün"
    r"|dan|den|tan|ten"
    r"|sın|sin|sun|sün"
    r"|lar|ler"
    r"|muş|mış|müş"
    r"|ile"
    # 1sg poss + acc/dat (ımı, imi, umu, ümü / ıma, ime, uma, üme)
    r"|ımı|imi|umu|ümü|ıma|ime|uma|üme"
    # 2sg poss + acc/dat (ını, ini, unu, ünü / ına, ine, una, üne)
    r"|ını|ini|unu|ünü|ına|ine|una|üne"
    r"|"
    # 2 chars: bare case markers, possessives, common verbal suffixes.
    # Note: `ım|im|um|üm` is 1sg poss after consonant-final stems
    # ("ateş" + "im" = "ateşim"); for vowel-final stems the 1-char
    # `m` below applies ("ağrı" + "m" = "ağrım").
    r"da|de|ta|te"
    r"|ya|ye|la|le"
    r"|yı|yi|yu|yü"
    r"|mı|mi|mu|mü"
    r"|nı|ni|nu|nü"
    r"|sı|si|su|sü"
    r"|ım|im|um|üm"  # 1sg poss for consonant-final stems
    r"|ın|in|un|ün"  # 2sg poss / genitive for consonant-final stems
    r"|du|dı|tu|tü|di"
    r"|ki|li|lı|lu|lü"
    r"|na|ne"  # 3sg poss + dative buffered (yan + ı + n + a = "yanına")
    r"|"
    # 1 char: minimal poss/dative
    r"m|n|ı|i|u|ü|a|e"
    r")?"
)


def tr_lower(s: str) -> str:
    return s.translate(TR_LOWER_MAP).lower()


def normalize_text_tr(text: str) -> str:
    t = tr_lower(text)
    t = re.sub(r"[^\w\sçğıöşü]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


# Pattern cache for build_synonym_patterns.
#
# Why cache: the orchestrator passes the same `runtime.synonyms` dict
# on every turn, and `extract_canonicals_tr` is called ≥4 times per
# turn. Without caching, we recompile 150+ patterns × ~700-char
# alternation on every call — which broke `test_local_p95_response_time_smoke`.
#
# Keyed by id() with an identity check on hit: we store both the dict
# object and its compiled patterns, then verify `cached_obj is current_obj`
# before returning. This guards against the realistic CPython behavior
# where a short-lived test dict gets GC'd and a fresh dict is allocated
# at the same memory address — without the identity check, the new dict
# would inherit the old dict's stale patterns. The accompanying tests
# in test_canonical_extract_unit.py exercise this exact pattern (each
# subtest constructs a brand-new dict literal), and silently failed
# with a naive id-only cache.
#
# Memory: production has 1 long-lived dict → 1 cache entry. Test runs
# can accumulate ~hundreds of entries but each pattern set is small,
# so the bound is acceptable for the test session lifetime.
_PATTERN_CACHE: Dict[int, Tuple[Any, List[Tuple[str, "re.Pattern[str]"]]]] = {}


def build_synonym_patterns(
    synonyms_json: Dict[str, Any],
) -> List[Tuple[str, "re.Pattern[str]"]]:
    """Build (canonical, compiled_pattern) list sorted by longest phrase first.

    Memoized to avoid re-compiling the suffix-tolerant regex set on every
    extract call. See `_PATTERN_CACHE` docstring above for the identity-
    check rationale.
    """
    cache_key = id(synonyms_json)
    cached = _PATTERN_CACHE.get(cache_key)
    if cached is not None and cached[0] is synonyms_json:
        return cached[1]

    items: List[Tuple[str, str]] = []

    for entry in synonyms_json.get("synonyms", []):
        canonical = normalize_text_tr(entry.get("canonical", ""))
        if not canonical:
            continue
        for v in entry.get("variants_tr", []):
            vn = normalize_text_tr(v)
            if vn:
                items.append((canonical, vn))
        # Also match the canonical itself
        items.append((canonical, canonical))

    # Longer phrases first (more specific)
    items.sort(key=lambda x: len(x[1]), reverse=True)

    # De-duplicate
    seen: Set[str] = set()
    patterns: List[Tuple[str, "re.Pattern[str]"]] = []
    for canonical, phrase in items:
        key = f"{canonical}|{phrase}"
        if key in seen:
            continue
        seen.add(key)
        # Trailing `_TR_SUFFIX_PATTERN` lets natural Turkish suffixes
        # (locative, ablative, possessive, etc.) attach to the phrase's
        # last token without breaking the match. See module docstring +
        # tests/test_canonical_extract_turkish_morphology.py.
        pat = re.compile(
            rf"\b{re.escape(phrase)}{_TR_SUFFIX_PATTERN}\b",
            flags=re.UNICODE,
        )
        patterns.append((canonical, pat))

    _PATTERN_CACHE[cache_key] = (synonyms_json, patterns)
    return patterns


def is_negated(
    text_norm: str,
    start_idx: int,
    negations: List[str],
    window: int = 18,
) -> bool:
    """Check small window before match position for negation tokens."""
    left = text_norm[max(0, start_idx - window) : start_idx]
    for n in negations:
        nn = normalize_text_tr(n)
        if nn and re.search(rf"\b{re.escape(nn)}\b", left):
            return True
    return False


def extract_canonicals_tr(
    text_tr: str,
    answers: Dict[str, str],
    synonyms_json: Dict[str, Any],
) -> List[str]:
    """
    Deterministic canonical extraction from:
      - free text (text_tr)
      - structured answers (answer keys as canonicals)

    Returns unique canonicals, sorted for stability.
    """
    text_norm = normalize_text_tr(text_tr)
    negations = DEFAULT_NEGATIONS

    patterns = build_synonym_patterns(synonyms_json)

    found: Set[str] = set()

    # 1) Extract from free text
    for canonical, pat in patterns:
        for m in pat.finditer(text_norm):
            if is_negated(text_norm, m.start(), negations):
                continue
            found.add(canonical)
            break  # one match per canonical is enough

    # 2) Add answer keys as canonicals
    for k in (answers or {}):
        kn = normalize_text_tr(k)
        if kn:
            found.add(kn)

    return sorted(found)
