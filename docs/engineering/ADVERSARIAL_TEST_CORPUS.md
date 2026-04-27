# Adversarial Test Corpus — Turkish Pre-Triage Inputs

**Owner:** emirgergin21@gmail.com (TriAIge founder)
**Status:** Draft — convert to executable corpus before pilot rollout.
**Audience:** backend engineers, QA, and the founder running demo prep.

## Why this corpus exists

TriAIge's triage envelope has two recurring failure shapes that the
existing unit tests do not catch: (a) emergency rules that key on a
small, hand-curated phrase list missing the exact morphology a real
patient types, and (b) `canonical_extract` patterns that bind too
tightly to one suffix form and silently drop matches on common Turkish
agglutinative variants. Demo-prep validation against
`backend/app/data/demo_scenarios/` (commit `88a533e`) surfaced both
shapes in the same week — a chest-pain emergency phrase that did not
fire a hard-trigger rule, plus a canonical-extract miss caused by the
locative suffix on `karın` (`karnımda`). This document defines a
golden-set corpus structured by failure mode so we can convert each
example into a regression test before the next class of input lands in
front of a real patient. The corpus is the test plan; the code change
is downstream.

References:
- Backend extractor: `backend/app/canonical_extract.py` (regex
  `\b{phrase}\b` against TR-lowercased text).
- Emergency router: `backend/app/emergency_router.py` (substring
  matching with normalized text).
- Demo scenarios that surfaced the bugs:
  `backend/app/data/demo_scenarios/demo_chest_emergency.json`,
  `demo_abdominal.json`.

## Corpus categories

Each category gives 8-15 representative Turkish inputs, the expected
envelope type (`EMERGENCY` / `SAME_DAY` / `QUESTION` / `RESULT`, or a
specific safety-net response), the expected canonicals, and the
failure mode if the system misses.

Severity column legend:
- **CRITICAL**: clinical risk if missed (false negative on emergency,
  misroute of red-flag symptom).
- **HIGH**: routing or canonical regression that visibly degrades the
  consult.
- **MEDIUM**: cosmetic or partial-extract miss; user gets a coherent
  flow but the trace is incomplete.

---

### 1. Vowel elision / harmony variants

Turkish vowel-elision drops the inner vowel of a stem when a possessive
or case suffix attaches: `göğüs` → `göğsüm`, `karın` → `karnım`,
`omuz` → `omzum`. Real users type both the elided and unelided forms;
regex patterns built from one canonical form must match all common
variants.

| Input | Expected envelope | Expected canonicals | Severity |
|-------|-------------------|---------------------|----------|
| `göğsüm sıkışıyor` | EMERGENCY (chest_pain_sob class) | `göğüs ağrısı`, `nefes darlığı` | CRITICAL |
| `göğüsüm sıkışıyor` | EMERGENCY | `göğüs ağrısı` | CRITICAL |
| `karnım çok ağrıyor` | SAME_DAY/QUESTION | `karın ağrısı` | HIGH |
| `karın ağrısı var` | SAME_DAY/QUESTION | `karın ağrısı` | HIGH |
| `koluma vuruyor ağrı` | EMERGENCY (cardiac referral pattern) | `kola yansıyan ağrı`, `göğüs ağrısı` if combined | CRITICAL |
| `kolum ağrıyor` | QUESTION | `kol ağrısı` | MEDIUM |
| `omzum ağrıyor` | QUESTION | `omuz ağrısı` | MEDIUM |
| `omuzum ağrıyor` | QUESTION | `omuz ağrısı` | MEDIUM |
| `gözüm yanıyor` | QUESTION | `göz ağrısı` / `göz yanması` | MEDIUM |
| `gözüme bir şey kaçtı` | QUESTION | `göze yabancı cisim` | HIGH |
| `bağırsaklarım rahatsız` | QUESTION | `karın rahatsızlığı` | MEDIUM |
| `boğazım kazınıyor` | QUESTION | `boğaz ağrısı` | MEDIUM |

**Failure mode if missed:** patient describing classic referred chest
pain (`göğsüm sıkışıyor, sol koluma vuruyor`) is routed to a generic
question flow instead of the emergency envelope. Demo prep already hit
this exact shape.

---

