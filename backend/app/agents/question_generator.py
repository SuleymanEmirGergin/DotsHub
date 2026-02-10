"""Question Generator Agent V2 - _tr field parsing.

NOTE (V3): This agent is now used as an LLM fallback when the deterministic
QuestionSelector (question_selector.py) returns None (no suitable discriminative
question found in the bank). The orchestrator handles the routing decision.
"""

import logging
from app.agents.base import BaseAgent
from app.prompts.system_prompts import QUESTION_GENERATOR_PROMPT
from app.models.schemas import QuestionOutput

logger = logging.getLogger(__name__)


class QuestionGeneratorAgent(BaseAgent):
    """Generates the single best next question to reduce diagnostic uncertainty."""

    name = "QuestionGenerator"
    system_prompt = QUESTION_GENERATOR_PROMPT

    async def run(self, context: dict) -> QuestionOutput:
        result = await super().run(context)

        return QuestionOutput(
            question_tr=result.get("question_tr", result.get("question", "")),
            answer_type=result.get("answer_type", "free_text"),
            choices_tr=result.get("choices_tr", result.get("choices", [])),
            why_this_question_tr=result.get("why_this_question_tr", result.get("why_this_question", "")),
            stop=result.get("stop", False),
        )
