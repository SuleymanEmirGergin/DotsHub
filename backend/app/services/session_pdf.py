"""PDF export for a triage session — admin-only.

Context
-------
Admins occasionally need to hand an auditor / regulator / patient
representative a snapshot of a single triage session: what the user
said, what the system asked, what the system recommended. The
dashboard's session-detail page renders this as HTML, but that's
awkward to email or print. This module produces a clean, printable
PDF from the same Supabase row shape.

Scope
-----
- Single page (target) / flows to a second page for long sessions.
- UTF-8 body (Turkish characters); DejaVu fonts are NOT bundled in
  fpdf2 by default, so we fall back to the built-in Helvetica and
  strip accents if the glyph isn't in the Latin-1 subset. If Turkish
  fidelity becomes critical, ship a DejaVu TTF in
  `backend/app/data/fonts/` and load it with `pdf.add_font(...)`.
- No PII beyond what's already in `triage_sessions` rows — no email,
  no auth token, no raw IP. The PDF is safe to share with the user
  whose session it represents.

Security
--------
Caller (`admin_v5.py::export_session_pdf`) checks `x-admin-key`
before invoking. This module does NOT re-check — it receives the
row dict and emits bytes.
"""
from __future__ import annotations

import unicodedata
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional

from fpdf import FPDF


# ─── Text helpers ───────────────────────────────────────────────────

def _safe_text(s: Any) -> str:
    """Collapse any input to a Latin-1-safe string.

    fpdf2's built-in Helvetica is Latin-1 only. Turkish letters like
    "ğ", "ş", "ı" fall inside Latin-1 but a few (e.g. some Unicode
    punctuation, emoji, curly quotes) don't — those get transliterated
    or stripped so the PDF renders instead of crashing with a
    FPDFException.

    Keeps the ASCII + most Latin-1-supplement range intact; drops the
    rest via NFKD decomposition + combining-mark filter.
    """
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)
    # Quick path: if already Latin-1-compatible, just return.
    try:
        s.encode("latin-1")
        return s
    except UnicodeEncodeError:
        pass
    # Decompose + drop combining chars that can't be encoded.
    normalised = unicodedata.normalize("NFKD", s)
    out_chars: List[str] = []
    for ch in normalised:
        try:
            ch.encode("latin-1")
            out_chars.append(ch)
        except UnicodeEncodeError:
            # Unknown glyph — replace with `?` so the PDF stays
            # readable even if some characters fade.
            out_chars.append("?")
    return "".join(out_chars)


def _format_created_at(raw: Optional[str]) -> str:
    """Format a Supabase ISO-8601 timestamp to a readable local form.

    Supabase returns strings like "2026-04-20T14:07:58.041+00:00".
    `fromisoformat` handles that on CPython 3.11+. We render the date
    in yyyy-mm-dd HH:MM UTC format — locale-neutral; an admin viewing
    the PDF can mentally offset for their zone.
    """
    if not raw:
        return "—"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(raw)[:19]


# ─── PDF assembly ──────────────────────────────────────────────────

class _SessionPDF(FPDF):
    """Custom FPDF subclass with header + footer for each page."""

    def __init__(self, session_id: str) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=18)
        self._session_id = session_id

    def header(self) -> None:  # noqa: D401 - fpdf lifecycle hook
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 8, _safe_text("Triaige — Session Export"), ln=True)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(100, 100, 100)
        self.cell(
            0,
            5,
            _safe_text(f"Session: {self._session_id}"),
            ln=True,
        )
        self.set_text_color(0, 0, 0)
        self.ln(4)

    def footer(self) -> None:  # noqa: D401 - fpdf lifecycle hook
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(130, 130, 130)
        self.cell(
            0,
            5,
            _safe_text(
                "Triaige pre-triage report. Not a medical diagnosis. "
                "Always consult a healthcare professional."
            ),
            align="C",
        )
        self.set_y(-8)
        self.cell(
            0,
            5,
            _safe_text(f"Page {self.page_no()} / {{nb}}"),
            align="C",
        )
        self.set_text_color(0, 0, 0)


def _reset_x(pdf: _SessionPDF) -> None:
    """Force the cursor to the left margin.

    Belt-and-suspenders after a previous multi_cell/set_x might have
    left the cursor shifted right; multi_cell(width=0) computes
    remaining-to-right-margin from the current X, so starting from
    l_margin guarantees max width.
    """
    pdf.set_x(pdf.l_margin)


def _section_title(pdf: _SessionPDF, text: str) -> None:
    _reset_x(pdf)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_fill_color(240, 240, 245)
    pdf.cell(0, 7, _safe_text(text), ln=True, fill=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.ln(1.5)


def _kv_row(pdf: _SessionPDF, key: str, value: str) -> None:
    """Render a `Key` + indented `Value` stacked on two lines.

    Previous attempt was a single-line layout (`Key: Value`) via
    cell() + multi_cell(), but fpdf2's multi_cell with the remainder-
    of-line width raised "Not enough horizontal space to render a
    single character" on specific font/margin combinations. Stacking
    is bulletproof: every multi_cell starts on a fresh line with the
    full content width (w=0), so wrap logic cannot exhaust space.
    Also friendlier to the eye for values that wrap (long specialty
    names, long stop_reasons).
    """
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5, _safe_text(key), ln=True)
    pdf.set_font("Helvetica", "", 10)
    # small left indent to visually group with the bold key above
    left_margin = pdf.l_margin
    pdf.set_x(left_margin + 4)
    pdf.multi_cell(0, 5, _safe_text(value))
    pdf.ln(0.5)


