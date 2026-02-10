"""Keywords patch generator — answer boosts for specialty_keywords_tr.json.

Given a tuning task of type SPECIALTY_CONFUSION, generates a JSON patch
that adjusts keyword weights to improve specialty discrimination.
"""

from __future__ import annotations
from typing import Any, Dict, List


def build_keywords_patch_from_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a specialty keywords patch from a SPECIALTY_CONFUSION task.
    
    Strategy:
    - Identify which specialty should be boosted
    - Find symptoms that are unique to top1 but not in top2
    - Create answer_boosts to increase their weight
    
    Args:
        task: Task dict from tuning_tasks table
        
    Returns:
        Patch dict with format:
        {
            "patch_type": "answer_boosts",
            "changes": [
                {
                    "action": "boost_keyword",
                    "specialty_id": "kardiyoloji",
                    "canonical": "göğüs ağrısı",
                    "boost_multiplier": 1.3
                },
                ...
            ]
        }
    """
    if task.get("task_type") != "SPECIALTY_CONFUSION":
        raise ValueError("Task must be SPECIALTY_CONFUSION type")
    
    payload = task.get("payload") or {}
    top1 = payload.get("top1") or {}
    top2 = payload.get("top2") or {}
    gap = payload.get("gap", 0)
    
    top1_id = top1.get("specialty_id")
    top2_id = top2.get("specialty_id")
    
    if not top1_id or not top2_id:
        return {
            "patch_type": "answer_boosts",
            "task_id": task.get("id"),
            "changes": [],
            "metadata": {"error": "Missing specialty IDs"}
        }
    
    changes: List[Dict[str, Any]] = []
    
    # Strategy: Boost top1's unique symptoms (heuristic: moderate boost)
    # In real scenario, we'd analyze which symptoms are discriminative
    # For now, create a placeholder boost
    
    # Example boost (requires domain knowledge to automate fully)
    boost_multiplier = 1.2 if gap < 0.10 else 1.15
    
    changes.append({
        "action": "boost_specialty",
        "specialty_id": top1_id,
        "reason": f"Confused with {top2_id} (gap: {gap:.3f})",
        "boost_multiplier": boost_multiplier,
        "apply_to": "all_keywords",  # or specific canonicals
    })
    
    return {
        "patch_type": "answer_boosts",
        "task_id": task.get("id"),
        "session_id": task.get("session_id"),
        "changes": changes,
        "metadata": {
            "total_changes": len(changes),
            "auto_generated": True,
            "requires_manual_review": True,  # High-impact changes
        }
    }


def apply_keywords_patch_to_file(patch: Dict[str, Any], keywords_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply a keywords patch to the in-memory specialty_keywords_tr.json data.
    
    Note: This is a simplified implementation. Real boost logic would be more sophisticated.
    
    Args:
        patch: Patch dict from build_keywords_patch_from_task
        keywords_data: Current specialty_keywords_tr.json content
        
    Returns:
        Updated keywords_data (deep copy)
    """
    import copy
    result = copy.deepcopy(keywords_data)
    
    # Keywords format: { "specialties": [ { "id": "...", "keywords": [...] } ] }
    specialties = result.get("specialties", [])
    
    for change in patch.get("changes", []):
        action = change.get("action")
        
        if action == "boost_specialty":
            specialty_id = change.get("specialty_id")
            boost = change.get("boost_multiplier", 1.0)
            
            # Find specialty
            for spec in specialties:
                if spec.get("specialty_id") == specialty_id or spec.get("id") == specialty_id:
                    # Add boost metadata (actual boosting happens in scoring logic)
                    spec["_boost_multiplier"] = boost
                    spec["_boost_reason"] = change.get("reason", "")
                    break
    
    result["specialties"] = specialties
    return result