### 2. Possessive + locative / ablative / dative suffix combinations

Patient describes pain location with a noun + possessive + case
suffix: `karın+ım+da` → `karnımda`, `baş+ım+a` → `başıma`. The
extractor's literal-phrase pattern misses unless every combinatorial
form is enumerated, which is impractical. This is the suffix bug class
fixed in commit `88a533e`.

| Input | Expected envelope | Expected canonicals | Severity |
|-------|-------------------|---------------------|----------|
| `karnımda şiddetli ağrı var` | SAME_DAY | `karın ağrısı` | HIGH |
| `karnımdan başlayıp sırtıma vuruyor` | EMERGENCY-suspect (pancreas / kidney) | `karın ağrısı`, `sırta yansıyan ağrı` | CRITICAL |
| `boynumda sertlik` | QUESTION | `boyun sertliği` | MEDIUM |
| `boynumdan baş ağrım başlıyor` | QUESTION | `boyun ağrısı`, `baş ağrısı` | MEDIUM |
| `başımda zonklama var` | QUESTION | `baş ağrısı` | HIGH |
| `başımdan ter akıyor` | QUESTION (vasovagal / ısı) | `terleme` | MEDIUM |
| `karnıma yumruk yedim gibi` | QUESTION (travma) | `karın ağrısı`, `travma` | HIGH |
| `başıma ağrı saplanıyor` | QUESTION | `baş ağrısı` | HIGH |
| `dizimde şişlik` | QUESTION | `diz şişliği` | MEDIUM |
| `bileğimden ağrı yayılıyor` | QUESTION | `bilek ağrısı` | MEDIUM |

**Failure mode:** stem-form regex fails on the suffixed form, so
`karnımda` misses while `karın` matches. The session ends up with no
canonicals from a sentence that clearly contains a symptom — and the
question selector picks generic onboarding questions instead of
abdomen-specific ones.

**Implementation note:** the durable fix is morphology-aware
extraction (Zemberek or a TR-aware tokenizer with stem reduction), not
ever-expanding the variants list. Until then, every locative /
ablative / dative form of the top-50 symptom nouns belongs in
`config/synonyms_tr.json` as an explicit `variants_tr` entry.

---

### 3. Missing diacritics

Mobile users typing without a TR keyboard drop diacritics: `gogusumde`
for `göğüsümde`, `karin` for `karın`, `bas agrim` for `baş ağrım`.
Common in older devices, in-call patient apps, and tourist medical
visits.

| Input | Expected envelope | Expected canonicals | Severity |
|-------|-------------------|---------------------|----------|
| `gogusumde sıkışma var` | EMERGENCY | `göğüs ağrısı` | CRITICAL |
| `karin agrim var` | SAME_DAY | `karın ağrısı` | HIGH |
| `bas donmesi yasiyorum` | QUESTION | `baş dönmesi` | HIGH |
| `gozum sislik` | QUESTION | `göz şişliği` | MEDIUM |
| `bogazim cok agriyor` | QUESTION | `boğaz ağrısı` | MEDIUM |
| `nefesim daraliyor` | EMERGENCY-candidate | `nefes darlığı` | CRITICAL |
| `idrarda yanma` | QUESTION | `idrar yanması` | MEDIUM |
| `sirtimda agri` | QUESTION | `sırt ağrısı` | MEDIUM |
| `gogus agrisi` | QUESTION (without modifier, not auto-EMERGENCY) | `göğüs ağrısı` | HIGH |
| `igrenc kokulu burun akintisi` | QUESTION | `burun akıntısı` | MEDIUM |

**Failure mode:** every regex compiled against the diacritic'd form
misses the ASCII transliteration. Verify `normalize_text_tr` does NOT
strip diacritics — it preserves them, which is correct for TR-aware
matching but means the input must be folded to the same form. Two
viable fixes: (a) ASCII-fold input AND every variant, (b) auto-expand
each variant entry into its diacritic-stripped twin at pattern build
time. Option (b) is one hook in `build_synonym_patterns`.

---

### 4. Spelling variants / typos

Typo modes: doubled consonants (`bbaş`), wrong vowel (`gögüs` instead
of `göğüs`), missing letter (`karnk` for `karnım`), keyboard-adjacent
slip (`karnim` for `karnım`). Mobile autocorrect on TR sometimes makes
this worse, not better, by suggesting the wrong word.

