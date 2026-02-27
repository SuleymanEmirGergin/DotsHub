"""
Red-flag kontrol soruları: Belirli belirti setlerinde acil yönlendirme için
tek seferlik "Bu belirtilerden var mı?" sorusu.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_RED_FLAG_FILE = _DATA_DIR / "red_flag_questions.json"
_red_flag_list: List[Dict[str, Any]] = []


def _load() -> None:
    global _red_flag_list
    if _red_flag_list:
        return
    try:
        with open(_RED_FLAG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        _red_flag_list = data.get("questions", [])
        logger.info(f"Red-flag questions loaded: {len(_red_flag_list)}")
    except FileNotFoundError:
        logger.warning(f"red_flag_questions.json not found at {_RED_FLAG_FILE}")
    except json.JSONDecodeError as e:
        logger.warning(f"red_flag_questions.json invalid: {e}")


def get_red_flag_question(
    known_symptoms: Set[str],
    asked_red_flag_ids: Optional[Set[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    known_symptoms ile eşleşen ve daha önce sorulmamış bir red-flag sorusu döndürür.
    Returns: {"id", "question_tr", "answer_type", "if_yes_escalate", "reason_tr"} veya None
    """
    _load()
    asked = asked_red_flag_ids or set()
    known_lower = {s.lower().strip() for s in known_symptoms}
    for q in _red_flag_list:
        if q.get("id") in asked:
            continue
        when = q.get("when_canonical_any") or []
        when_set = {s.lower().strip() for s in when}
        if when_set and when_set & known_lower:
            return {
                "id": q.get("id"),
                "question_tr": q.get("question_tr", ""),
                "question_en": q.get("question_en"),
                "answer_type": q.get("answer_type", "yes_no"),
                "if_yes_escalate": q.get("if_yes_escalate"),
                "reason_tr": q.get("reason_tr", ""),
                "reason_en": q.get("reason_en"),
            }
    return None


def get_red_flag_by_id(red_flag_id: str) -> Optional[Dict[str, Any]]:
    """ID ile red-flag sorusu döndürür (reason_tr vb. için)."""
    _load()
    for q in _red_flag_list:
        if q.get("id") == red_flag_id:
            return q
    return None


def should_escalate_on_yes(answer_text: str) -> bool:
    """Kullanıcı cevabı 'evet' ise True (acil yönlendirme yapılmalı)."""
    if not answer_text:
        return False
    return answer_text.lower().strip() in ("evet", "var", "oldu", "oluyor", "yes", "var")
