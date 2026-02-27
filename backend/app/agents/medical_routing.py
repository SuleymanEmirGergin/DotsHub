"""Medical Routing Agent V2 - _tr field parsing + specialty_scores context."""

import logging
from app.agents.base import BaseAgent
from app.prompts.system_prompts import MEDICAL_ROUTING_PROMPT
from app.models.schemas import RoutingOutput, DoctorReadySummary

logger = logging.getLogger(__name__)


class MedicalRoutingAgent(BaseAgent):
    """Recommends the appropriate medical specialty and urgency level."""

    name = "MedicalRouting"
    system_prompt = MEDICAL_ROUTING_PROMPT

    async def run(self, context: dict) -> RoutingOutput:
        result = await super().run(context)

        drs = result.get("doctor_ready_summary_tr", result.get("doctor_ready_summary", {}))
        doctor_summary = DoctorReadySummary(
            symptoms_tr=drs.get("symptoms_tr", drs.get("symptoms", [])),
            timeline_tr=drs.get("timeline_tr", drs.get("timeline", "")),
            qa_highlights_tr=drs.get("qa_highlights_tr", drs.get("qa_highlights", [])),
            risk_level=drs.get("risk_level", "LOW"),
        )

        return RoutingOutput(
            recommended_specialty_tr=result.get("recommended_specialty_tr", result.get("recommended_specialty", "")),
            urgency=result.get("urgency", "ROUTINE"),
            rationale_tr=result.get("rationale_tr", result.get("rationale", [])),
            emergency_watchouts_tr=result.get("emergency_watchouts_tr", result.get("emergency_watchouts", [])),
            doctor_ready_summary_tr=doctor_summary,
        )
