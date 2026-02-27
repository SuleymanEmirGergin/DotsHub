"""Base agent class for all medical pre-triage agents."""

import json
import logging
from typing import Optional

from app.core.llm_client import LLMClient

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base class for all agents in the triage pipeline."""

    name: str = "BaseAgent"
    system_prompt: str = ""

    def __init__(self, llm: Optional[LLMClient] = None):
        from app.core.llm_client import llm_client
        self.llm = llm or llm_client

    async def run(self, context: dict) -> dict:
        """Execute the agent with the given context.

        Args:
            context: Dictionary containing all relevant information for the agent

        Returns:
            Parsed JSON response from the LLM
        """
        logger.info(f"[{self.name}] Running with context keys: {list(context.keys())}")

        user_message = json.dumps(context, ensure_ascii=False, default=str)
        result = await self.llm.chat_json(
            system=self.system_prompt,
            user=user_message,
        )

        logger.info(f"[{self.name}] Completed successfully")
        return result
