"""
Oturum sonucunun yapılandırılmış metin olarak dışa aktarılması.
E-posta özeti ile uyumlu; PDF için aynı metin kullanılabilir.
"""

from __future__ import annotations

from typing import Any


def build_export_text(payload: dict[str, Any], locale: str = "tr-TR") -> str:
    """
    RESULT payload'dan düz metin özet üretir.
    İndirilebilir .txt veya e-posta gövdesi olarak kullanılabilir.
    """
    lines: list[str] = []

    if locale and locale.strip().lower().startswith("en"):
        lines.append("Triage session summary")
        lines.append("")
        spec = payload.get("recommended_specialty") or {}
        lines.append(f"Recommended specialty: {spec.get('name_tr', spec.get('id', '-'))}")
        lines.append(f"Urgency: {payload.get('urgency', 'ROUTINE')}")
        lines.append("")
        sentence = payload.get("doctor_ready_summary_sentence_tr") or ""
        if sentence:
            lines.append("Summary for the doctor:")
            lines.append(sentence)
        else:
            for s in payload.get("doctor_ready_summary_tr") or []:
                lines.append(s)
        lines.append("")
        for cond in payload.get("top_conditions") or []:
            lines.append(f"  - {cond.get('disease_label', '')} ({cond.get('score_0_1', 0)})")
        lines.append("")
        lines.append("Safety notes:")
        for note in payload.get("safety_notes_tr") or []:
            lines.append(f"  - {note}")
    else:
        lines.append("Triaj oturum özeti")
        lines.append("")
        spec = payload.get("recommended_specialty") or {}
        lines.append(f"Önerilen branş: {spec.get('name_tr', spec.get('id', '-'))}")
        lines.append(f"Aciliyet: {payload.get('urgency', 'ROUTINE')}")
        lines.append("")
        sentence = payload.get("doctor_ready_summary_sentence_tr") or ""
        if sentence:
            lines.append("Doktora söyleyebileceğiniz özet:")
            lines.append(sentence)
        else:
            lines.append("Doktora söyleyebileceğiniz özet:")
            for s in payload.get("doctor_ready_summary_tr") or []:
                lines.append(f"  {s}")
        lines.append("")
        lines.append("Olası durumlar:")
        for cond in payload.get("top_conditions") or []:
            lines.append(f"  - {cond.get('disease_label', '')} (%{int((cond.get('score_0_1') or 0) * 100)})")
        lines.append("")
        lines.append("Uyarılar:")
        for note in payload.get("safety_notes_tr") or []:
            lines.append(f"  - {note}")

    return "\n".join(lines)
