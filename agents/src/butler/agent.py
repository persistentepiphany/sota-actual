"""
Butler Agent — SOTA on Flare

The Butler Agent is the user-facing interface that:
1. Answers questions via RAG (Qdrant + Mem0)
2. Collects structured intent via slot filling
3. Posts jobs to FlareOrderBook
4. Monitors bids and helps user select best agent
5. Tracks job execution and retrieves deliveries

This is NOT a worker agent — it posts jobs but doesn't bid on them.
Uses OpenAI API directly for LLM interactions.
"""

import os
import json
import asyncio
import logging
from typing import Optional, Dict, Any, List

from ..shared.agent_runner import AgentRunner, LLMClient
from ..shared.tool_base import ToolManager
from ..shared.config import get_network, get_contract_addresses
from .tools import create_butler_tools

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
#  System Prompt
# ──────────────────────────────────────────────────────────────

BUTLER_SYSTEM_PROMPT = """
You are the Butler AI for SOTA — a decentralized agent marketplace on Flare.

### MANDATORY WORKFLOW
For EVERY user request, you must follow this sequence:

1. **CHECK KNOWLEDGE (RAG)**:
   - Call `rag_search` to see if you have context or if this is a simple question.
   - If the tool says "Match found", answer the user and STOP.
   - If the tool says "No match", PROCEED to Step 2 (Evaluate Intent).

2. **EVALUATE INTENT**:
   - **DECISION POINT**:
     - If the user clearly wants to perform a task (scrape, analyze, etc.) -> Call `fill_slots`.
     - If the user's intent is unclear or looks like a question you don't know -> ASK for clarification and STOP.

   - **IF CALLING `fill_slots`**:
     - If the tool says "Missing slots", ASK the user the questions provided and STOP.
     - If the tool says "Ready", SUMMARIZE the job and ASK for confirmation. STOP.

3. **POST JOB**:
   - ONLY after the user explicitly confirms "Yes, post it", call `post_job`.

4. **POLL BIDS**:
   - Immediately after posting, call `get_bids` to show initial status.
   - Present the bids to the user and STOP.

5. **AGENT COMMUNICATION** (after job is assigned):
   - Worker agents may request additional data during job execution.
   - Call `check_agent_requests` to see if any agent needs information.
   - If there are requests, relay the questions to the user and STOP.
   - When the user answers, call `answer_agent_request` to send the data back.
   - Call `get_agent_updates` periodically to get progress updates from
     the worker and share them with the user.

### STOPPING RULES
- If you generate a text response to the user, you MUST STOP.
- Do NOT loop. Do NOT call `fill_slots` repeatedly without user input.
"""


# ──────────────────────────────────────────────────────────────
#  Butler Agent
# ──────────────────────────────────────────────────────────────

class ButlerAgent:
    """
    Butler Agent for SOTA on Flare.

    This is the main user interface agent — it posts jobs but doesn't execute them.
    Uses OpenAI API for LLM-driven tool-calling.
    """

    def __init__(
        self,
        private_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
    ):
        """Initialize Butler Agent."""
        self.private_key = private_key or os.getenv("FLARE_PRIVATE_KEY")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.model = model

        if not self.private_key:
            raise ValueError("FLARE_PRIVATE_KEY required")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY required")

        # Create tool manager
        self.tool_manager = create_butler_tools()

        # Create LLM-backed agent runner
        self.agent_runner = AgentRunner(
            name="butler",
            description="Butler AI agent for SOTA — user-facing assistant",
            system_prompt=BUTLER_SYSTEM_PROMPT,
            max_steps=10,
            tools=self.tool_manager,
            llm=LLMClient(
                model=self.model,
                api_key=self.openai_api_key,
            ),
        )

        # Session state
        self.conversation_history: List[Dict[str, str]] = []
        self.current_job_id: Optional[int] = None
        self.current_slots: Dict[str, Any] = {}

        logger.info("🤖 Butler Agent initialized (model=%s)", self.model)

    async def chat(self, message: str, user_id: str = "cli_user") -> str:
        """
        Main chat interface — send message and get response.

        Args:
            message: User's message
            user_id: User identifier for personalization

        Returns:
            Butler's response
        """
        self.conversation_history.append({"role": "user", "content": message})

        try:
            response = await self.agent_runner.run_with_history(
                user_message=message,
                history=self.conversation_history[:-1],
            )

            self.conversation_history.append({"role": "assistant", "content": response})
            return response

        except Exception as e:
            error_msg = f"I encountered an error: {e}"
            logger.error("Chat error: %s", e)
            return error_msg

    async def post_job(
        self,
        description: str,
        tool: str,
        parameters: Dict[str, Any],
        deadline_hours: int = 24,
    ) -> Dict[str, Any]:
        """Post a job to FlareOrderBook."""
        try:
            result = await self.tool_manager.call(
                "post_job",
                json.dumps({
                    "description": description,
                    "tool": tool,
                    "parameters": parameters,
                    "deadline_hours": deadline_hours,
                }),
            )
            return json.loads(result)
        except Exception as e:
            logger.error("Failed to post job: %s", e)
            return {"error": str(e)}

    async def get_bids(self, job_id: Optional[int] = None) -> Dict[str, Any]:
        """Get bids for a job."""
        job_id = job_id or self.current_job_id
        if not job_id:
            return {"error": "No job ID provided"}
        try:
            result = await self.tool_manager.call("get_bids", json.dumps({"job_id": job_id}))
            return json.loads(result)
        except Exception as e:
            logger.error("Failed to get bids: %s", e)
            return {"error": str(e)}

    async def accept_bid(self, bid_id: int, job_id: Optional[int] = None) -> Dict[str, Any]:
        """Accept a bid."""
        job_id = job_id or self.current_job_id
        if not job_id:
            return {"error": "No job ID provided"}
        try:
            result = await self.tool_manager.call(
                "accept_bid", json.dumps({"job_id": job_id, "bid_id": bid_id})
            )
            return json.loads(result)
        except Exception as e:
            logger.error("Failed to accept bid: %s", e)
            return {"error": str(e)}

    async def check_status(self, job_id: Optional[int] = None) -> Dict[str, Any]:
        """Check job status."""
        job_id = job_id or self.current_job_id
        if not job_id:
            return {"error": "No job ID provided"}
        try:
            result = await self.tool_manager.call(
                "check_job_status", json.dumps({"job_id": job_id})
            )
            return json.loads(result)
        except Exception as e:
            logger.error("Failed to check status: %s", e)
            return {"error": str(e)}

    async def get_delivery(self, job_id: Optional[int] = None) -> Dict[str, Any]:
        """Get delivery results."""
        job_id = job_id or self.current_job_id
        if not job_id:
            return {"error": "No job ID provided"}
        try:
            result = await self.tool_manager.call(
                "get_delivery", json.dumps({"job_id": job_id})
            )
            return json.loads(result)
        except Exception as e:
            logger.error("Failed to get delivery: %s", e)
            return {"error": str(e)}


def create_butler_agent(
    private_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    model: str = "gpt-4o-mini",
) -> ButlerAgent:
    """Factory function to create Butler Agent."""
    return ButlerAgent(
        private_key=private_key,
        openai_api_key=openai_api_key,
        model=model,
    )
