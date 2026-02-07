"""
Hackathon Agent -- SOTA on Flare

The Hackathon Agent:
1. Listens for hackathon registration job events
2. Evaluates jobs and auto-bids via the JobBoard marketplace
3. Searches the internet for UPCOMING hackathons by time period,
   location, topics, and mode (online / in-person)
4. Scrapes event pages for detailed information
5. Returns formatted results to the Butler

Key design rule: NEVER return past hackathons.  All search and
display paths enforce an upcoming-only filter.
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
You are the Hackathon Agent for SOTA, specializing in finding UPCOMING
hackathons and coding competitions, AND automatically registering users
for them.

## GOLDEN RULE
Never show or return past hackathons.  Every result you present to the
user must have a start date >= today.  If a search returns any past
events, silently drop them.

## Gathering User Preferences
Before searching, you MUST collect these four inputs from the user
(via the Butler when running a marketplace job, or from the request
parameters when called directly):

1. **Time period** -- a date range (date_from / date_to).
   If the user says "next month" or "this summer", convert to YYYY-MM-DD.
   Default: today -> 3 months from now.

2. **Location** -- city, region, country, or "anywhere".
   Default: anywhere.

3. **Topics** -- comma-separated interests (e.g. "AI, blockchain, health").
   Default: none (all topics).

4. **Mode** -- "online", "in-person", or "both".
   Default: both.

If any of these are missing from the job description, request
clarification from the Butler (data_type="clarification") before
searching.  Do NOT guess -- ask.

## CRITICAL: Butler Communication (Marketplace Jobs)
When you are executing a job from the marketplace, you were selected by
the Butler on behalf of a user.

**ALWAYS start by requesting data from the Butler:**
1. Call `request_butler_data` with data_type="user_profile" to get the
   user's name, email, location, skills, and preferences.
2. If the job description lacks time period, location, topics, or mode,
   call `request_butler_data` with data_type="clarification" to ask.
3. Before submitting any registration, call `request_butler_data` with
   data_type="confirmation" to get user approval.
4. Use `notify_butler` to send progress updates.

## Search Workflow
1. Validate / collect: time period, location, topics, mode.
2. Call search_hackathons with all four parameters.
3. Optionally scrape_hackathon_details for the top results.
4. Call filter_hackathons if the user wants further narrowing.
5. Call format_hackathon_results for a clean summary.
6. Present results to the user.

## Registration Capabilities
5. **User Profile**: Use get_user_profile / save_user_profile.
6. **Detect Form**: Use detect_registration_form.
7. **Auto-Fill & Register**: Use auto_fill_and_register.
   ALWAYS use dry_run=true first.

## Registration Workflow
1. User says "register me for <hackathon>".
2. get_user_profile -> check completeness.
3. If incomplete, ask for missing fields (min: full_name, email).
4. detect_registration_form with the hackathon URL.
5. auto_fill_and_register with dry_run=true.
6. Ask user to confirm.
7. If confirmed, auto_fill_and_register with dry_run=false.
8. Report result.

## Safety Rules
- NEVER submit without user confirmation (always dry_run first).
- If the form requires fields the user hasn't provided, ask.
- If registration requires OAuth, inform the user you cannot automate
  it and suggest manual registration.

## Wallet & Bidding
8. Check balance and manage bids when needed.

Always be helpful and concise.

## FORMATTING RULES:
- NEVER use markdown syntax in your responses (no **bold**, no [text](url), no ## headings).
- Write plain text only. For links, just paste the URL directly.
- Keep output clean and readable for a chat interface.
"""


