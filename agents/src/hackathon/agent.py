"""
Hackathon Agent — SOTA on Flare

The Hackathon Agent:
1. Listens for hackathon registration job events
2. Evaluates jobs and auto-bids via the JobBoard marketplace
3. Searches the internet for hackathons by date & location (OpenAI)
4. Scrapes event pages for detailed information
5. Returns formatted results to the Butler
"""

import os
import asyncio
import logging
from typing import Optional

from ..shared.agent_runner import AgentRunner, LLMClient
from ..shared.tool_base import ToolManager

from ..shared.base_agent import BaseArchiveAgent, AgentCapability, ActiveJob
from ..shared.auto_bidder import AutoBidderMixin
from ..shared.config import JobType, JOB_TYPE_LABELS
from ..shared.events import JobPostedEvent
from ..shared.wallet_tools import create_wallet_tools
from ..shared.bidding_tools import create_bidding_tools
from ..shared.butler_comms import create_butler_comm_tools

from .tools import create_hackathon_tools
from .registration_tools import create_registration_tools

logger = logging.getLogger(__name__)


HACKATHON_SYSTEM_PROMPT = """
You are the Hackathon Agent for SOTA, specializing in finding hackathons and
coding competitions, AND automatically registering users for them.

## CRITICAL: Butler Communication (Marketplace Jobs)
When you are executing a job from the marketplace, you were selected by the
Butler on behalf of a user.  You may NOT have all the info you need.

**ALWAYS start by requesting data from the Butler:**
1. Call `request_butler_data` with data_type="user_profile" to get the user's
   name, email, location, skills, and preferences.
2. If the job description lacks specifics (date, location, keywords), call
   `request_butler_data` with data_type="clarification" to ask the Butler.
3. Before submitting any registration, call `request_butler_data` with
   data_type="confirmation" to get user approval.
4. Use `notify_butler` to send progress updates so the user knows what's
   happening (e.g. "Found 5 hackathons near London").

## Search Capabilities:
1. **Search Hackathons**: Use search_hackathons to find upcoming events
   near a specific location and date range.

2. **Scrape Details**: Use scrape_hackathon_details to get detailed info
   from a hackathon event page.

3. **Filter**: Use filter_hackathons to narrow results.

4. **Format**: Use format_hackathon_results for a clean summary.

## Registration Capabilities:
5. **User Profile**: Use get_user_profile to retrieve the user's stored
   registration info (name, email, skills, etc.).
   Use save_user_profile to store info the user provides.

6. **Detect Form**: Use detect_registration_form to scan a hackathon page
   and identify all form fields (inputs, selects, checkboxes, etc.).

7. **Auto-Fill & Register**: Use auto_fill_and_register to fill the form
   with the user's profile and submit it.
   ALWAYS use dry_run=true first so the user can confirm before submitting.

## Marketplace Job Workflow (when selected via JobBoard):
1. **Get user data**: Call `request_butler_data(data_type="user_profile")`
   to get the user's profile from the Butler.
2. **Clarify if needed**: If the job description is vague, call
   `request_butler_data(data_type="clarification")` asking for specifics.
3. **Notify progress**: Call `notify_butler(status="in_progress")` as you
   work through the search/registration steps.
4. **Search & process**: Use the search/scrape/filter/format tools.
5. **Send results**: Call `notify_butler(status="partial_result")` with
   the search results so the user can see them.
6. **Confirm before action**: For registration, call
   `request_butler_data(data_type="confirmation")` before submitting.
7. **Final update**: Call `notify_butler(status="completed")` when done.

## Registration Workflow:
1. User says "register me for <hackathon>" or similar.
2. Call get_user_profile to see what info you already have.
3. If profile is incomplete, ask the user for missing required fields
   (at minimum: full_name, email).  Save with save_user_profile.
4. Call detect_registration_form with the hackathon URL.
5. Call auto_fill_and_register with dry_run=true — report what was filled.
6. Ask the user to confirm.  If confirmed, call auto_fill_and_register
   with dry_run=false to actually submit.
7. Report the result (success / failure / confirmation page).

## Safety Rules:
- NEVER submit without user confirmation (always dry_run first).
- If the form requires fields the user hasn't provided, ask for them.
- If registration requires OAuth (Google/GitHub login), inform the user
  you cannot automate OAuth and suggest they register manually.

8. **Wallet & Bidding**: Check balance and manage bids when needed.

Always be helpful and concise.
"""


