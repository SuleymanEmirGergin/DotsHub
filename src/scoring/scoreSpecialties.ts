/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * TypeScript Reference Implementation — Deterministic Specialty Scoring
 *
 * Usage (Node.js):
 *   import { scoreSpecialtiesDeterministic } from './scoreSpecialties';
 *   const res = scoreSpecialtiesDeterministic(
 *     "Başım dönüyor, midem bulanıyor",
 *     "./config/synonyms_tr.json",
 *     "./config/specialty_keywords_tr.json"
 *   );
 *   console.log(res.top);
 */
import fs from "fs";

type SynonymsFile = {
  version: string;
  language: string;
  rules: {
    double_count_policy: "NO_DOUBLE_COUNT_SAME_CANONICAL";
    canonical_priority: ("phrase" | "keyword")[];
  };
  synonyms: Array<{
    canonical: string;
    type: "symptom" | "red_flag";
    variants_tr: string[];
  }>;
};

type SpecialtyKeywordsFile = {
  version: string;
  language: string;
  specialties: Array<{
    id: string;
    specialty_tr: string;
    keywords_tr: string[];
    negative_keywords_tr: string[];
  }>;
  scoring: {
    keyword_match_points: number; // 3
    phrase_match_points: number;  // 5
    negative_keyword_penalty: number; // -4
    tie_breakers: string[];
  };
};

export type SpecialtyScore = {
  id: string;
  specialty_tr: string;
  score: number;
  phrase_score: number;
  keyword_score: number;
  negative_penalties: number;
  matched_phrases_tr: string[];
  matched_keywords_tr: string[];
  matched_canonicals: string[]; // scored canonicals
  debug: {
    normalized_text: string;
    hits: Array<{ kind: "phrase" | "keyword" | "negative"; value: string; points: number }>;
  };
};

