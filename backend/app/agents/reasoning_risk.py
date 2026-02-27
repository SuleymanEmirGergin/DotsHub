"""Reasoning & Risk Agent V2 - _tr field parsing."""

import logging
from app.agents.base import BaseAgent
from app.prompts.system_prompts import REASONING_RISK_PROMPT
from app.models.schemas import ReasoningOutput, CandidateCondition

logger = logging.getLogger(__name__)


class ReasoningRiskAgent(BaseAgent):
    """Produces ranked list of plausible conditions with risk assessment."""

    name = "ReasoningRisk"
    system_prompt = REASONING_RISK_PROMPT

    async def run(self, context: dict) -> ReasoningOutput:
        result = await super().run(context)

        candidates = []
        for c in result.get("candidates", []):
            candidates.append(CandidateCondition(
                label_tr=c.get("label_tr", c.get("label", "")),
                probability_0_1=c.get("probability_0_1", 0.0),
                supporting_evidence_tr=c.get("supporting_evidence_tr", c.get("supporting_evidence", [])),
                contradicting_evidence_tr=c.get("contradicting_evidence_tr", c.get("contradicting_evidence", [])),
            ))

        return ReasoningOutput(
            risk_level=result.get("risk_level", "LOW"),
            candidates=candidates,
            confidence_notes_tr=result.get("confidence_notes_tr", result.get("confidence_notes", "")),
            need_more_info_tr=result.get("need_more_info_tr", result.get("need_more_info", [])),
        )
