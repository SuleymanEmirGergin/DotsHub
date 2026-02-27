"""Symptom Interpreter Agent V2 - _tr field parsing."""

import logging
from app.agents.base import BaseAgent
from app.prompts.system_prompts import SYMPTOM_INTERPRETER_PROMPT
from app.models.schemas import InterpreterOutput, SymptomItem, SymptomContext

logger = logging.getLogger(__name__)


class SymptomInterpreterAgent(BaseAgent):
    """Converts user's free-text symptoms into structured medical representation."""

    name = "SymptomInterpreter"
    system_prompt = SYMPTOM_INTERPRETER_PROMPT

    async def run(self, context: dict) -> InterpreterOutput:
        result = await super().run(context)

        symptoms = []
        for s in result.get("symptoms", []):
            symptoms.append(SymptomItem(
                name_tr=s.get("name_tr", s.get("name", "unknown")),
                onset_tr=s.get("onset_tr", s.get("onset")),
                duration_tr=s.get("duration_tr", s.get("duration")),
                severity_0_10=s.get("severity_0_10"),
                notes_tr=s.get("notes_tr", s.get("notes")),
            ))

        ctx = result.get("context", {})
        symptom_context = SymptomContext(
            age=ctx.get("age"),
            sex=ctx.get("sex"),
            pregnancy=ctx.get("pregnancy"),
            chronic_conditions_tr=ctx.get("chronic_conditions_tr", ctx.get("chronic_conditions", [])),
            medications_tr=ctx.get("medications_tr", ctx.get("medications", [])),
            allergies_tr=ctx.get("allergies_tr", ctx.get("allergies", [])),
        )

        return InterpreterOutput(
            chief_complaint_tr=result.get("chief_complaint_tr", result.get("chief_complaint", "")),
            symptoms=symptoms,
            negatives_tr=result.get("negatives_tr", result.get("negatives", [])),
            context=symptom_context,
        )
