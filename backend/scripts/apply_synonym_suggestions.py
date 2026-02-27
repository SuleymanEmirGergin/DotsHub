"""Apply synonym suggestions from a tuning report to synonyms_tr.json.

Reads synonym_suggestions from a tuning report JSON, then:
  - Checks if each token→canonical mapping already exists
  - Adds new variants to the matching canonical entry
  - Writes a patch file for audit trail
  - Optionally updates synonyms_tr.json (or --dry_run)

Adapted to the actual synonyms_tr.json format:
  {
    "synonyms": [
      { "canonical": "baş ağrısı", "type": "symptom", "variants_tr": [...] }
    ]
  }

Usage:
  python scripts/apply_synonym_suggestions.py --report reports/tuning_report_*.json --dry_run
  python scripts/apply_synonym_suggestions.py --report reports/tuning_report_*.json
"""

from __future__ import annotations
import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def load_json(p: str) -> Any:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def save_json(p: str, data: Any) -> None:
    Path(p).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def main() -> None:
    ap = argparse.ArgumentParser(description="Apply synonym suggestions to synonyms_tr.json")
    ap.add_argument("--report", required=True, help="tuning_report_*.json path")
    ap.add_argument("--synonyms", default="app/data/synonyms_tr.json")
    ap.add_argument("--min_count", type=int, default=3)
    ap.add_argument("--dry_run", action="store_true")
    args = ap.parse_args()

    report = load_json(args.report)
    syn = load_json(args.synonyms)

    suggestions: List[Dict[str, Any]] = report.get("synonym_suggestions", [])
    synonyms_list: List[Dict[str, Any]] = syn.get("synonyms", [])

    # Build existing variants set and canonical→index lookup
    existing_variants: set = set()
    canonical_idx: Dict[str, int] = {}
    for i, entry in enumerate(synonyms_list):
        c = norm(entry.get("canonical", ""))
        if c:
            canonical_idx[c] = i
            for v in entry.get("variants_tr", []):
                existing_variants.add((c, norm(v)))
            existing_variants.add((c, c))  # canonical itself

    applied: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    for s in suggestions:
        token = norm(s.get("token", ""))
        can = norm(s.get("suggested_canonical", ""))
        cnt = int(s.get("support_count", 0))

        if not token or not can or cnt < args.min_count:
            skipped.append({**s, "reason": "missing_fields_or_low_count"})
            continue

        if can not in canonical_idx:
            skipped.append({**s, "reason": "canonical_not_in_synonyms"})
            continue

        if (can, token) in existing_variants:
            skipped.append({**s, "reason": "already_present"})
            continue

        # Apply
        idx = canonical_idx[can]
        synonyms_list[idx]["variants_tr"].append(token)
        existing_variants.add((can, token))
        applied.append(s)

    syn["synonyms"] = synonyms_list

    # Write patch file
    patch = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "report_used": args.report,
        "synonyms_file": args.synonyms,
        "min_count": args.min_count,
        "applied": applied,
        "skipped": skipped,
    }

    out = Path("reports")
    out.mkdir(exist_ok=True, parents=True)
    patch_path = out / f"synonyms_patch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    save_json(str(patch_path), patch)

    if args.dry_run:
        print("DRY RUN. Would update:", args.synonyms)
        print("Patch written:", patch_path)
        print(f"Applied: {len(applied)}  Skipped: {len(skipped)}")
        return

    save_json(args.synonyms, syn)
    print("UPDATED:", args.synonyms)
    print("Patch written:", patch_path)
    print(f"\nApplied: {len(applied)}  Skipped: {len(skipped)}")
    print("\nNext steps:")
    print(f"  git diff {args.synonyms}")
    print(f"  git add {args.synonyms} {patch_path}")
    print('  git commit -m "tuning: apply synonym suggestions"')


if __name__ == "__main__":
    main()
