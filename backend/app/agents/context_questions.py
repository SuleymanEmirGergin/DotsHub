"""
Bağlam ve demografik sorular: Yaş, cinsiyet, hamilelik, kronik hastalık/ilaç.
Profil eksikse sohbet içinde sorulur; cevaplar profile yazılır.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CONTEXT_FILE = _DATA_DIR / "context_questions.json"
_questions: List[Dict[str, Any]] = []


def _load() -> None:
    global _questions
    if _questions:
        return
    try:
        with open(_CONTEXT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        _questions = sorted(data.get("questions", []), key=lambda q: q.get("order", 99))
        logger.info("Context questions loaded: %s", len(_questions))
    except FileNotFoundError:
        logger.warning("context_questions.json not found at %s", _CONTEXT_FILE)
    except json.JSONDecodeError as e:
        logger.warning("context_questions.json invalid: %s", e)


def _profile_missing(state: Any) -> Dict[str, bool]:
    """Hangi profil alanları eksik (soru sorulmalı)."""
    profile = getattr(state, "profile", None)
    missing = {"age": True, "sex": True, "pregnancy": True, "chronic": True}
    if profile:
        if getattr(profile, "age", None) is not None:
            missing["age"] = False
        if getattr(profile, "sex", None) and str(profile.sex).strip():
            missing["sex"] = False
        if getattr(profile, "pregnancy", None) is not None and str(profile.pregnancy).strip():
            missing["pregnancy"] = False
        if (getattr(profile, "chronic_conditions_tr", None) and len(profile.chronic_conditions_tr) > 0) or (
            getattr(profile, "medications_tr", None) and len(profile.medications_tr) > 0
        ):
            missing["chronic"] = False
    return missing


def _is_female(state: Any) -> bool:
    profile = getattr(state, "profile", None)
    if not profile or not getattr(profile, "sex", None):
        return False
    s = (profile.sex or "").lower().strip()
    return s in ("kadın", "kadin", "female", "f", "k")


def _has_any_symptom(state: Any, canonicals: List[str]) -> bool:
    known = getattr(state, "known_symptoms", set()) or set()
    known_lower = {s.lower().strip() for s in known}
    for c in canonicals:
        if c.lower().strip() in known_lower:
            return True
    return False


def get_next_context_question(state: Any, asked_context_ids: Optional[Set[str]] = None) -> Optional[Dict[str, Any]]:
    """
    Eksik profil alanı için sorulacak bir sonraki bağlam sorusu döndürür.
    Returns: {"id", "question_tr", "answer_type", "choices_tr"?, "profile_field"} veya None
    """
    _load()
    asked = asked_context_ids or set()
    missing = _profile_missing(state)

    for q in _questions:
        qid = q.get("id")
        if not qid or qid in asked:
            continue
        when = q.get("when_ask", "always")

        if when == "always":
            if qid == "age" and missing.get("age"):
                return _question_out(q)
            if qid == "sex" and missing.get("sex"):
                return _question_out(q)
            if qid == "chronic" and missing.get("chronic"):
                return _question_out(q)
            if qid == "pregnancy":
                continue
        if when == "when_female_and_relevant":
            if qid != "pregnancy":
                continue
            if not missing.get("pregnancy"):
                continue
            if not _is_female(state):
                continue
            symptoms = q.get("when_symptoms_any") or []
            if symptoms and not _has_any_symptom(state, symptoms):
                continue
            return _question_out(q)

    return None


def _question_out(q: Dict[str, Any]) -> Dict[str, Any]:
    out = {
        "id": q.get("id"),
        "question_tr": q.get("question_tr", ""),
        "question_en": q.get("question_en"),
        "answer_type": q.get("answer_type", "free_text"),
        "profile_field": q.get("profile_field"),
    }
    if q.get("choices_tr"):
        out["choices_tr"] = q["choices_tr"]
    if q.get("choices_en"):
        out["choices_en"] = q["choices_en"]
    return out


def get_context_question_by_id(context_id: str) -> Optional[Dict[str, Any]]:
    """ID ile bağlam sorusu döndürür."""
    _load()
    for q in _questions:
        if q.get("id") == context_id:
            return q
    return None


def parse_context_answer(context_id: str, answer_text: str) -> Dict[str, Any]:
    """
    Kullanıcı cevabını profil alanlarına yazılacak dict'e çevirir.
    Returns: {"age": int?}, {"sex": str}, {"pregnancy": str}, {"chronic_conditions_tr": list} vb.
    """
    answer_text = (answer_text or "").strip()
    out: Dict[str, Any] = {}

    if context_id == "age":
        age = _parse_age(answer_text)
        if age is not None:
            out["age"] = age
    elif context_id == "sex":
        sex = _parse_sex(answer_text)
        if sex:
            out["sex"] = sex
    elif context_id == "pregnancy":
        out["pregnancy"] = "evet" if _is_yes(answer_text) else "hayır"
    elif context_id == "chronic":
        if _is_yes(answer_text):
            out["chronic_conditions_tr"] = ["Var"]
        else:
            out["chronic_conditions_tr"] = []
    return out


def _parse_age(text: str) -> Optional[int]:
    if not text:
        return None
    numbers = re.findall(r"\d+", text)
    if numbers:
        n = int(numbers[0])
        if 0 <= n <= 120:
            return n
    return None


def _parse_sex(text: str) -> Optional[str]:
    if not text:
        return None
    t = text.lower().strip()
    if t in ("erkek", "e", "male", "m"):
        return "Erkek"
    if t in ("kadın", "kadin", "k", "female", "f"):
        return "Kadın"
    if t in ("belirtmek istemiyorum", "istemiyorum"):
        return "Belirtmek istemiyorum"
    return text.strip()


def _is_yes(text: str) -> bool:
    if not text:
        return False
    t = text.lower().strip()
    return t in ("evet", "var", "yes", "oldu", "oluyor")