| Input | Expected envelope | Expected canonicals | Severity |
|-------|-------------------|---------------------|----------|
| `gögüs ağrım var` | QUESTION (with cardiac follow-up) | `göğüs ağrısı` | HIGH |
| `goğus ağrım var` | QUESTION | `göğüs ağrısı` | MEDIUM |
| `karnk ağrıyor` | (unrecoverable typo) → QUESTION asking clarification | (none) | MEDIUM |
| `karnim ağrıyor` (i not ı) | SAME_DAY | `karın ağrısı` | HIGH |
| `bbaş ağrım` | QUESTION | `baş ağrısı` | MEDIUM |
| `mıdem bulanıyor` | QUESTION | `mide bulantısı` | MEDIUM |
| `bsşım dönüyor` | QUESTION (clarify) | (partial) | MEDIUM |
| `kararım ağrıyor` (typo for karnım) | QUESTION (clarify) | (none) | LOW |

**Failure mode:** strict regex misses any typo. A small fuzzy-match
layer (Levenshtein ≤2 on canonical phrase) catches most without
introducing false positives on body-part nouns. Keep fuzzy matching
OFF for emergency patterns — false positives there are dangerous.

---

### 5. Dialect / colloquial / aged-care voice

Older patients use colloquial intensifiers (`fena halde`, `iğrenç`,
`çok kötü`) and family-relational speech to the assistant
(`evlat dinler misin`, `oğlum şuraya bak`). Aged-care is a real
TriAIge segment — Acıbadem's catchment is older.

| Input | Expected envelope | Expected canonicals | Severity |
|-------|-------------------|---------------------|----------|
| `evlat içim çok fena, midem bulandı` | QUESTION | `mide bulantısı`, `halsizlik` | HIGH |
| `oğlum başım dönüyor düşeceğim galiba` | QUESTION (geriatric fall risk) | `baş dönmesi`, `düşme riski` | CRITICAL |
| `boklu bir gün geçirdim midem bozuldu` | QUESTION | `mide bozukluğu` | MEDIUM |
| `iğrenç bir koku duyuyorum sürekli` | QUESTION (olfactory hallucination) | `koku alma bozukluğu` | HIGH |
| `kötü hissediyorum, ne diyim` | QUESTION (clarify) | (none) | MEDIUM |
| `delirdim ya kafam çatlıyor` | QUESTION | `baş ağrısı` | HIGH |
| `fena haldeyim doktor` | QUESTION (clarify severity) | (none) | HIGH |
| `kızım ne yapacağız bilmiyorum, çok ağrı var` | QUESTION (clarify location) | (none) | HIGH |
| `şu an yaşadığım şey çok berbat` | QUESTION (clarify) | (none) | MEDIUM |
| `nefesim tıkanıyor adeta` | EMERGENCY-candidate | `nefes darlığı` | CRITICAL |

**Failure mode:** symptom-relevant content is buried under colloquial
filler. The free-text parser strips punctuation but does not strip
sentiment intensifiers. Acceptable as long as canonical extraction
still finds the noun. Risk: colloquial intensifiers (`delirdim`,
`fena halde`) might be misread as severity claims by an LLM-based
pass; ensure the deterministic path remains the source of truth for
emergency routing.

---

### 6. Mixed language

Turkish + English (common with younger users), Turkish + Kurdish
(southeast Anatolia), Turkish + Arabic (medical tourism, Syrian
patients).

| Input | Expected envelope | Expected canonicals | Severity |
|-------|-------------------|---------------------|----------|
| `stress var, anxiety basıyor` | QUESTION | `stres`, `anksiyete` | MEDIUM |
| `panic attack geçirdim sanırım` | QUESTION | `panik atak` | HIGH |
| `bugün sabah migraine vardı şimdi yok` | QUESTION | `migren` | MEDIUM |
| `headache + fever 38` | QUESTION | `baş ağrısı`, `ateş`, value:38 | HIGH |
| `serê min êşan dike` (KU: head hurts) | QUESTION (clarify in TR) | (none — out of scope) | LOW |
| `راسي يؤلمني` (AR: my head hurts) | QUESTION (clarify in TR) | (none — out of scope) | LOW |
| `nausea var sabahtan beri` | QUESTION | `mide bulantısı` | MEDIUM |
| `chest pain, sharp` | EMERGENCY-candidate | `göğüs ağrısı` | CRITICAL |