def _bullet_list(pdf: _SessionPDF, items: List[str]) -> None:
    if not items:
        _reset_x(pdf)
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(130, 130, 130)
        pdf.cell(0, 6, _safe_text("— no entries —"), ln=True)
        pdf.set_text_color(0, 0, 0)
        return
    pdf.set_font("Helvetica", "", 10)
    for item in items:
        _reset_x(pdf)
        pdf.multi_cell(0, 6, _safe_text(f"  • {item}"))


def build_session_pdf(detail: Dict[str, Any]) -> bytes:
    """Render the session-detail dict to a PDF byte string.

    Expects the shape returned by `admin_v5.get_session_detail`:
        { "session": {...row}, "events": [{...}], "feedback": [{...}] }

    Returns raw PDF bytes — caller sets the Content-Type +
    Content-Disposition on the Response.
    """
    session = detail.get("session") or {}
    events: List[Dict[str, Any]] = detail.get("events") or []
    feedback: List[Dict[str, Any]] = detail.get("feedback") or []

    pdf = _SessionPDF(session_id=str(session.get("session_id", "unknown")))
    pdf.alias_nb_pages()  # "Page X / N" footer needs this
    pdf.add_page()
    pdf.set_font("Helvetica", "", 10)

    # ─── Session meta ──────────────────────────────────────────────
    _section_title(pdf, "Session Metadata")
    _kv_row(pdf, "Created", _format_created_at(session.get("created_at")))
    _kv_row(pdf, "Envelope", session.get("envelope_type", "—"))
    _kv_row(pdf, "Urgency", session.get("urgency", "—"))
    _kv_row(pdf, "Specialty", session.get("recommended_specialty_tr", "—"))
    conf = session.get("confidence_0_1")
    conf_str = f"{float(conf):.2f}" if isinstance(conf, (int, float)) else "—"
    _kv_row(pdf, "Confidence", conf_str)
    _kv_row(pdf, "Stop reason", session.get("stop_reason", "—"))
    pdf.ln(2)

    # ─── User input / canonicals ───────────────────────────────────
    _section_title(pdf, "User Input")
    raw_text = session.get("input_text") or "—"
    pdf.multi_cell(0, 6, _safe_text(raw_text))
    pdf.ln(2)

    canonicals = session.get("extracted_canonicals") or []
    _section_title(pdf, "Extracted Canonicals")
    _bullet_list(pdf, [str(c) for c in canonicals])
    pdf.ln(2)

    # ─── Top conditions ────────────────────────────────────────────
    _section_title(pdf, "Top Conditions")
    conds = session.get("top_conditions") or []
    if not conds:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(130, 130, 130)
        pdf.cell(0, 6, _safe_text("— no conditions suggested —"), ln=True)
        pdf.set_text_color(0, 0, 0)
    else:
        for c in conds:
            if not isinstance(c, dict):
                continue
            label = c.get("disease_label") or c.get("label_tr") or "—"
            score = c.get("score_0_1")
            score_str = f"{float(score):.2f}" if isinstance(score, (int, float)) else "—"
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, _safe_text(f"{label}  ({score_str})"), ln=True)
            desc = c.get("disease_description_tr") or c.get("disease_description")
            if desc:
                pdf.set_font("Helvetica", "", 9)
                pdf.multi_cell(0, 5, _safe_text(desc))
            pdf.ln(1)
    pdf.ln(2)

    # ─── Q&A log ───────────────────────────────────────────────────
    _section_title(pdf, "Q&A Log")
    if not events:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(130, 130, 130)
        pdf.cell(0, 6, _safe_text("— no events recorded —"), ln=True)
        pdf.set_text_color(0, 0, 0)
    else:
        for ev in events:
            if not isinstance(ev, dict):
                continue
            role = ev.get("role") or ev.get("event_type") or "?"
            content = ev.get("content") or ev.get("question_tr") or ev.get("answer_value") or ""
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 5, _safe_text(f"[{role}]"), ln=True)
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 5, _safe_text(str(content)))
            pdf.ln(0.5)
    pdf.ln(2)

    # ─── Feedback ──────────────────────────────────────────────────
    _section_title(pdf, "User Feedback")
    if not feedback:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(130, 130, 130)
        pdf.cell(0, 6, _safe_text("— no feedback left —"), ln=True)
        pdf.set_text_color(0, 0, 0)
    else:
        for fb in feedback:
            if not isinstance(fb, dict):
                continue
            rating = fb.get("rating") or fb.get("up_down") or "?"
            comment = fb.get("comment_tr") or fb.get("comment") or ""
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, _safe_text(f"Rating: {rating}"), ln=True)
            if comment:
                pdf.set_font("Helvetica", "", 10)
                pdf.multi_cell(0, 6, _safe_text(str(comment)))
            pdf.ln(1)

    # fpdf2 >= 2.5 returns bytes from .output() when no name is given;
    # older versions return bytearray. Coerce either way to bytes
    # before handing to FastAPI's Response.
    buf = BytesIO()
    pdf.output(buf)
    return bytes(buf.getvalue())
