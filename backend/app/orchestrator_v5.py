"""Orchestrator V5 - unified deterministic envelope flow.

Single entry point: orchestrate().
Frontend only renders based on envelope_type.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.duration_parse import extract_duration_days
from app.explainability import build_explanation_trace
from app.risk import compute_risk


class EnvelopeType(str, Enum):
    QUESTION = "QUESTION"
    RESULT = "RESULT"
    EMERGENCY = "EMERGENCY"
    SAME_DAY = "SAME_DAY"


class StopReason(str, Enum):
    EMERGENCY_DETECTED = "emergency_detected"
    SAME_DAY_RECOMMENDED = "same_day_recommended"
    QUESTION_BUDGET_EXCEEDED = "question_budget_exceeded"
    MIN_EXPECTED_GAIN = "min_expected_gain"
    HIGH_CONFIDENCE = "high_confidence"
    POLICY_FORCED_STOP = "policy_forced_stop"


@dataclass
class Envelope:
    envelope_type: EnvelopeType
    payload: Dict[str, Any]
    stop_reason: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


@dataclass
class TriageContext:
    session_id: str
    user_text: str
    locale: str = "tr-TR"
    device_id: Optional[str] = None
    ip: Optional[str] = None

    extracted_canonicals: List[str] = field(default_factory=list)
    specialty_scores: Dict[str, float] = field(default_factory=dict)
    asked_canonicals: List[str] = field(default_factory=list)
    questions_asked: int = 0
    confidence_0_1: float = 0.0
    recommended_specialty_id: Optional[int] = None
    top_conditions: List[Dict[str, Any]] = field(default_factory=list)
    envelope_type: Optional[str] = None
    stop_reason: Optional[str] = None

    duration_days: Optional[int] = None
    profile: Optional[Dict[str, Any]] = None
    risk_level: Optional[str] = None
    risk_score_0_1: Optional[float] = None


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


@dataclass
class PolicyConfig:
    max_questions: int = 5
    min_expected_gain: float = 0.08
    high_confidence_threshold: float = 0.85
    allow_same_day_to_continue: bool = True


@dataclass
class Config:
    synonyms: Dict[str, List[str]]
    specialty_keywords: Dict[str, List[str]]
    emergency_rules: Dict[str, Any]
    sameday_rules: Dict[str, Any]
    risk_rules: Dict[str, Any]
    policy: PolicyConfig


def load_config(config_dir: str = "config") -> Config:
    base = Path(config_dir)

    synonyms = _load_json(base / "synonyms_tr.json", default={})
    specialty_keywords = _load_json(base / "specialty_keywords_tr.json", default={})
    emergency_rules = _load_json(base / "emergency_rules.json", default={"rules": []})
    sameday_rules = _load_json(base / "sameday_rules.json", default={"rules": []})
    risk_rules = _load_json(base / "risk_rules.json", default={})
    policy_raw = _load_json(base / "triage_policy.json", default={})

    policy = PolicyConfig(
        max_questions=int(policy_raw.get("max_questions", 5)),
        min_expected_gain=float(policy_raw.get("min_expected_gain", 0.08)),
        high_confidence_threshold=float(policy_raw.get("high_confidence_threshold", 0.85)),
        allow_same_day_to_continue=bool(policy_raw.get("allow_same_day_to_continue", True)),
    )

    return Config(
        synonyms=synonyms,
        specialty_keywords=specialty_keywords,
        emergency_rules=emergency_rules,
        sameday_rules=sameday_rules,
        risk_rules=risk_rules,
        policy=policy,
    )


def canonical_extract(user_text: str, synonyms: Dict[str, List[str]]) -> List[str]:
    t = (user_text or "").lower()
    found: List[str] = []

    for canonical, syns in (synonyms or {}).items():
        if str(canonical).lower() in t:
            found.append(canonical)
            continue
        for s in syns or []:
            if str(s).lower() in t:
                found.append(canonical)
                break

    out: List[str] = []
    for item in found:
        if item not in out:
            out.append(item)
    return out


def score_specialties(canonicals: List[str], specialty_keywords: Dict[str, List[str]]) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    canon_set = {c.lower() for c in canonicals}

    for specialty_id, keywords in (specialty_keywords or {}).items():
        s = 0.0
        for keyword in keywords or []:
            if str(keyword).lower() in canon_set:
                s += 1.0
        if s > 0:
            scores[specialty_id] = s

    if scores:
        mx = max(scores.values())
        if mx > 0:
            for k in list(scores.keys()):
                scores[k] = scores[k] / mx

    return scores


def pick_top_specialty(scores: Dict[str, float]) -> Tuple[Optional[str], float]:
    if not scores:
        return None, 0.0
    best = max(scores.items(), key=lambda kv: kv[1])
    return best[0], float(best[1])


def _rule_hits(rule: Dict[str, Any], canonicals: List[str]) -> bool:
    cset = {c.lower() for c in canonicals}
    any_list = [x.lower() for x in rule.get("any", [])]
    all_list = [x.lower() for x in rule.get("all", [])]
    none_list = [x.lower() for x in rule.get("none", [])]

    any_ok = True if not any_list else any(x in cset for x in any_list)
    all_ok = True if not all_list else all(x in cset for x in all_list)
    none_ok = True if not none_list else all(x not in cset for x in none_list)
    return any_ok and all_ok and none_ok


def emergency_router(canonicals: List[str], emergency_rules: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for rule in emergency_rules.get("rules", []):
        if _rule_hits(rule, canonicals):
            return {
                "rule_id": rule.get("id"),
                "message": rule.get("message", "Acil durum belirtisi tespit edildi."),
                "action": rule.get("action", "call_emergency"),
            }
    return None


def sameday_router(canonicals: List[str], sameday_rules: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for rule in sameday_rules.get("rules", []):
        if _rule_hits(rule, canonicals):
            return {
                "rule_id": rule.get("id"),
                "message": rule.get("message", "Bugun bir uzmana gorunmeniz onerilir."),
                "action": rule.get("action", "see_today"),
            }
    return None


def expected_gain_next_question(ctx: TriageContext) -> Tuple[Optional[Dict[str, Any]], float]:
    if not ctx.extracted_canonicals:
        return (
            {
                "question_id": "q_any_other_symptoms",
                "text": "Ek belirti var mi? (ates, nefes darligi, siddetli agri, bayilma)",
                "expects": "free_text",
            },
            0.5,
        )

    if ctx.confidence_0_1 < 0.65:
        return (
            {
                "question_id": "q_duration",
                "text": "Bu sikayet kac gundur var ve siddeti artiyor mu?",
                "expects": "free_text",
            },
            0.15,
        )

    return None, 0.0


def build_result(
    ctx: TriageContext,
    same_day: Optional[Dict[str, Any]],
    risk_rules: Dict[str, Any],
) -> Dict[str, Any]:
    top_conditions = ctx.top_conditions or [
        {"name": "Belirsiz / degerlendirme gerekli", "score": max(ctx.confidence_0_1, 0.3)}
    ]

    risk = compute_risk(
        extracted_canonicals=ctx.extracted_canonicals,
        confidence_0_1=ctx.confidence_0_1,
        same_day=same_day,
        duration_days=ctx.duration_days,
        profile=ctx.profile,
        risk_rules=risk_rules or {},
    )

    ctx.risk_level = str(risk.get("level")) if isinstance(risk, dict) else None
    score = risk.get("score_0_1") if isinstance(risk, dict) else None
    ctx.risk_score_0_1 = float(score) if isinstance(score, (int, float)) else None

    trace = build_explanation_trace(
        extracted_canonicals=ctx.extracted_canonicals,
        confidence_0_1=ctx.confidence_0_1,
        stop_reason=ctx.stop_reason,
        same_day=same_day,
        duration_days=ctx.duration_days,
        profile=ctx.profile,
    )

    return {
        "probable_conditions": top_conditions,
        "recommended_specialty_id": ctx.recommended_specialty_id,
        "confidence_0_1": round(ctx.confidence_0_1, 3),
        "risk": risk,
        "explanation": "Deterministic semptom->brans skoru ve policy kurallariyla uretildi.",
        "explanation_trace": trace,
        "asked_canonicals": ctx.asked_canonicals or [],
    }


def log_session_event(ctx: TriageContext, event: str, extra: Optional[Dict[str, Any]] = None) -> None:
    """Persist session state + immutable event log when DB is configured."""
    try:
        from app.db import hash_ip, insert_event, upsert_session
    except Exception:
        return

    row = {
        "envelope_type": ctx.envelope_type,
        "stop_reason": ctx.stop_reason,
        "confidence_0_1": round(float(ctx.confidence_0_1 or 0.0), 4),
        "recommended_specialty_id": ctx.recommended_specialty_id,
        "extracted_canonicals": ctx.extracted_canonicals,
        "device_id": ctx.device_id,
        "ip_hash": hash_ip(ctx.ip),
        "meta": {
            "risk_level": ctx.risk_level,
            "risk_score_0_1": ctx.risk_score_0_1,
            "duration_days": ctx.duration_days,
        },
    }

    try:
        upsert_session(ctx.session_id, row)
        insert_event(
            ctx.session_id,
            event,
            {
                "extra": extra or {},
                "envelope_type": ctx.envelope_type,
                "stop_reason": ctx.stop_reason,
                "confidence_0_1": round(float(ctx.confidence_0_1 or 0.0), 4),
            },
        )
    except Exception:
        return


def _result_meta(t0: float, same_day: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "latency_ms": int((time.time() - t0) * 1000),
        "same_day": same_day,
    }


def orchestrate(
    user_text: str,
    session_id: str,
    config: Config,
    ip: Optional[str] = None,
    device_id: Optional[str] = None,
    profile: Optional[Dict[str, Any]] = None,
) -> Envelope:
    t0 = time.time()

    ctx = TriageContext(
        session_id=session_id,
        user_text=user_text,
        device_id=device_id,
        ip=ip,
        profile=profile,
    )

    log_session_event(ctx, "input_received", {"len": len(user_text or "")})

    ctx.duration_days = extract_duration_days(user_text or "")
    log_session_event(ctx, "duration_parsed", {"duration_days": ctx.duration_days})

    if ctx.profile is not None:
        log_session_event(ctx, "profile_received", {"profile": ctx.profile})

    ctx.extracted_canonicals = canonical_extract(user_text, config.synonyms)
    log_session_event(ctx, "canonicals_extracted", {"canonicals": ctx.extracted_canonicals})

    em = emergency_router(ctx.extracted_canonicals, config.emergency_rules)
    if em:
        ctx.envelope_type = EnvelopeType.EMERGENCY.value
        ctx.stop_reason = StopReason.EMERGENCY_DETECTED.value
        log_session_event(ctx, "emergency_triggered", em)
        return Envelope(
            envelope_type=EnvelopeType.EMERGENCY,
            payload=em,
            stop_reason=ctx.stop_reason,
            meta={"latency_ms": int((time.time() - t0) * 1000)},
        )

    sd = sameday_router(ctx.extracted_canonicals, config.sameday_rules)
    if sd:
        log_session_event(ctx, "same_day_triggered", sd)
        if not config.policy.allow_same_day_to_continue:
            ctx.envelope_type = EnvelopeType.SAME_DAY.value
            ctx.stop_reason = StopReason.SAME_DAY_RECOMMENDED.value
            return Envelope(
                envelope_type=EnvelopeType.SAME_DAY,
                payload=sd,
                stop_reason=ctx.stop_reason,
                meta={"latency_ms": int((time.time() - t0) * 1000)},
            )

    ctx.specialty_scores = score_specialties(ctx.extracted_canonicals, config.specialty_keywords)
    best_spec, best_score = pick_top_specialty(ctx.specialty_scores)

    ctx.recommended_specialty_id = int(best_spec) if best_spec and str(best_spec).isdigit() else None
    ctx.confidence_0_1 = float(best_score)
    log_session_event(ctx, "specialty_scored", {"best_spec": best_spec, "score": best_score})

    if ctx.questions_asked >= config.policy.max_questions:
        ctx.envelope_type = EnvelopeType.RESULT.value
        ctx.stop_reason = StopReason.QUESTION_BUDGET_EXCEEDED.value
        payload = build_result(ctx, sd, config.risk_rules)
        log_session_event(ctx, "stop_budget", {"max_questions": config.policy.max_questions})
        return Envelope(
            envelope_type=EnvelopeType.RESULT,
            payload=payload,
            stop_reason=ctx.stop_reason,
            meta=_result_meta(t0, sd),
        )

    if ctx.confidence_0_1 >= config.policy.high_confidence_threshold:
        ctx.envelope_type = EnvelopeType.RESULT.value
        ctx.stop_reason = StopReason.HIGH_CONFIDENCE.value
        payload = build_result(ctx, sd, config.risk_rules)
        log_session_event(ctx, "stop_high_conf", {"threshold": config.policy.high_confidence_threshold})
        return Envelope(
            envelope_type=EnvelopeType.RESULT,
            payload=payload,
            stop_reason=ctx.stop_reason,
            meta=_result_meta(t0, sd),
        )

    q, gain = expected_gain_next_question(ctx)
    if q is None or gain < config.policy.min_expected_gain:
        ctx.envelope_type = EnvelopeType.RESULT.value
        ctx.stop_reason = StopReason.MIN_EXPECTED_GAIN.value
        payload = build_result(ctx, sd, config.risk_rules)
        log_session_event(ctx, "stop_min_gain", {"gain": gain, "min": config.policy.min_expected_gain})
        return Envelope(
            envelope_type=EnvelopeType.RESULT,
            payload=payload,
            stop_reason=ctx.stop_reason,
            meta=_result_meta(t0, sd),
        )

    ctx.envelope_type = EnvelopeType.QUESTION.value
    ctx.questions_asked += 1
    log_session_event(ctx, "question_emitted", {"question_id": q.get("question_id"), "gain": gain})

    return Envelope(
        envelope_type=EnvelopeType.QUESTION,
        payload={
            "question": q,
            "expected_gain": round(gain, 3),
            "current_best_specialty_id": ctx.recommended_specialty_id,
            "current_confidence_0_1": round(ctx.confidence_0_1, 3),
        },
        stop_reason=None,
        meta={
            "latency_ms": int((time.time() - t0) * 1000),
            "same_day": sd,
        },
    )
