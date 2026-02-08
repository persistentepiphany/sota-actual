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
        Execute a booking/verification call.

        Tries ElevenLabs ConvAI outbound call first (conversational AI),
        falls back to Twilio TwiML (text-to-speech script).
        """
        params = job.params or {}
        phone_number = params.get("phone_number", "")
        purpose = params.get("purpose", job.description or "booking")

        # Booking details
        location = params.get("location") or params.get("city") or ""
        date = params.get("date") or params.get("check_in") or "tomorrow"
        time_slot = params.get("time") or "8pm"
        guests = params.get("guests") or params.get("num_of_people") or 2
        cuisine = params.get("cuisine") or ""
        user_name = params.get("user_name") or "SOTA Guest"

        if not phone_number:
            return {
                "success": False,
                "error": "No phone_number provided in job parameters",
                "chat_summary": "I couldn't make the call because no phone number was provided.",
            }

        logger.info("📞 Executing call job #%s → %s (%s)", job.job_id, phone_number, purpose)

        # ── Try ElevenLabs ConvAI outbound call ──────────────
        from .tools import MakeElevenLabsCallTool, MakePhoneCallTool, GetCallStatusTool
        import json as _json

        el_api_key = os.getenv("ELEVENLABS_API_KEY")
        el_phone_id = os.getenv("ELEVENLABS_PHONE_ID")
        el_agent_id = os.getenv("ELEVENLABS_CALLER_AGENT_ID") or os.getenv("ELEVENLABS_AGENT_ID")

        if el_api_key and el_phone_id and el_agent_id:
            logger.info("📞 Using ElevenLabs ConvAI for outbound call")
            tool = MakeElevenLabsCallTool()
            raw = await tool.execute(
                to_number=phone_number,
                user_name=user_name,
                time=time_slot,
                date=str(date),
                num_of_people=int(guests),
                booking_type=booking_type,
                cuisine=cuisine,
                location=location,
            )
            result = _json.loads(raw)
            if result.get("success"):
                return {
                    "success": True,
                    "method": "elevenlabs_convai",
                    "phone_number": phone_number,
                    "call_data": result,
                    "chat_summary": (
                        f"I've placed a call to {phone_number} to "
                        f"{'book a table' if 'restaurant' in purpose.lower() else 'make a reservation'} "
                        f"for {guests} guests on {date} at {time_slot}. "
                        f"The AI assistant is handling the conversation now."
                    ),
                }
            logger.warning("ElevenLabs call failed, falling back to Twilio: %s", result.get("error"))

        # ── Fallback: Twilio TwiML call ──────────────────────
        logger.info("📞 Using Twilio TwiML for outbound call")
        booking_type = "restaurant" if "restaurant" in purpose.lower() else "hotel" if "hotel" in purpose.lower() else "booking"
        script = (
            f"Hello, this is an automated call from SOTA concierge service. "
            f"I'm calling to make a {booking_type} reservation. "
            f"{'We would like a table' if booking_type == 'restaurant' else 'We would like to book a room'} "
            f"for {guests} {'people' if int(guests) > 1 else 'person'} "
            f"on {date} at {time_slot}. "
        )
        if cuisine:
            script += f"We're interested in {cuisine} cuisine. "
        if location:
            script += f"Location preference: {location}. "
        script += (
            f"The reservation would be under the name {user_name}. "
            f"Please confirm availability. Thank you!"
        )

        call_tool = MakePhoneCallTool()
        raw = await call_tool.execute(
            phone_number=phone_number,
            script=script,
            gather_input=False,
            record=True,
        )
        call_result = _json.loads(raw)

        if not call_result.get("success"):
            return {
                "success": False,
                "error": call_result.get("error", "Call failed"),
                "chat_summary": f"I tried to call {phone_number} but the call couldn't be connected: {call_result.get('error', 'unknown error')}",
            }

        call_sid = call_result.get("call_sid")

        # Poll for call completion (up to 90 seconds)
        status_tool = GetCallStatusTool()
        final_status = "initiated"
        call_duration = None
        recording_urls = []

        for _ in range(18):  # 18 * 5s = 90s max
            await asyncio.sleep(5)
            try:
                status_raw = await status_tool.execute(call_sid)
                status_data = _json.loads(status_raw)
                if status_data.get("success"):
                    final_status = status_data.get("status", "unknown")
                    call_duration = status_data.get("duration")
                    recording_urls = status_data.get("recording_urls", [])
                    if final_status in ("completed", "failed", "busy", "no-answer", "canceled"):
                        break
            except Exception:
                pass

        logger.info("📞 Call %s finished: status=%s duration=%s", call_sid, final_status, call_duration)

        return {
            "success": final_status == "completed",
            "method": "twilio_twiml",
            "phone_number": phone_number,
            "call_sid": call_sid,
            "status": final_status,
            "duration_seconds": call_duration,
            "recording_urls": recording_urls,
            "booking_details": {
                "type": booking_type,
                "guests": guests,
                "date": date,
                "time": time_slot,
                "name": user_name,
                "location": location,
                "cuisine": cuisine,
            },
            "chat_summary": (
                f"I called {phone_number} to make a {booking_type} reservation "
                f"for {guests} guests on {date} at {time_slot} under {user_name}. "
                f"Call status: {final_status}"
                + (f", duration: {call_duration}s" if call_duration else "")
                + ". "
                + ("The reservation request has been communicated." if final_status == "completed"
                   else f"The call ended with status: {final_status}. You may want to try again.")
            ),
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