class HackathonAgent(AutoBidderMixin, BaseArchiveAgent):
    """
    Hackathon Agent for SOTA.

    Extends BaseArchiveAgent with internet search for hackathon events.
    Mixes in AutoBidderMixin to participate in the JobBoard marketplace.
    """

    agent_type = "hackathon"
    agent_name = "SOTA Hackathon Agent"
    capabilities = [
        AgentCapability.DATA_ANALYSIS,
    ]
    supported_job_types = [
        JobType.HACKATHON_REGISTRATION,
    ]

    # Bidding configuration
    min_profit_margin = 0.10    # 10% margin
    max_concurrent_jobs = 5
    auto_bid_enabled = True
    bid_price_ratio = 0.70      # hackathon search is cheap → bid 70%
    bid_eta_seconds = 120       # ~2 min to search & format

    async def _create_llm_agent(self) -> AgentRunner:
        """Create agent runner with hackathon + registration + butler comm + wallet + bidding tools."""
        all_tools: list = []
        all_tools.extend(create_hackathon_tools())
        all_tools.extend(create_registration_tools())
        all_tools.extend(create_butler_comm_tools())
        all_tools.extend(create_wallet_tools(self.wallet))
        all_tools.extend(create_bidding_tools(self._contracts, self.agent_type))

        model_name = os.getenv("LLM_MODEL", "gpt-4o-mini")

        return AgentRunner(
            name="hackathon",
            description="Hackathon search & registration agent for SOTA on Flare",
            system_prompt=HACKATHON_SYSTEM_PROMPT,
            max_steps=15,
            tools=ToolManager(all_tools),
            llm=LLMClient(model=model_name),
        )

    def get_bidding_prompt(self, job: JobPostedEvent) -> str:
        """Not used for auto-bid; kept for compatibility."""
        job_type_label = JOB_TYPE_LABELS.get(JobType(job.job_type), "Unknown")
        budget_flr = job.budget / 10**18
        return (
            f"Auto-bid mode: will place bid on job {job.job_id} "
            f"({job_type_label}) budget {budget_flr} C2FLR."
        )

    async def execute_job(self, job: ActiveJob) -> dict:
        """
        Execute a hackathon job (search or registration).

        When executing a marketplace job, the agent communicates with
        the Butler to get user data and send progress updates.
        """
        desc_lower = job.description.lower()
        is_registration = any(
            kw in desc_lower for kw in ["register", "sign up", "sign me up", "enroll", "rsvp"]
        )

        # Common header: instruct the agent to communicate with Butler
        butler_header = (
            f"You are executing marketplace job #{job.job_id}.\n"
            f"Budget: {job.budget / 1_000_000:.2f} USDC\n\n"
            f"IMPORTANT: This job came from the marketplace via the Butler.\n"
            f"You MUST communicate with the Butler to get user data.\n\n"
            f"Step 1: Call `request_butler_data` with data_type='user_profile', "
            f"job_id='{job.job_id}' to get the user's profile.\n"
            f"Step 2: Call `notify_butler` with job_id='{job.job_id}', "
            f"status='in_progress' to keep the user informed.\n\n"
        )

        if is_registration:
            logger.info("📝 Executing hackathon registration for job #%s", job.job_id)
            prompt = (
                butler_header
                + f"Job description: {job.description}\n\n"
                f"Task: Register the user for a hackathon.\n\n"
                f"Workflow:\n"
                f"1. Request user profile from Butler (request_butler_data)\n"
                f"2. Detect the registration form\n"
                f"3. Auto-fill with dry_run=true and notify Butler with results\n"
                f"4. Request confirmation from Butler (data_type='confirmation')\n"
                f"5. If confirmed, submit with dry_run=false\n"
                f"6. Notify Butler with final status (notify_butler status='completed')"
            )
        else:
            logger.info("🔍 Executing hackathon search for job #%s", job.job_id)
            prompt = (
                butler_header
                + f"Job description: {job.description}\n\n"
                f"Task: Search for hackathons matching the request.\n\n"
                f"Workflow:\n"
                f"1. Request user profile/preferences from Butler for location hints\n"
                f"2. If the description is vague about dates/location, request "
                f"   clarification from Butler (data_type='clarification')\n"
                f"3. Search for hackathons, scrape details, format summary\n"
                f"4. Notify Butler with results (notify_butler status='partial_result')\n"
                f"5. Notify Butler with final status (notify_butler status='completed')"
            )

        try:
            if self.llm_agent:
                result = await self.llm_agent.run(prompt)
                return {
                    "success": True,
                    "result": result,
                    "job_id": job.job_id,
                }
            else:
                return {
                    "success": False,
                    "error": "LLM agent not initialized",
                    "job_id": job.job_id,
                }
        except Exception as e:
            logger.error("Hackathon job #%s failed: %s", job.job_id, e)
            return {
                "success": False,
                "error": str(e),
                "job_id": job.job_id,
            }


# ─── Factory ──────────────────────────────────────────────────

async def create_hackathon_agent() -> HackathonAgent:
    """Factory function to create and initialise a Hackathon Agent."""
    agent = HackathonAgent()
    await agent.initialize()
    agent.register_on_board()       # register on JobBoard marketplace
    return agent


async def main():
    """Run the Hackathon Agent standalone."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("🏆 SOTA Hackathon Agent")
    print("=" * 60)

    agent = await create_hackathon_agent()
    print(f"\n📊 Status: {agent.get_status()}")

    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        agent.stop()
        print("\n👋 Hackathon Agent stopped")


if __name__ == "__main__":
    asyncio.run(main())