**Failure mode:** mixed-language input breaks word-boundary matching
when the foreign word ends in a non-`\w` boundary character. EN +
TR mostly works; KU/AR with non-Latin script is currently out of
scope and should fall through to a clarification question, NOT crash.

---

### 7. Code-switching mid-sentence

Distinct from simple borrow words — full clause in a second language.

| Input | Expected envelope | Expected canonicals | Severity |
|-------|-------------------|---------------------|----------|
| `chest pain var sol koluma vuruyor` | EMERGENCY | `göğüs ağrısı`, `kola yansıyan ağrı` | CRITICAL |
| `since yesterday başım ağrıyor` | QUESTION | `baş ağrısı` | MEDIUM |
| `my stomach hurts midem ağrıyor` | QUESTION (dedup) | `mide ağrısı` | MEDIUM |
| `feeling dizzy, başım dönüyor` | QUESTION | `baş dönmesi` | HIGH |
| `i have fever, ateşim var 38.5` | QUESTION | `ateş`, value:38.5 | HIGH |
| `breathing zor, nefes alamıyorum` | EMERGENCY-candidate | `nefes darlığı` | CRITICAL |

**Failure mode:** EN clause contains the symptom; TR clause has the
modifier (or vice versa). Only the language-matched extractor sees
half. EN canonical synonyms entries (a small set, top-20 symptoms)
solve this without a full multilingual pipeline.

---

### 8. Severity descriptors as adjectives

`çok kötü ağrı`, `dayanılmaz`, `delicesine`, `bayılacak gibi`,
`ölecek gibi` — these often signal red-flag severity even on a
non-emergency body part.

| Input | Expected envelope | Expected canonicals | Severity |
|-------|-------------------|---------------------|----------|
| `dayanılmaz baş ağrım var` | EMERGENCY-candidate (sudden severe) | `baş ağrısı`, `şiddet:dayanılmaz` | CRITICAL |
| `delicesine ağrı, ölecek gibiyim` | EMERGENCY | `ölecek gibi` (red-flag), `şiddet:max` | CRITICAL |
| `bayılacak gibi oluyorum` | EMERGENCY-candidate (presyncope) | `presenkop`, `baş dönmesi` | CRITICAL |
| `karnım korkunç ağrıyor` | SAME_DAY (high severity) | `karın ağrısı`, `şiddet:yüksek` | HIGH |
| `çok kötü ağrı` (no body part) | QUESTION (clarify location) | (none) | HIGH |
| `şiddetli baş ağrısı ani başladı` | EMERGENCY (thunderclap pattern) | `baş ağrısı`, `ani başlangıç` | CRITICAL |
| `daha önce hiç böyle ağrım olmadı` | EMERGENCY-suspect (novel severe) | `yeni başlangıç` | HIGH |

**Failure mode:** body-part canonical extracted, severity adjective
ignored, envelope downgrades to `QUESTION`. The thunderclap-headache
pattern is a known stroke / SAH red flag and SHOULD route as
emergency.

---

### 9. Negation

Emergency rules MUST NOT fire on a negated form. Real user reports
include statements like "no chest pain" while listing other
symptoms — the wrong rule firing on a negation is both clinically
wrong and erodes user trust.

| Input | Expected envelope | Expected canonicals | Severity |
|-------|-------------------|---------------------|----------|
| `göğüs ağrım yok ama nefesim daralıyor` | EMERGENCY-candidate (nefes) | `nefes darlığı` (NOT göğüs ağrısı) | CRITICAL |
| `nefes darlığı yaşamıyorum` | QUESTION | (none — negated) | HIGH |
| `başım dönmüyor şu an` | QUESTION | (none — negated) | MEDIUM |
| `bayılma değil, sadece halsizlik` | QUESTION | `halsizlik` (NOT bayılma) | HIGH |
| `kalp çarpıntısı yok` | QUESTION | (none — negated) | HIGH |
| `kanama olmadı henüz` | QUESTION | (none — negated) | HIGH |
| `ağrım yok artık` | QUESTION | (none — negated) | MEDIUM |
| `daha önce vardı şimdi yok` | QUESTION | (none — past + negated) | MEDIUM |