function normalizeTR(input: string): string {
  // deterministic normalization with Turkish İ/I case folding
  return input
    .replace(/\u0130/g, "i")   // İ → i (Turkish capital I with dot)
    .replace(/I/g, "\u0131")   // I → ı (Turkish capital I without dot)
    .toLowerCase()
    .trim()
    .replace(/[.,;:!?(){}\[\]"'`~]/g, " ")
    .replace(/\s+/g, " ");
}

function unique<T>(arr: T[]): T[] {
  return Array.from(new Set(arr));
}

function loadJson<T>(path: string): T {
  return JSON.parse(fs.readFileSync(path, "utf-8")) as T;
}

export function buildSynonymIndex(syn: SynonymsFile) {
  // variants sorted by length desc for deterministic longest-match-first
  const variants: Array<{ variant: string; canonical: string; type: string }> = [];
  for (const s of syn.synonyms) {
    for (const v of s.variants_tr) {
      variants.push({ variant: v.toLowerCase(), canonical: s.canonical.toLowerCase(), type: s.type });
    }
  }
  variants.sort((a, b) => b.variant.length - a.variant.length || a.variant.localeCompare(b.variant));

  // canonical set for quick keyword checks
  const canonicalSet = new Set(syn.synonyms.map(s => s.canonical.toLowerCase()));
  return { variants, canonicalSet };
}

export function scoreSpecialtiesDeterministic(
  text_tr: string,
  synonymsPath: string,
  specialtyKeywordsPath: string
): { normalized_text: string; scores: SpecialtyScore[]; top: SpecialtyScore; tie: boolean } {
  const syn = loadJson<SynonymsFile>(synonymsPath);
  const spec = loadJson<SpecialtyKeywordsFile>(specialtyKeywordsPath);
  const { variants, canonicalSet } = buildSynonymIndex(syn);

  const normalized = normalizeTR(text_tr);

  // 1) Phrase detection -> matched canonicals (NOT scored yet)
  const matchedPhrases: Array<{ phrase: string; canonical: string }> = [];
  const canonicalLocked = new Set<string>(); // NO_DOUBLE_COUNT_SAME_CANONICAL

  for (const item of variants) {
    if (normalized.includes(item.variant)) {
      // if canonical already locked, still allow storing phrase for UX,
      // but do not create new canonical
      matchedPhrases.push({ phrase: item.variant, canonical: item.canonical });
      canonicalLocked.add(item.canonical);
    }
  }

  // 2) Canonical keywords appearing directly in text (if not already locked by phrase)
  const matchedKeywords: string[] = [];
  for (const canonical of Array.from(canonicalSet).sort()) {
    if (normalized.includes(canonical) && !canonicalLocked.has(canonical)) {
      matchedKeywords.push(canonical);
      canonicalLocked.add(canonical);
    }
  }

  // For scoring, we want: phrase contributes once per canonical (priority phrase>keyword)
  // We'll compute scoredCanonicals from phrases first, then keywords.
  const phraseCanonicalsOrdered = unique(matchedPhrases.map(p => p.canonical));
  const keywordCanonicalsOrdered = unique(matchedKeywords);

  // Precompute per-specialty keyword sets (lowercase)
  const specialtyData = spec.specialties.map(s => ({
    id: s.id,
    specialty_tr: s.specialty_tr,
    keywords: new Set(s.keywords_tr.map(k => k.toLowerCase())),
    negatives: s.negative_keywords_tr.map(n => n.toLowerCase())
  }));

  const scores: SpecialtyScore[] = [];

  for (const s of specialtyData) {
    let score = 0;
    let phraseScore = 0;
    let keywordScore = 0;
    let negativePenalties = 0;

    const matched_phrases_tr: string[] = [];
    const matched_keywords_tr: string[] = [];
    const scoredCanonicals = new Set<string>();
    const hits: SpecialtyScore["debug"]["hits"] = [];

    // Phrase scoring: if canonical OR phrase literal exists in specialty keywords
    for (const canonical of phraseCanonicalsOrdered) {
      // Find a representative phrase for UX
      const anyPhrase = matchedPhrases.find(p => p.canonical === canonical)?.phrase;

      const phraseMatchesSpecialty =
        s.keywords.has(canonical) || (anyPhrase ? s.keywords.has(anyPhrase) : false);

      if (phraseMatchesSpecialty && !scoredCanonicals.has(canonical)) {
        score += spec.scoring.phrase_match_points;
        phraseScore += spec.scoring.phrase_match_points;
        scoredCanonicals.add(canonical);
        if (anyPhrase) matched_phrases_tr.push(anyPhrase);
        hits.push({ kind: "phrase", value: anyPhrase ?? canonical, points: spec.scoring.phrase_match_points });
      }
    }

    // Keyword scoring (only canonicals not scored by phrase)
    for (const canonical of keywordCanonicalsOrdered) {
      if (s.keywords.has(canonical) && !scoredCanonicals.has(canonical)) {
        score += spec.scoring.keyword_match_points;
        keywordScore += spec.scoring.keyword_match_points;
        scoredCanonicals.add(canonical);
        matched_keywords_tr.push(canonical);
        hits.push({ kind: "keyword", value: canonical, points: spec.scoring.keyword_match_points });
      }
    }

    // Negative penalties
    for (const neg of s.negatives) {
      if (neg && normalized.includes(neg)) {
        score += spec.scoring.negative_keyword_penalty;
        negativePenalties += spec.scoring.negative_keyword_penalty;
        hits.push({ kind: "negative", value: neg, points: spec.scoring.negative_keyword_penalty });
      }
    }

    scores.push({
      id: s.id,
      specialty_tr: s.specialty_tr,
      score,
      phrase_score: phraseScore,
      keyword_score: keywordScore,
      negative_penalties: negativePenalties,
      matched_phrases_tr: unique(matched_phrases_tr),
      matched_keywords_tr: unique(matched_keywords_tr),
      matched_canonicals: Array.from(scoredCanonicals).sort(),
      debug: { normalized_text: normalized, hits }
    });
  }

  // Deterministic sorting + tie flag
  scores.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    if (b.keyword_score !== a.keyword_score) return b.keyword_score - a.keyword_score; // tie-break 1
    return a.id.localeCompare(b.id); // deterministic final tie-break
  });

  const top = scores[0];
  const tie = scores.length > 1 && scores[0].score === scores[1].score && scores[0].keyword_score === scores[1].keyword_score;

  return { normalized_text: normalized, scores, top, tie };
}
