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
You are the Butler — a personal AI concierge for SOTA, a decentralized service platform on Flare.

You speak like a warm, professional personal assistant. NEVER use technical
marketplace jargon with the user. No mention of "posting jobs", "bids",
"workers", "slots", or "marketplace" — to the user you are simply
handling their request behind the scenes.

### MANDATORY WORKFLOW
For EVERY user request, follow this sequence:

1. **UNDERSTAND THE REQUEST**:
   - If the user wants something done (book, find hackathon, call, search, etc.) → call `fill_slots`.
   - If unclear → ask a natural clarifying question and STOP.
   - After `fill_slots`:
     - If missing info → ask the user naturally and STOP.
     - If all info gathered → summarize and ask: "Shall I go ahead?"
       STOP and wait for confirmation.

2. **EXECUTE — THIS IS THE MOST IMPORTANT STEP**:
   When the user confirms ("yes", "go ahead", "do it", "the details are accurate", etc.):

   YOU MUST IMMEDIATELY CALL THE `post_job` FUNCTION.

   Do NOT write JSON. Do NOT show parameters as text.
   You must make a FUNCTION CALL to `post_job` with these arguments:
   - description: a natural language description of the task
   - tool: the job type (e.g. "hackathon_registration", "hotel_booking", "call_verification")
   - parameters: an object with the gathered details

   ⚠️ VIOLATION: Outputting JSON like ```json {...}``` as text is FORBIDDEN.
   ⚠️ VIOLATION: Saying "I will now create the job request" without calling `post_job` is FORBIDDEN.
   ✅ CORRECT: Make a function call to `post_job` tool.

3. **REPORT BACK**:
   After `post_job` returns:
   - Success → "I've got someone working on it. I'll keep you updated."
   - No bids → "I wasn't able to find anyone available right now. Want me to try again?"
   - NEVER mention bids, workers, job IDs, USDC, or marketplace.

4. **AGENT COMMUNICATION** (after job is assigned):
   - Call `check_agent_requests` to see if a worker needs information.
   - Relay questions to user. When user answers, call `answer_agent_request`.
   - Call `get_agent_updates` for progress and share with user.

### TONE
- Friendly, concise, professional — like a hotel concierge.
- NEVER expose internal tool names, job IDs, or marketplace mechanics.
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

    async def chat(self, message: str, user_id: str = "cli_user") -> dict:
        """
        Main chat interface — send message and get response.
        Includes safety net: if LLM outputs JSON instead of calling post_job,
        we detect it and auto-call post_job.

        Returns dict with:
          - "response": str — friendly text for user
          - "job_posted": dict|None — structured job data if post_job was called
        """
        self.conversation_history.append({"role": "user", "content": message})

        try:
            result = await self.agent_runner.run_with_history(
                user_message=message,
                history=self.conversation_history[:-1],
            )

            response = result["response"]
            tool_results = result.get("tool_results", [])

            # ── Extract job posting data from tool results ───
            job_posted = None
            for tr in tool_results:
                if tr["tool"] == "post_job":
                    try:
                        job_data = json.loads(tr["result"])
                        if job_data.get("success"):
                            job_posted = job_data
                            logger.info("📦 post_job result captured for frontend: job #%s", job_data.get("on_chain_job_id"))
                    except (json.JSONDecodeError, TypeError):
                        pass

            # ── Safety net: detect JSON in text response ─────────
            if not job_posted:
                response, job_posted = await self._intercept_json_job(response)

            self.conversation_history.append({"role": "assistant", "content": response})
            return {"response": response, "job_posted": job_posted}

        except Exception as e:
            error_msg = f"I encountered an error: {e}"
            logger.error("Chat error: %s", e)
            return {"response": error_msg, "job_posted": None}

    async def _intercept_json_job(self, response: str) -> tuple:
        """
        Safety net: if the LLM returned a text response containing JSON
        that looks like a job definition, auto-call post_job and return
        a user-friendly message instead.

        Returns (response_text, job_posted_data_or_None)
        """
        import re

        # Look for JSON block in the response
        json_match = re.search(r'```(?:json)?\s*({[^`]+})\s*```', response)
        if not json_match:
            # Try bare JSON object
            json_match = re.search(r'(\{[\s\S]*"(?:job|tool|description|location|theme)"[\s\S]*\})', response)
        if not json_match:
            return response, None

        try:
            data = json.loads(json_match.group(1))
        except (json.JSONDecodeError, IndexError):
            return response, None

        # Check if it looks like a job definition
        job_keys = {"job", "tool", "description", "location", "theme", "type",
                    "parameters", "date_range", "online_or_in_person", "phone_number"}
        if not (set(data.keys()) & job_keys):
            return response, None

        logger.info("🔄 Intercepted JSON job in text response — auto-posting to marketplace")
        print("🔄 SAFETY NET: LLM output JSON as text — auto-routing to post_job")

        # Build post_job arguments from the intercepted JSON
        tool_type = data.get("job", data.get("tool", "generic"))
        description_parts = []
        for k, v in data.items():
            if k not in ("job", "tool"):
                description_parts.append(f"{k}: {v}")
        description = data.get("description", "; ".join(description_parts))

        # Parameters = everything except "job" and "description"
        parameters = {k: v for k, v in data.items() if k not in ("job", "tool", "description")}

        try:
            result = await self.tool_manager.call(
                "post_job",
                json.dumps({
                    "description": description,
                    "tool": tool_type,
                    "parameters": parameters,
                }),
            )
            result_data = json.loads(result)

            if result_data.get("success"):
                winning = result_data.get("winning_bid", {})
                eta = winning.get("eta_seconds", 120)
                return (
                    f"I've found a specialist and they're working on your request now. "
                    f"Estimated time: about {eta // 60} minutes. "
                    f"I'll keep you posted on the progress!"
                ), result_data
            else:
                return (
                    "I wasn't able to find anyone available at the moment. "
                    "Would you like me to try again in a few minutes?"
                ), None
        except Exception as e:
            logger.error("Auto post_job failed: %s", e)
            return (
                "I'm setting that up for you now. "
                "Give me a moment to find the best option."
            ), None

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