class HackathonAgent(AutoBidderMixin, BaseArchiveAgent):
    """
    Hackathon Agent for SOTA.

    Extends BaseArchiveAgent with internet search for upcoming hackathon
    events.  Mixes in AutoBidderMixin to participate in the JobBoard
    marketplace.
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
    bid_price_ratio = 0.70      # hackathon search is cheap -> bid 70%
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

        # Extract structured params from the job description
        # Description format: "hackathon_discovery: location=London, date_range=Feb 20-22, ..."
        location = ""
        date_from = ""
        date_to = ""
        keywords = ""
        if "location=" in job.description:
            try:
                parts = job.description.split(": ", 1)[-1]
                for param in parts.split(", "):
                    if "=" in param:
                        k, v = param.split("=", 1)
                        k = k.strip()
                        v = v.strip()
                        if k == "location":
                            location = v
                        elif k == "date_range":
                            date_from = v
                        elif k == "theme_technology_focus":
                            keywords = v.strip("[]'\"")
                        elif k == "online_or_in_person":
                            if v == "in_person":
                                keywords = (keywords + " in-person").strip()
            except Exception:
                pass

        if is_registration:
            logger.info("Executing hackathon registration for job #%s", job.job_id)
            prompt = (
                f"You are executing marketplace job #{job.job_id}.\n\n"
                f"Job description: {job.description}\n\n"
                f"Task: Register the user for a hackathon.\n\n"
                f"Workflow:\n"
                f"1. Request user profile from Butler (request_butler_data, "
                f"   data_type='user_profile', job_id='{job.job_id}')\n"
                f"2. Detect the registration form\n"
                f"3. Auto-fill with dry_run=true and notify Butler with results\n"
                f"4. Request confirmation from Butler (data_type='confirmation')\n"
                f"5. If confirmed, submit with dry_run=false\n"
                f"6. Notify Butler with final status (notify_butler status='completed')"
            )
        else:
            logger.info("Executing hackathon search for job #%s", job.job_id)
            prompt = (
                f"You are executing marketplace job #{job.job_id}.\n\n"
                f"Job description: {job.description}\n\n"
                f"## EXTRACTED SEARCH PARAMETERS (use these directly):\n"
                f"- Location: {location or 'any'}\n"
                f"- Date range: {date_from or 'upcoming'}\n"
                f"- Keywords: {keywords or 'any'}\n\n"
                f"## YOUR TASK — MANDATORY STEPS:\n"
                f"1. **IMMEDIATELY** call `search_hackathons` with "
                f"location=\"{location or 'worldwide'}\"" +
                (f", date_from/date_to covering {date_from}" if date_from else "") +
                (f", keywords=\"{keywords}\"" if keywords and keywords != "any" else "") +
                f".\n"
                f"   Do NOT skip this step. Do NOT wait for user profile data.\n"
                f"2. Call `notify_butler` with job_id='{job.job_id}', "
                f"status='in_progress', message='Searching for hackathons...'\n"
                f"3. If search returns results, call `format_hackathon_results`.\n"
                f"4. Call `notify_butler` with status='completed' and the results.\n\n"
                f"CRITICAL: You MUST call search_hackathons as your FIRST action. "
                f"The search parameters are already provided above — do not ask "
                f"the Butler for clarification. Proceed immediately with the search."
            )

        try:
            if self.llm_agent:
                result = await self.llm_agent.run(prompt)

                # If the LLM returned text without structured data,
                # do a direct search fallback
                if not is_registration and self._looks_like_no_results(result):
                    logger.warning("LLM returned no results — running direct search fallback")
                    fallback = await self._direct_search_fallback(location, date_from, keywords)
                    if fallback:
                        return {
                            "success": True,
                            "hackathons": fallback,
                            "job_id": job.job_id,
                            "source": "direct_fallback",
                        }

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
            # Last resort: try direct search even on error
            if not is_registration:
                try:
                    fallback = await self._direct_search_fallback(location, date_from, keywords)
                    if fallback:
                        return {
                            "success": True,
                            "hackathons": fallback,
                            "job_id": job.job_id,
                            "source": "error_fallback",
                        }
                except Exception:
                    pass
            return {
                "success": False,
                "error": str(e),
                "job_id": job.job_id,
            }

    @staticmethod
    def _looks_like_no_results(text: str) -> bool:
        """Check if the LLM response indicates no hackathons were found."""
        if not text:
            return True
        lower = text.lower()
        no_result_phrases = [
            "couldn't find",
            "could not find",
            "no hackathons",
            "no results",
            "unable to find",
            "didn't find",
            "no matching",
            "try different",
            "step limit",
        ]
        return any(phrase in lower for phrase in no_result_phrases)

    async def _direct_search_fallback(
        self, location: str, date_range: str, keywords: str
    ) -> list:
        """
        Bypass the LLM and call the search tool directly as a fallback.
        Also tries the event_finder scrapers.
        """
        from .tools import SearchHackathonsTool
        import json

        results = []

        # Try the OpenAI-powered search tool directly
        try:
            tool = SearchHackathonsTool()
            raw = await tool.execute(
                location=location or "worldwide",
                keywords=keywords if keywords and keywords != "any" else None,
            )
            data = json.loads(raw)
            if data.get("success") and data.get("hackathons"):
                results.extend(data["hackathons"])
        except Exception as e:
            logger.warning("Direct search tool failed: %s", e)

        # Also try event_finder scrapers
        if len(results) < 3:
            try:
                import sys
                import os
                agents_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                sys.path.insert(0, agents_dir)
                from event_finder import search_hackathons as scrape_search
                scraped = scrape_search(
                    query=f"hackathons in {location}" if location else "hackathons",
                    location=location,
                    num=5,
                )
                for s in scraped:
                    results.append({
                        "name": s.get("name", ""),
                        "location": s.get("location", ""),
                        "date_start": s.get("date", ""),
                        "date_end": s.get("date", ""),
                        "url": s.get("url", ""),
                        "description": s.get("description", ""),
                        "source": s.get("platform", "scraper"),
                    })
            except Exception as e:
                logger.warning("Event finder scraper failed: %s", e)

        return results


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

    print("SOTA Hackathon Agent")
    print("=" * 60)

    agent = await create_hackathon_agent()
    print(f"\nStatus: {agent.get_status()}")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        agent.stop()
        print("\nHackathon Agent stopped")


if __name__ == "__main__":
    asyncio.run(main())
