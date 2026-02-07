"""
CV Magic Agent — SOTA on Flare

The CV Magic Agent:
1. Listens for job scouring requests
2. Evaluates jobs and decides whether to bid
3. Executes accepted jobs by searching job boards
4. Returns scored/filtered job listings based on user CVs
"""

import os
import asyncio
import logging
import json
import base64
from typing import Optional, Dict, Any

from pydantic import Field

from ..shared.agent_runner import AgentRunner, LLMClient
from ..shared.tool_base import ToolManager

from ..shared.base_agent import BaseArchiveAgent, AgentCapability, ActiveJob, BidDecision
from ..shared.auto_bidder import AutoBidderMixin
from ..shared.config import JobType, JOB_TYPE_LABELS
from ..shared.events import JobPostedEvent
from ..shared.wallet_tools import create_wallet_tools
from ..shared.bidding_tools import create_bidding_tools

from .tools import create_cv_magic_tools

logger = logging.getLogger(__name__)


CV_MAGIC_SYSTEM_PROMPT = """
You are the CV Magic Agent for SOTA, specializing in job scouring on Flare.

Your capabilities:
1. **Job Scouring**: Use scour_jobs to:
   - Accept CV/resume documents (base64 encoded)
   - Search multiple job boards (LinkedIn, Indeed, etc.)
   - Score and filter jobs by relevance to the candidate
   - Return detailed job listings with application tips

2. **Profile Extraction**: Use extract_profile to:
   - Parse CV/resume documents
   - Extract skills, experience, education
   - Identify key projects and links

3. **Job Details**: Use get_job_details to:
   - Fetch full details from a job listing URL
   - Get complete descriptions and requirements

4. **Delivery**: After job scouring:
   - Format results as structured JSON
   - Include relevance scores and tips
   - Submit delivery with proof hash

5. **Wallet & Bidding**: Check balance and manage bids.

WORKFLOW:
1. Receive job scouring request with CV document and preferences
2. Extract profile from CV using extract_profile
3. Search job boards using scour_jobs with extracted profile
4. Return scored job listings with relevance and tips
5. Submit delivery with results

Based on the current progress, decide the next action:
- To scour jobs: use scour_jobs with document and preferences
- To extract profile only: use extract_profile
- For job details: use get_job_details
- Finally: submit_delivery with proof hash
"""


class CVMagicAgent(AutoBidderMixin, BaseArchiveAgent):
    """
    CV Magic Agent for SOTA.
    
    Extends BaseArchiveAgent with job scouring capabilities.
    Mixes in AutoBidderMixin to participate in the JobBoard marketplace.
    """
    
    agent_type = "cv_magic"
    agent_name = "SOTA CV Magic Agent"
    capabilities = [
        AgentCapability.WEB_SCRAPING,
    ]
    # Specialize in job scouring
    supported_job_types = [JobType.JOB_SCOURING]
    
    # Bidding configuration
    min_profit_margin = 0.15  # 15% margin
    max_concurrent_jobs = 5   # Can handle multiple concurrent scours
    auto_bid_enabled = True
    bid_price_ratio = 0.85    # CV Magic bids 85% of budget
    bid_eta_seconds = 600     # 10 minute ETA for job scouring
    
    async def _create_llm_agent(self) -> AgentRunner:
        """Create agent runner for tooling (bidding is auto)."""
        all_tools = []
        all_tools.extend(create_cv_magic_tools())
        all_tools.extend(create_wallet_tools(self.wallet))
        all_tools.extend(create_bidding_tools(self._contracts, self.agent_type))

        model_name = os.getenv("LLM_MODEL", "gpt-4o-mini")

        return AgentRunner(
            name="cv_magic",
            description="CV Magic Agent for job scouring tasks",
            system_prompt=CV_MAGIC_SYSTEM_PROMPT,
            max_steps=20,
            tools=ToolManager(all_tools),
            llm=LLMClient(model=model_name),
        )

    def get_bidding_prompt(self, job: JobPostedEvent) -> str:
        """Not used for auto-bid; kept for compatibility."""
        job_type_label = JOB_TYPE_LABELS.get(JobType(job.job_type), "Unknown")
        budget_usdc = job.budget / 1_000_000
        return f"Auto-bid mode: will place bid on job {job.job_id} ({job_type_label}) budget {budget_usdc} USDC."

    async def _evaluate_and_bid(self, job: JobPostedEvent):
        """
        Auto-bid on job scouring requests.
        """
        if len(self.active_jobs) >= self.max_concurrent_jobs:
            logger.warning("At capacity, skipping job %s", job.job_id)
            return

        # Only bid on job scouring type
        if job.job_type != JobType.JOB_SCOURING:
            logger.debug("Skipping non-scouring job %s (type: %s)", job.job_id, job.job_type)
            return

        decision = BidDecision(
            should_bid=True,
            proposed_amount=max(int(job.budget * self.bid_price_ratio), 500_000),  # Min 0.5 USDC
            estimated_time=self.bid_eta_seconds,
            reasoning=f"CV Magic agent bidding on job scouring task {job.job_id}"
        )

        await self._place_bid(job, decision)

    async def execute_job(self, job: ActiveJob) -> Dict[str, Any]:
        """
        Execute a job scouring task.
        
        Job parameters expected:
        - document_base64: Base64-encoded CV/resume
        - document_filename: Original filename
        - job_title: Target job title
        - location: Target location
        - Additional preferences (seniority, remote, etc.)
        """
        params = job.parameters or {}
        
        logger.info("Executing job scouring task %s with params: %s", 
                   job.job_id, list(params.keys()))

        # Validate required parameters
        required = ["document_base64", "job_title", "location"]
        missing = [k for k in required if not params.get(k)]
        if missing:
            return {
                "success": False,
                "error": f"Missing required parameters: {missing}"
            }

        try:
            # Use the scour_jobs tool
            from .tools import ScourJobsTool
            tool = ScourJobsTool()
            
            result_json = await tool.execute(
                document_base64=params["document_base64"],
                document_filename=params.get("document_filename", "resume.pdf"),
                job_title=params["job_title"],
                location=params["location"],
                seniority=params.get("seniority"),
                remote=params.get("remote"),
                employment_type=params.get("employment_type"),
                include_keywords=params.get("include_keywords"),
                exclude_keywords=params.get("exclude_keywords"),
                num_openings=params.get("num_openings", 100)
            )
            
            result = json.loads(result_json)
            
            if result.get("success"):
                logger.info("Job scouring completed: found %d jobs", 
                           result.get("meta", {}).get("returned_jobs", 0))
            else:
                logger.warning("Job scouring failed: %s", result.get("error"))
            
            return result

        except Exception as e:
            logger.exception("Error executing job scouring: %s", e)
            return {
                "success": False,
                "error": str(e)
            }


async def create_cv_magic_agent() -> CVMagicAgent:
    """Factory function to create and initialize CV Magic agent."""
    agent = CVMagicAgent()
    await agent.initialize()
    agent.register_on_board()
    return agent