**Failure mode:** the existing `is_negated` window in
`canonical_extract.py` is 18 chars — it catches `ağrım yok` but
misses `göğüs ağrısı yaşamıyorum` if the negation token sits past
the window. Verify window size and add tests for both edges. The
`emergency_router.py` does NOT do negation filtering — it uses raw
`contains_any`. That is the higher-risk gap; add negation gating to
emergency rule evaluation.

---

### 10. Indirect speech / quotation

Patient quotes someone else's reassurance or fear. Must NOT route as
emergency just because the words appear inside a quote.

| Input | Expected envelope | Expected canonicals | Severity |
|-------|-------------------|---------------------|----------|
| `doktor 'bu acil değil' dedi ama içim rahat değil` | QUESTION (anxiety, NOT emergency) | `anksiyete` | HIGH |
| `annem panik atak diyor ama ben emin değilim` | QUESTION | `panik atak (suspect)` | MEDIUM |
| `eşim 'kalp krizi geçiriyorsun' dedi` | EMERGENCY (still treat seriously — third-party report) | `göğüs ağrısı (suspect)` | CRITICAL |
| `internet 'kanser olabilir' yazıyor` | QUESTION (anxiety + clarify) | `anksiyete` | MEDIUM |
| `arkadaşım stres dedi` | QUESTION | `stres (subjective)` | LOW |
| `babam 'beyin kanaması olabilir' dedi` | EMERGENCY-candidate (third-party report still triggers safety) | `baş ağrısı (suspect)` | CRITICAL |

**Failure mode:** the rule fires on the quoted phrase rather than the
patient's actual symptom claim. Ambiguous: when a third party reports
a serious symptom, the conservative move is still to escalate even if
the patient denies it ("eşim kalp krizi diyor"). Document the rule:
**third-party report of a red-flag symptom DOES trigger safety check;
quoted reassurance does NOT downgrade severity.**

---

### 11. Numeric expressions

Duration, count, vitals, frequency. The duration parser
(`backend/app/duration_parse.py`) handles some of these; verify it
handles the long tail.

| Input | Expected envelope | Expected canonicals | Severity |
|-------|-------------------|---------------------|----------|
| `5 gündür baş ağrım var` | QUESTION | `baş ağrısı`, duration:5d | HIGH |
| `iki saat oldu başlayalı` | QUESTION | duration:2h | MEDIUM |
| `yarım gündür ateşim var` | QUESTION | `ateş`, duration:0.5d | MEDIUM |
| `38 derece ateş var` | QUESTION | `ateş`, value:38°C | HIGH |
| `tansiyonum 18` | EMERGENCY-candidate (high) | `yüksek tansiyon`, value:180/? | CRITICAL |
| `şeker 350` | EMERGENCY-candidate (DKA suspect) | `yüksek kan şekeri`, value:350 | CRITICAL |
| `nabız 130` | EMERGENCY-candidate (taşikardi) | `taşikardi`, value:130 | CRITICAL |
| `oksijen 88` (sat) | EMERGENCY (hipoksi) | `hipoksi`, value:88 | CRITICAL |
| `30 dk önce başladı` | QUESTION | duration:30m | MEDIUM |
| `3 haftadır` | QUESTION | duration:21d | MEDIUM |
| `günde 5 kez kustum` | SAME_DAY | `kusma`, freq:5/day | HIGH |
| `son bir hafta günde 3 kez` | QUESTION | freq, duration | MEDIUM |

**Failure mode:** numeric red-flags (BP, glucose, sat, HR) parsed as
plain text, not as vitals, so emergency rules do not fire. Add a
vitals-extractor stage before the canonical extractor.

---

### 12. Empty / whitespace / single-character / extreme-length

