"""Synonyms patch generator — deterministic patch creation for synonyms_tr.json.

Given a tuning task of type KEYWORD_MISSING, generates a JSON patch
that can be applied to synonyms_tr.json to add missing synonym mappings.
"""

from __future__ import annotations
from typing import Any, Dict, List


def build_synonyms_patch_from_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a synonyms patch from a KEYWORD_MISSING task.
    
    Args:
        task: Task dict from tuning_tasks table
        
    Returns:
        Patch dict with format:
        {
            "patch_type": "synonyms",
            "changes": [
                {
                    "action": "add_synonym",
                    "canonical": "baş ağrısı",
                    "new_phrase": "kafa ağrısı"
                },
                ...
            ]
        }
    """
    if task.get("task_type") != "KEYWORD_MISSING":
        raise ValueError("Task must be KEYWORD_MISSING type")
    
    payload = task.get("payload") or {}
    missed_tokens = payload.get("missed_tokens") or []
    existing_canonicals = set(payload.get("existing_canonicals") or [])
    
    changes: List[Dict[str, Any]] = []
    
    # For each missed token, try to map to closest existing canonical
    for token_info in missed_tokens:
        if not isinstance(token_info, list) or len(token_info) < 2:
            continue
            
        token, count = token_info[0], token_info[1]
        token_lower = str(token).strip().lower()
        
        # Find best matching canonical (simple heuristic: first canonical that shares 3+ chars)
        best_canonical = None
        for c in sorted(existing_canonicals):
            c_lower = c.lower()
            # Simple substring matching
            if len(token_lower) >= 4 and (token_lower in c_lower or c_lower in token_lower):
                best_canonical = c
                break
        
        if not best_canonical and existing_canonicals:
            # Fallback: use first canonical (will require manual review)
            best_canonical = sorted(existing_canonicals)[0]
        
        if best_canonical:
            changes.append({
                "action": "add_synonym",
                "canonical": best_canonical,
                "new_phrase": token_lower,
                "confidence": "auto" if token_lower in best_canonical.lower() else "low",
            })
    
    return {
        "patch_type": "synonyms",
        "task_id": task.get("id"),
        "session_id": task.get("session_id"),
        "changes": changes,
        "metadata": {
            "total_changes": len(changes),
            "auto_generated": True,
        }
    }


def apply_synonyms_patch_to_file(patch: Dict[str, Any], synonyms_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply a synonyms patch to the in-memory synonyms_tr.json data.
    
    Args:
        patch: Patch dict from build_synonyms_patch_from_task
        synonyms_data: Current synonyms_tr.json content
        
    Returns:
        Updated synonyms_data (deep copy, does not mutate input)
    """
    import copy
    result = copy.deepcopy(synonyms_data)
    
    # Synonyms format: { "synonyms": [ { "canonical_symptom": "...", "phrases": [...] } ] }
    synonyms_list = result.get("synonyms", [])
    
    for change in patch.get("changes", []):
        if change.get("action") != "add_synonym":
            continue
            
        canonical = change.get("canonical", "")
        new_phrase = change.get("new_phrase", "")
        
        if not canonical or not new_phrase:
            continue
        
        # Find existing canonical entry
        found = False
        for syn_entry in synonyms_list:
            if syn_entry.get("canonical_symptom", "").lower() == canonical.lower():
                phrases = syn_entry.get("phrases", [])
                # Avoid duplicates
                if new_phrase not in [p.lower() for p in phrases]:
                    phrases.append(new_phrase)
                    syn_entry["phrases"] = phrases
                found = True
                break
        
        # If canonical not found, create new entry
        if not found:
            synonyms_list.append({
                "canonical_symptom": canonical,
                "phrases": [new_phrase],
            })
    
    result["synonyms"] = synonyms_list
    return result
