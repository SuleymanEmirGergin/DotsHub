#!/usr/bin/env python3
"""Produce a human-readable diff of two Kaggle-cache snapshots.

Intended use: the `kaggle-ingest` workflow stashes the pre-refresh
cache directory under `/tmp/kaggle_cache_pre/`, runs the fetch +
preprocess pipeline in place, then calls this script to render a
markdown summary of what actually changed. The summary is pasted
into the auto-created PR body so reviewers can spot-check without
doing a diff by eye on 1000-line JSON files.

Inputs
------
Two directory paths, each expected to contain the four cache files
the preprocess script emits:

    disease_symptoms.json          # {disease_label: [kaggle_symptom, ...]}
    symptom_severity.json          # {kaggle_symptom: int}
    disease_descriptions.json      # {disease_label: description_en}
    kaggle_to_canonical.json       # {kaggle_symptom: canonical_tr | null}

Either snapshot may be empty or missing files — if the "before"
directory is absent we emit an initial-ingest summary instead of a
diff. Missing files inside a present snapshot are treated as
"empty side" rather than erroring.

Output
------
Markdown on stdout. Always prints a top-level section count so the
caller can grep for non-zero totals to decide whether to open a PR.
Example tail:

    ### Totals

    | Metric | Before | After | Delta |
    | ------ | ------ | ----- | ----- |
    | diseases | 39 | 40 | +1 |
    | symptoms | 140 | 141 | +1 |
    | canonical mappings | 91 | 92 | +1 |

Exit codes
----------
    0 — diff produced (even if empty — the caller decides on PR)
    2 — the "after" directory is missing files we expect; workflow
        should halt before opening a PR

Not a gate, not a guardrail — those concerns belong to
`validate_kaggle_mapping.py` + the golden-flow test suite. This
script is purely observational reporting.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

CACHE_FILES = (
    "disease_symptoms.json",
    "symptom_severity.json",
    "disease_descriptions.json",
    "kaggle_to_canonical.json",
)


def _load(path: Path) -> Any:
    """Load JSON from path; return None if missing, {} for empty file."""
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    return json.loads(text)


def _sym_counts(disease_symptoms: Dict[str, List[str]]) -> int:
    total = 0
    for _, syms in disease_symptoms.items():
        if isinstance(syms, list):
            total += len(syms)
    return total


def _canonical_counts(mapping: Dict[str, Optional[str]]) -> Tuple[int, int]:
    """Return (total, non-null) canonical mappings."""
    total = len(mapping)
    non_null = sum(1 for v in mapping.values() if v)
    return total, non_null


def _format_delta(before: int, after: int) -> str:
    delta = after - before
    if delta == 0:
        return "±0"
    if delta > 0:
        return f"+{delta}"
    return str(delta)


def _bullet_list(items: Iterable[str], limit: int = 10) -> str:
    items_list = list(items)
    if not items_list:
        return "_(none)_"
    shown = items_list[:limit]
    lines = [f"- `{x}`" for x in shown]
    if len(items_list) > limit:
        lines.append(f"- _…and {len(items_list) - limit} more_")
    return "\n".join(lines)


def _render_diseases_section(
    before: Dict[str, List[str]],
    after: Dict[str, List[str]],
) -> str:
    before_set: Set[str] = set(before.keys())
    after_set: Set[str] = set(after.keys())
    added = sorted(after_set - before_set)
    removed = sorted(before_set - after_set)
    common = before_set & after_set

    # For diseases present in both snapshots, flag when the symptom
    # list changed materially — reviewers care most about >10%
    # shifts because that's when CandidateGenerator scoring moves.
    symptom_drift: List[Tuple[str, int, int]] = []
    for label in sorted(common):
        b_syms = before.get(label) or []
        a_syms = after.get(label) or []
        if set(b_syms) != set(a_syms):
            symptom_drift.append((label, len(b_syms), len(a_syms)))

    parts = ["## Diseases\n"]
    parts.append(f"**Added ({len(added)}):**\n{_bullet_list(added)}\n")
    parts.append(f"**Removed ({len(removed)}):**\n{_bullet_list(removed)}\n")
    if symptom_drift:
        rows = [
            f"| `{label}` | {b} | {a} | {_format_delta(b, a)} |"
            for label, b, a in symptom_drift[:20]
        ]
        overflow = (
            f"\n_…and {len(symptom_drift) - 20} more_"
            if len(symptom_drift) > 20
            else ""
        )
        parts.append(
            "**Symptom lists changed (count before -> after):**\n\n"
            "| Disease | Before | After | Δ |\n"
            "| ------- | ------ | ----- | - |\n"
            + "\n".join(rows)
            + overflow
        )
    else:
        parts.append("**Symptom lists changed:** _(none)_")
    return "\n".join(parts) + "\n"


def _render_symptoms_section(
    before: Dict[str, int],
    after: Dict[str, int],
) -> str:
    before_set = set(before.keys())
    after_set = set(after.keys())
    added = sorted(after_set - before_set)
    removed = sorted(before_set - after_set)
    severity_changed = sorted(
        s
        for s in (before_set & after_set)
        if before.get(s) != after.get(s)
    )
    parts = ["## Symptoms (severity matrix)\n"]
    parts.append(f"**Added ({len(added)}):**\n{_bullet_list(added)}\n")
    parts.append(f"**Removed ({len(removed)}):**\n{_bullet_list(removed)}\n")
    if severity_changed:
        rows = []
        for s in severity_changed[:20]:
            b_sev = before.get(s)
            a_sev = after.get(s)
            rows.append(f"| `{s}` | {b_sev} | {a_sev} |")
        overflow = (
            f"\n_…and {len(severity_changed) - 20} more_"
            if len(severity_changed) > 20
            else ""
        )
        parts.append(
            "**Severity changed (before -> after):**\n\n"
            "| Symptom | Before | After |\n"
            "| ------- | ------ | ----- |\n"
            + "\n".join(rows)
            + overflow
        )
    else:
        parts.append("**Severity values changed:** _(none)_")
    return "\n".join(parts) + "\n"


def _render_canonical_section(
    before: Dict[str, Optional[str]],
    after: Dict[str, Optional[str]],
) -> str:
    before_set = set(before.keys())
    after_set = set(after.keys())
    added = sorted(after_set - before_set)
    removed = sorted(before_set - after_set)
    # Remapped = key exists in both but canonical value changed.
    remapped: List[Tuple[str, Optional[str], Optional[str]]] = []
    for k in sorted(before_set & after_set):
        bv = before.get(k)
        av = after.get(k)
        if bv != av:
            remapped.append((k, bv, av))

    parts = ["## Canonical mappings (kaggle_to_canonical)\n"]
    parts.append(f"**Added ({len(added)}):**\n{_bullet_list(added)}\n")
    parts.append(f"**Removed ({len(removed)}):**\n{_bullet_list(removed)}\n")
    if remapped:
        rows = []
        for key, bv, av in remapped[:20]:
            rows.append(f"| `{key}` | `{bv}` | `{av}` |")
        overflow = (
            f"\n_…and {len(remapped) - 20} more_"
            if len(remapped) > 20
            else ""
        )
        parts.append(
            "**Canonical value changed:**\n\n"
            "| Kaggle symptom | Before | After |\n"
            "| -------------- | ------ | ----- |\n"
            + "\n".join(rows)
            + overflow
        )
    else:
        parts.append("**Canonical remappings:** _(none)_")
    return "\n".join(parts) + "\n"


def _render_descriptions_section(
    before: Dict[str, str],
    after: Dict[str, str],
) -> str:
    before_set = set(before.keys())
    after_set = set(after.keys())
    added = sorted(after_set - before_set)
    removed = sorted(before_set - after_set)
    changed = sorted(
        k for k in (before_set & after_set) if before.get(k) != after.get(k)
    )
    parts = ["## Disease descriptions\n"]
    parts.append(f"**Added descriptions ({len(added)}):**\n{_bullet_list(added)}\n")
    parts.append(f"**Removed descriptions ({len(removed)}):**\n{_bullet_list(removed)}\n")
    parts.append(f"**Rewritten descriptions:** {len(changed)}")
    return "\n".join(parts) + "\n"


def _render_totals(
    before: Optional[Dict[str, Any]],
    after: Dict[str, Any],
) -> str:
    def metric(key: str, counter) -> Tuple[int, int]:
        b_val = counter(before.get(key, {})) if before else 0
        a_val = counter(after.get(key, {}))
        return b_val, a_val

    ds_b, ds_a = metric("disease_symptoms", lambda x: len(x))
    sy_b, sy_a = metric("disease_symptoms", _sym_counts)
    sev_b, sev_a = metric("symptom_severity", lambda x: len(x))
    can_b, can_a = metric("kaggle_to_canonical", lambda x: len(x))
    rows = [
        ("diseases", ds_b, ds_a),
        ("symptom occurrences", sy_b, sy_a),
        ("unique symptoms (severity)", sev_b, sev_a),
        ("canonical mappings", can_b, can_a),
    ]
    body = "\n".join(
        f"| {name} | {b} | {a} | {_format_delta(b, a)} |"
        for name, b, a in rows
    )
    return (
        "## Totals\n\n"
        "| Metric | Before | After | Δ |\n"
        "| ------ | ------ | ----- | - |\n"
        f"{body}\n"
    )


def _load_snapshot(dir_path: Path) -> Dict[str, Any]:
    snap: Dict[str, Any] = {}
    missing: List[str] = []
    for name in CACHE_FILES:
        data = _load(dir_path / name)
        if data is None:
            missing.append(name)
            snap[name.replace(".json", "")] = {}
        else:
            snap[name.replace(".json", "")] = data
    snap["__missing__"] = missing
    return snap


def build_markdown(before_dir: Optional[Path], after_dir: Path) -> str:
    if not after_dir.exists():
        return "_**error:** after-dir does not exist — nothing to diff._"
    after = _load_snapshot(after_dir)
    if after["__missing__"]:
        return (
            "_**error:** after-snapshot missing files: "
            f"{', '.join(after['__missing__'])}_"
        )

    if before_dir is None or not before_dir.exists():
        # Initial-ingest mode — summarise the new cache only.
        sections = [
            "_No prior snapshot found — this is an initial ingest._\n",
            _render_totals(None, after),
        ]
        return "\n\n".join(sections)

    before = _load_snapshot(before_dir)

    sections = [
        _render_diseases_section(
            before.get("disease_symptoms", {}),
            after.get("disease_symptoms", {}),
        ),
        _render_symptoms_section(
            before.get("symptom_severity", {}),
            after.get("symptom_severity", {}),
        ),
        _render_canonical_section(
            before.get("kaggle_to_canonical", {}),
            after.get("kaggle_to_canonical", {}),
        ),
        _render_descriptions_section(
            before.get("disease_descriptions", {}),
            after.get("disease_descriptions", {}),
        ),
        _render_totals(before, after),
    ]
    return "\n\n".join(sections)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--before",
        type=Path,
        default=None,
        help="Directory with the pre-refresh cache snapshot (optional).",
    )
    parser.add_argument(
        "--after",
        type=Path,
        required=True,
        help="Directory with the post-refresh cache snapshot.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write markdown to this path in addition to stdout.",
    )
    args = parser.parse_args(argv)

    try:
        md = build_markdown(args.before, args.after)
    except json.JSONDecodeError as exc:
        print(f"FATAL: malformed JSON in cache snapshot: {exc}", file=sys.stderr)
        return 2

    # Markdown contains Turkish characters + the Δ glyph in the
    # totals table. Force UTF-8 on stdout so the script is portable —
    # CI runs on Linux (already UTF-8) but local devs on Windows hit
    # cp1254 by default which choke on Δ.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        pass
    sys.stdout.write(md + "\n")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