| Input | Expected envelope | Expected canonicals | Severity |
|-------|-------------------|---------------------|----------|
| `""` (empty) | ERROR (validation 422) | — | HIGH |
| `" "` (whitespace) | ERROR (validation 422) | — | HIGH |
| `"a"` | QUESTION (clarify) | (none) | MEDIUM |
| `"."` | QUESTION (clarify) | (none) | MEDIUM |
| 1× character × 5000 | ERROR (validation — too long) | — | HIGH |
| Long real Turkish text >2000 chars | QUESTION (truncate, parse first 2000) | (extract from prefix) | MEDIUM |
| 50× repeated `aa aa aa…` | QUESTION (clarify) | (none) | MEDIUM |

**Failure mode:** unbounded input wastes Wiro tokens on every NLU
call. Pydantic max-length on the request body is the primary defense;
the canonical extractor's regex performance also degrades on very long
text (linear, but multiplied by ~1000 patterns).

---

### 13. Emoji-only / symbol-only

Mobile users sometimes send emoji as a description. Should not crash;
should ask for clarification.

| Input | Expected envelope | Expected canonicals | Severity |
|-------|-------------------|---------------------|----------|
| `😷` | QUESTION (clarify) | (none) | MEDIUM |
| `❤️ ağrı` | QUESTION (heart emoji + ağrı) | `kalp ağrısı (suspect)` | HIGH |
| `???` | QUESTION (clarify) | (none) | LOW |
| `🤒🤕` | QUESTION (clarify) | (none) | MEDIUM |
| `🔥 boğazım` | QUESTION (interpret 🔥 as severity?) | `boğaz ağrısı` | MEDIUM |

**Failure mode:** emoji passes through `normalize_text_tr` because
it's stripped by the punctuation regex. Fine. The question selector
should detect "input had no extractable canonical" and ask a
clarification question, not pretend a generic onboarding flow.

---

### 14. Adversarial / red-flag self-harm attempts

These MUST trigger an explicit safety response, not the generic triage
flow. Wrong response here is the highest-stakes failure mode in the
entire system.

| Input | Expected envelope | Expected canonicals | Severity |
|-------|-------------------|---------------------|----------|
| `intihar etmek istiyorum` | SAFETY_NET (Yaşam Hattı 182) | `intihar düşüncesi` | CRITICAL |
| `kendime zarar veriyorum` | SAFETY_NET | `kendine zarar verme` | CRITICAL |
| `hap yutmam gerek mi` | SAFETY_NET (clarify intent) | `hap doz sorusu` | CRITICAL |
| `mide ilacı kaç tane içsem` | SAFETY_NET | `doz aşımı sorusu` | CRITICAL |
| `ölmek istiyorum` | SAFETY_NET | `intihar düşüncesi` | CRITICAL |
| `bir avuç parol içsem ne olur` | SAFETY_NET | `doz aşımı` | CRITICAL |
| `kendimi kesmek istiyorum` | SAFETY_NET | `kendine zarar verme` | CRITICAL |
| `anneme zarar verme düşüncesi` | SAFETY_NET (others-harm) | `başkasına zarar` | CRITICAL |
| `iple bağlama yöntemi` | SAFETY_NET | `intihar yöntem sorusu` | CRITICAL |
| `bayılmak için ilaç` | SAFETY_NET | `doz aşımı` | CRITICAL |

**Failure mode:** the system gives generic medical triage advice on
self-harm intent. Verify `backend/app/safety_guard.py` and the
`safety_guard_check` rule fire on every phrase above. The expected
safety response includes:
1. The Turkish suicide hotline (Yaşam Hattı 182, AMATEM crisis line).
2. An explicit non-judgmental statement.
3. NO continuation of the regular triage flow.
4. NO LLM-generated free-form response — fully scripted, deterministic.

This is the single most important category in this corpus.

---

### 15. Profanity + symptom

Real patients vent. The system must extract the symptom and ignore
the profanity, not refuse to respond.

| Input | Expected envelope | Expected canonicals | Severity |
|-------|-------------------|---------------------|----------|
| `am[REDACTED] başım çatlıyor` | QUESTION | `baş ağrısı` | HIGH |
| `s[REDACTED] mideeem bulanıyor` | QUESTION | `mide bulantısı` | MEDIUM |
| `lan ne biçim ağrı bu karnımda` | QUESTION | `karın ağrısı` | MEDIUM |
| `aman tanrım göğsüm yanıyor` | EMERGENCY-candidate | `göğüs ağrısı` | CRITICAL |
| `ulan dayanamıyorum bu ağrıya` | QUESTION (severity: high) | `ağrı (location?)` | HIGH |

