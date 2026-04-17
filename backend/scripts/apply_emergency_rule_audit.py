#!/usr/bin/env python3
"""One-shot: extend emergency rule keyword/canonical lists (RC #2b).

Closes keyword gaps in config/emergency_rules.json surfaced by the
golden-flow triage. Each delta is idempotent — re-running is a no-op.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve()
_REPO_ROOT = _SCRIPT.parent.parent.parent
RULES_PATH = _REPO_ROOT / "config" / "emergency_rules.json"


# For each rule id, specify what to append. We never remove or rewrite.
# Fields we extend: keyword_any, canonical_any, and require_any_group items.
DELTAS: dict[str, dict] = {
    "infant_fever_under3months": {
        "keyword_any_add": [
            "6 haftalık",
            "5 haftalık",
            "4 haftalık",
            "7 haftalık",
            "8 haftalık",
            "10 haftalık",
            "yenidoğan bebeğim",
            "bebeğim 6 haftalık",
            "bebeğim 2 aylık",
        ],
        "canonical_any_add": [
            "yenidoğan ateşi",
        ],
        # require_any_group[0] is the fever-threshold group; add common
        # decimal temperature phrasings.
        "require_group_keyword_adds": {
            0: ["38.5", "38,5", "39.0", "39,0", "ateşi çıktı", "termometre 38"],
        },
    },
    "acute_glaucoma_crisis": {
        "keyword_any_add": [
            "ışıkların etrafında hale",
            "ışıkların etrafında halka",
            "ışıkta hale görüyorum",
        ],
        "canonical_any_add": [
            "ışık haleleri",
        ],
    },
    "ectopic_pregnancy_suspect": {
        # keyword_any is already rich (hamile/gebeyim/gebelik testi pozitif).
        # Extend the require_any_group so one-sided pelvic pain phrasings
        # also qualify as the "severity" gate.
        "require_group_keyword_adds": {
            0: [
                "kasığımda şiddetli ağrı",
                "sağ kasığımda ağrı",
                "sol kasığımda ağrı",
                "kasıkta ağrı",
                "tek taraflı kasık ağrısı",
            ],
        },
    },
    "acute_appendicitis_suspect": {
        # Cover the real phrasings: "sağ alt karın bölgemde" (with locative)
        # and similar variants. The canonical "sağ alt karın ağrısı" already
        # exists but synonyms may not boundary-match these exact strings.
        "keyword_any_add": [
            "sağ alt karın bölgem",
            "sağ alt karnımda",
            "sağ alt karın bölgemde",
            "sağ alt kadranda",
            "karnımın sağ alt kısmı",
        ],
    },
}


def _append_missing(dest: list, items: list, counters: list[int]) -> None:
    existing = {str(x).strip().lower() for x in dest}
    for it in items:
        key = str(it).strip().lower()
        if key and key not in existing:
            dest.append(it)
            existing.add(key)
            counters[0] += 1


def main() -> int:
    data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    rules = data.get("rules", [])
    by_id = {r.get("id"): r for r in rules}

    total_adds = [0]

    for rid, delta in DELTAS.items():
        rule = by_id.get(rid)
        if rule is None:
            print(f"WARN: rule id not found, skipping: {rid!r}", file=sys.stderr)
            continue

        if "keyword_any_add" in delta:
            rule.setdefault("keyword_any", [])
            _append_missing(rule["keyword_any"], delta["keyword_any_add"], total_adds)

        if "canonical_any_add" in delta:
            rule.setdefault("canonical_any", [])
            _append_missing(rule["canonical_any"], delta["canonical_any_add"], total_adds)

        if "require_group_keyword_adds" in delta:
            groups = rule.setdefault("require_any_group", [])
            for idx, items in delta["require_group_keyword_adds"].items():
                while len(groups) <= idx:
                    groups.append({"keyword_any": []})
                g = groups[idx]
                g.setdefault("keyword_any", [])
                _append_missing(g["keyword_any"], items, total_adds)

    RULES_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Done. {total_adds[0]} additions across {len(DELTAS)} rules.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
