"""Shared types for the safety package.

`SafetyResult` is the single contract returned by `app.safety.check_safety`.
Both orchestrator paths (triage_engine + agents/orchestrator) consume the
same shape — divergence between the two old safety_guard implementations
is exactly what ADR-001 set out to eliminate.

`path` is the observability dimension: which evaluation layer fired.
Counter `safety_guard_triggers_total{path=}` slices on this label.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional

SafetyStatus = Literal["OK", "EMERGENCY"]
SafetyPath = Literal["hard_keyword", "hard_regex", "soft_age", "llm", "none"]


@dataclass(frozen=True)
class SafetyResult:
    status: SafetyStatus
    rule_id: Optional[str] = None
    reason_tr: str = ""
    instructions_tr: List[str] = field(default_factory=list)
    soft_triggers: List[str] = field(default_factory=list)
    high_risk_age: bool = False
    enriched_by_llm: bool = False
    path: SafetyPath = "none"