**Failure mode:** input filter rejects the entire message because of
profanity, dropping the symptom signal. The canonical extractor
already strips non-`\w` chars; verify no upstream profanity filter
short-circuits the pipeline.

---

## Implementation plan

### File layout

```
backend/tests/
├─ data/
│  └─ turkish_corpus.json        ← golden set (one entry per row above)
└─ test_corpus_turkish_natural.py ← parametrized pytest
```

### Golden JSON shape

```json
[
  {
    "id": "vowel_elision_001",
    "input": "göğsüm sıkışıyor",
    "category": "vowel_elision",
    "severity": "CRITICAL",
    "expected_envelope": "EMERGENCY",
    "expected_canonicals": ["göğüs ağrısı", "nefes darlığı"],
    "expected_safety_response": null,
    "notes": "chest_pain_sob class — must fire hard-trigger"
  },
  ...
]
```

`expected_canonicals` is a SUPERSET assertion (extracted set must
include all listed). `expected_envelope` is exact match. For category
14, `expected_safety_response` is an enum value (`SUICIDE_HOTLINE_182`,
`SELF_HARM`, `OVERDOSE`) that the test asserts on the rendered
response.

### Pytest harness sketch

```python
# backend/tests/test_corpus_turkish_natural.py
import json, pytest
from pathlib import Path
from app.canonical_extract import extract_canonicals_tr
from app.emergency_router import evaluate_rules
# Load synonyms + emergency rules once per session.

CORPUS_PATH = Path(__file__).parent / "data" / "turkish_corpus.json"
CORPUS = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))

@pytest.mark.parametrize("case", CORPUS, ids=[c["id"] for c in CORPUS])
def test_corpus_envelope(case, synonyms_fixture, rules_fixture):
    # Run the full deterministic pipeline (no Wiro / LLM).
    canonicals = extract_canonicals_tr(case["input"], {}, synonyms_fixture)
    envelope = decide_envelope(case["input"], canonicals, rules_fixture)
    assert envelope.type == case["expected_envelope"], (
        f"{case['id']} expected {case['expected_envelope']} got {envelope.type}"
    )
    for needed in case["expected_canonicals"]:
        assert needed in canonicals, (
            f"{case['id']} missing canonical {needed!r} in {canonicals}"
        )
```

### CI gate

- Add the test file to `backend-regression.yml`'s job set.
- **Pass criterion:** corpus pass rate ≥ 95% AND no regressions —
  i.e., previously-passing inputs that newly fail. Compute regression
  rate by storing the prior-run pass set as a CI artifact and diffing
  on each new run.
- **Fail criterion:** regression rate > 5%, OR any CRITICAL-severity
  case fails. CRITICAL fails the build unconditionally.
- **Report:** the test run uploads a `corpus_report.json` artifact
  with per-category pass rate. Slack-bot posts the diff if it
  worsens; silent on improvement.

### Refresh cadence

- **Monthly:** review the prior month's failed-input log
  (`triage_sessions` rows where envelope is `ERROR` or canonicals
  list is empty for non-trivial input). Pick the most-frequent novel
  shapes, add as new entries.
- **Quarterly:** spot-check a random 5% of the corpus to ensure
  expected envelopes are still clinically correct (rules drift; new
  rules can recategorize a previously-`SAME_DAY` input as `EMERGENCY`).
- **On every emergency rule change:** re-run the corpus locally
  before merging the rule change.

### Out of scope for v1

- Full Turkish morphology (Zemberek integration) — captured as future
  work. The corpus exposes the cost of NOT having it; the corpus
  itself doesn't fix it.
- Streaming / multi-turn coherence (a corpus entry is one input);
  multi-turn drift is its own test surface.
- Multi-tenant rule overrides — corpus runs against the default
  tenant config.

## What this corpus is not

- Not a substitute for adversarial human review of every emergency
  rule change.
- Not a replacement for clinical-board sign-off on routing decisions.
- Not a measure of model quality — it tests determinism, not
  diagnostic accuracy.
