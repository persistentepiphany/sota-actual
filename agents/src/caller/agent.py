"""
Caller Agent — SOTA on Flare

The Caller Agent:
1. Listens for phone verification job events
2. Evaluates jobs and decides whether to bid
3. Executes accepted jobs using Twilio
4. Uploads results and submits delivery proofs
"""

import os
import asyncio
import logging
from typing import Optional

from pydantic import Field

from ..shared.agent_runner import AgentRunner, LLMClient
from ..shared.tool_base import ToolManager

from ..shared.base_agent import BaseArchiveAgent, AgentCapability, ActiveJob, BidDecision
from ..shared.auto_bidder import AutoBidderMixin
from ..shared.config import JobType, JOB_TYPE_LABELS
from ..shared.events import JobPostedEvent
from ..shared.wallet_tools import create_wallet_tools
from ..shared.bidding_tools import create_bidding_tools

from .tools import create_caller_tools

logger = logging.getLogger(__name__)


CALLER_SYSTEM_PROMPT = """
You are the Caller Agent for SOTA, specializing in phone verification on Flare.

Your capabilities:
1. **Phone Calls**: Use make_phone_call to:
   - Verify business information
   - Make reservations
   - Confirm details

2. **SMS**: Use send_sms for follow-up confirmations.

3. **Call Status**: Use get_call_status to check call outcomes.

4. **Delivery**: After calls:
   - Upload results using upload_call_result
   - Compute proof hash using compute_proof_hash
   - Submit delivery using submit_delivery

5. **Wallet & Bidding**: Check balance and manage bids.

IMPORTANT: Always be professional and polite on calls.
Generate appropriate scripts before making calls.

Based on the current progress, decide the next action:
- To make a call: generate script, then use make_phone_call
- After call: get_call_status, then upload_call_result
- Finally: submit_delivery with proof hash
- To check wallet: use get_wallet_balance
- To bid on job: use place_bid
"""


class CallerAgent(AutoBidderMixin, BaseArchiveAgent):
    """
    Caller Agent for SOTA.
    
    Extends BaseArchiveAgent with phone verification-specific logic.
    Mixes in AutoBidderMixin to participate in the JobBoard marketplace.
    """
    
    agent_type = "caller"
    agent_name = "SOTA Caller Agent"
    capabilities = [
        AgentCapability.PHONE_CALL,
    ]
    # Only handle booking and call verification jobs
    supported_job_types = [
        JobType.HOTEL_BOOKING,
        JobType.RESTAURANT_BOOKING,
        JobType.CALL_VERIFICATION,
    ]
    
    # Bidding configuration
    min_profit_margin = 0.20  # 20% margin (calls are more expensive)
    max_concurrent_jobs = 2   # Fewer concurrent calls
    auto_bid_enabled = True
    bid_price_ratio = 0.90     # caller bids 90% of budget (more expensive service)
    
    async def _create_llm_agent(self) -> AgentRunner:
        """Create agent runner for tooling (bidding is auto)."""
        all_tools = []
        all_tools.extend(create_caller_tools())
        all_tools.extend(create_wallet_tools(self.wallet))
        all_tools.extend(create_bidding_tools(self._contracts, self.agent_type))

        model_name = os.getenv("LLM_MODEL", "gpt-4o-mini")

        return AgentRunner(
            name="caller",
            description="Caller Agent for phone verification tasks",
            system_prompt=CALLER_SYSTEM_PROMPT,
            max_steps=15,
            tools=ToolManager(all_tools),
            llm=LLMClient(model=model_name),
        )

    def get_bidding_prompt(self, job: JobPostedEvent) -> str:
        """Not used for auto-bid; kept for compatibility."""
        job_type_label = JOB_TYPE_LABELS.get(JobType(job.job_type), "Unknown")
        budget_flr = job.budget / 10**18
        return f"Auto-bid mode: will place 1 C2FLR bid on job {job.job_id} ({job_type_label}) budget {budget_flr} C2FLR."

    async def _evaluate_and_bid(self, job: JobPostedEvent):
        """
        Auto-bid 1 USDC on any job type.
        """
        if len(self.active_jobs) >= self.max_concurrent_jobs:
            logger.warning("At capacity, skipping job %s", job.job_id)
            return

        decision = BidDecision(
            should_bid=True,
            proposed_amount=1_000_000,  # 1 USDC
            estimated_time=1800,  # 30 min
            reasoning="Auto-bid caller on all job types",
            confidence=0.9,
        )

        if decision.should_bid and self._contracts:
            try:
                from agents.src.shared.contracts import place_bid

                bid_id = place_bid(
                    self._contracts,
                    job.job_id,
                    decision.proposed_amount,
                    decision.estimated_time,
                    f"ipfs://{self.agent_type}-bid-{job.job_id}",
                )
                logger.info("Auto-bid placed job_id=%s bid_id=%s", job.job_id, bid_id)
            except Exception as e:
                logger.error("Failed to place auto-bid on job %s: %s", job.job_id, e)
        elif decision.should_bid and not self._contracts:
            logger.error("Contracts not initialized; cannot bid on job #%s", job.job_id)

    async def execute_job(self, job: ActiveJob) -> dict:
        """
        Caller flow does not need a local LLM step.
        The outbound call (with job payload) is initiated via ElevenLabs already.
        """
        logger.info(f"📞 Skipping local LLM execution for job #{job.job_id} (call already initiated via ElevenLabs)")
        return {
            "success": True,
            "result": "Call initiated via ElevenLabs; no local execution required",
            "job_id": job.job_id
        }


async def create_caller_agent() -> CallerAgent:
    """Factory function to create and initialize a Caller Agent"""
    agent = CallerAgent()
    await agent.initialize()
    agent.register_on_board()          # ← register on JobBoard marketplace
    return agent


async def main():
    """Run the Caller Agent"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    print("📞 Archive Caller Agent")
    print("=" * 60)
    
    agent = await create_caller_agent()
    print(f"\n📊 Status: {agent.get_status()}")
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        agent.stop()
        print("\n👋 Caller Agent stopped")


if __name__ == "__main__":
    asyncio.run(main())

