"""
Flare Market Predictor Agent

Consumes FTSO time-series data and generates trading signals for on-chain strategies.
"""

import os
import asyncio
import logging
import json
from typing import Optional, Dict, Any, List

from pydantic import Field

from ..shared.agent_runner import AgentRunner, LLMClient
from ..shared.tool_base import ToolManager

from ..shared.base_agent import BaseArchiveAgent, AgentCapability, ActiveJob, BidDecision
from ..shared.auto_bidder import AutoBidderMixin
from ..shared.config import JobType, JOB_TYPE_LABELS
from ..shared.events import JobPostedEvent
from ..shared.wallet_tools import create_wallet_tools
from ..shared.bidding_tools import create_bidding_tools

from .tools import create_flare_predictor_tools

logger = logging.getLogger(__name__)


FLARE_PREDICTOR_SYSTEM_PROMPT = """
You are an on-chain trading advisor and signal explainer for the Flare blockchain.
Your job is to:

1. Consume recent time-series data for assets (e.g. BTC/USD, FLR/USD, FXRP/USD) derived from Flare's FTSO price feeds.
2. Optionally consume external indicators via Flare Data Connector (FDC): funding rates, open interest, risk indices.
3. Generate a simple, discrete market signal and clear explanation for smart-contract strategies.

Your capabilities:
1. **Get FTSO Prices**: Use get_ftso_prices to fetch current/historical price data from Flare FTSO
2. **Generate Signal**: Use generate_signal to produce trading signals with full analysis
3. **Get External Indicators**: Use get_external_indicators to fetch FDC-compatible data

SIGNAL OUTPUT FORMAT:
{
  "signal": "STRONGLY_BUY | BUY | HOLD | SELL | STRONGLY_SELL",
  "confidence": 0.0-1.0,
  "reasoning_short": "One-sentence summary.",
  "reasoning_detailed": "2-4 bullet-style sentences.",
  "risk_flags": ["List of risk concerns"],
  "recommended_action": "How an on-chain strategy should react",
  "time_horizon_minutes": 60
}

BEHAVIOUR GUIDELINES:
- You are NOT executing trades - producing advisory signals only
- Err on HOLD when indicators conflict or data is sparse
- Focus on momentum, volatility, mean reversion vs breakout
- Mention when indicators could be brought on-chain via FDC
- Never guarantee profits - probabilistic guidance only
- If input is malformed, return HOLD with confidence 0.0
"""


class FlarePredictor(AutoBidderMixin, BaseArchiveAgent):
    """
    Flare Market Prediction Agent for SOTA.
    
    Generates trading signals based on FTSO price data and external indicators.
    Uses LLM reasoning to analyze market conditions and produce actionable signals.
    """
    
    agent_type = "flare_predictor"
    agent_name = "SOTA Flare Market Predictor"
    capabilities = [
        AgentCapability.DATA_ANALYSIS,
    ]
    # Specialize in market prediction
    supported_job_types = [JobType.MARKET_PREDICTION]
    
    # Bidding configuration
    min_profit_margin = 0.10  # 10% margin
    max_concurrent_jobs = 10  # Can handle many concurrent predictions
    auto_bid_enabled = True
    bid_price_ratio = 0.80    # Predictor bids 80% of budget
    bid_eta_seconds = 30      # Fast signal generation
    
    def get_bidding_prompt(self, job) -> str:
        """Generate prompt for evaluating whether to bid on a market prediction job."""
        return f"""
Evaluate this market prediction job and decide whether to bid:

Job ID: {job.job_id}
Job Type: Market Prediction
Budget: {job.budget} USDC
Description: {job.description}
Parameters: {job.params}

You are the Flare Predictor agent specializing in on-chain trading signals.
You can generate market signals using FTSO price data and external indicators.

Consider:
1. Is this a market prediction / trading signal request?
2. Is the budget reasonable for the work required?
3. Can you deliver within the expected timeframe?

Respond with your bid decision.
"""

    async def _create_llm_agent(self) -> AgentRunner:
        """Create agent runner for market prediction."""
        all_tools: list = []
        all_tools.extend(create_flare_predictor_tools())
        all_tools.extend(create_wallet_tools(self.wallet))
        all_tools.extend(create_bidding_tools(self._contracts, self.agent_type))

        model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        return AgentRunner(
            name="flare_predictor",
            description="Flare market prediction agent using FTSO data",
            system_prompt=FLARE_PREDICTOR_SYSTEM_PROMPT,
            max_steps=10,
            tools=ToolManager(all_tools),
            llm=LLMClient(model=model_name),
        )
    
    async def execute_job(self, job: ActiveJob) -> Dict[str, Any]:
        """
        Execute a market prediction job.
        
        Expected job params:
        - asset: str (e.g., "BTC/USD", "FLR/USD")
        - horizon_minutes: int (prediction horizon)
        - risk_profile: str ("conservative", "moderate", "aggressive")
        - external_indicators: dict (optional)
        """
        params = job.params or {}
        asset = params.get("asset", "FLR/USD")
        horizon = params.get("horizon_minutes", 60)
        risk_profile = params.get("risk_profile", "moderate")
        
        logger.info("Executing market prediction for %s (horizon: %d min)", asset, horizon)
        
        try:
            from .services.ftso_data import get_ftso_time_series, compute_derived_features
            from .services.signal_generator import generate_market_signal
            from .services.external_data import get_external_indicators
            
            # 1. Fetch FTSO time series
            time_series = await get_ftso_time_series(asset, horizon * 2)
            
            # 2. Compute derived features
            derived = compute_derived_features(time_series)
            
            # 3. Get external indicators (if available)
            external = await get_external_indicators(asset)
            
            # 4. Generate signal via LLM
            signal_input = {
                "asset": asset,
                "horizon_minutes": horizon,
                "ftso_time_series": time_series,
                "derived_features": derived,
                "external_indicators": external,
                "risk_profile": risk_profile,
            }
            
            result = await generate_market_signal(signal_input)
            
            logger.info("Generated signal: %s (confidence: %.2f)", 
                       result.get("signal"), result.get("confidence", 0))
            
            return {
                "success": True,
                "asset": asset,
                "horizon_minutes": horizon,
                **result
            }
            
        except Exception as e:
            logger.exception("Error generating market prediction: %s", e)
            return {
                "success": False,
                "signal": "HOLD",
                "confidence": 0.0,
                "reasoning_short": f"Error during prediction: {str(e)}",
                "reasoning_detailed": "An error occurred while processing the prediction request.",
                "risk_flags": ["Prediction error - data unavailable"],
                "recommended_action": "Do not change position until valid signal is available.",
                "time_horizon_minutes": 0,
                "error": str(e)
            }


async def create_flare_predictor_agent() -> FlarePredictor:
    """Factory function to create and initialize Flare Predictor agent."""
    agent = FlarePredictor()
    await agent.initialize()
    agent.register_on_board()
    return agent
