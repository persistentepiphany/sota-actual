"""
Flare Predictor Server — FastAPI A2A Endpoint

Runs the Flare Market Prediction agent as a standalone service.
"""

import os
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Global agent instance
_agent = None


class UserStrategy(BaseModel):
    """User's trading strategy and preferences"""
    risk_tolerance: str = Field(
        default="moderate",
        description="Risk tolerance: conservative, moderate, aggressive"
    )
    investment_goal: str = Field(
        default="growth",
        description="Investment goal: income, growth, speculation, hedging"
    )
    time_horizon: str = Field(
        default="short",
        description="Time horizon: scalp (minutes), short (hours), medium (days), long (weeks)"
    )
    max_position_size_pct: float = Field(
        default=10.0,
        description="Maximum position size as % of portfolio"
    )
    preferred_assets: List[str] = Field(
        default=["BTC/USD", "ETH/USD", "FLR/USD"],
        description="List of preferred trading assets"
    )
    stop_loss_pct: Optional[float] = Field(
        default=5.0,
        description="Stop loss percentage"
    )
    take_profit_pct: Optional[float] = Field(
        default=10.0,
        description="Take profit percentage"
    )
    avoid_high_volatility: bool = Field(
        default=False,
        description="Avoid signals during high volatility periods"
    )
    require_confirmation: bool = Field(
        default=True,
        description="Require multiple indicator confirmation"
    )


class PredictionRequest(BaseModel):
    """Request model for market prediction"""
    asset: str = Field(default="FLR/USD", description="Asset pair to analyze")
    horizon_minutes: int = Field(default=60, description="Prediction time horizon in minutes")
    include_external: bool = Field(default=True, description="Include external indicators")
    user_strategy: Optional[UserStrategy] = Field(default=None, description="User's trading strategy")
    user_question: Optional[str] = Field(default=None, description="User's specific question about the market")


class SignalResponse(BaseModel):
    """Response model for market signal - JSON formatted for chat display"""
    success: bool
    asset: str
    current_price: float
    signal: str
    confidence: float
    reasoning_short: str
    reasoning_detailed: str
    risk_flags: List[str]
    recommended_action: str
    time_horizon_minutes: int
    # User strategy context
    strategy_alignment: Optional[str] = None
    position_suggestion: Optional[str] = None
    entry_zone: Optional[str] = None
    stop_loss: Optional[str] = None
    take_profit: Optional[str] = None
    # Chat display fields
    chat_summary: Optional[str] = None
    error: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage agent lifecycle."""
    global _agent
    
    logger.info("Starting Flare Predictor Agent...")
    # Skip full agent initialization for now - use standalone mode
    logger.info("✅ Flare Predictor Agent ready (standalone mode)")
    
    yield
    
    logger.info("Shutting down Flare Predictor Agent...")


app = FastAPI(
    title="SOTA Flare Predictor Agent",
    description="On-chain trading signal generator using Flare FTSO data",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "flare_predictor",
        "ready": True
    }


@app.get("/status")
async def agent_status():
    """Get agent status and capabilities."""
    return {
        "agent_type": "flare_predictor",
        "agent_name": "SOTA Flare Predictor",
        "mode": "standalone" if not _agent else "full",
        "supported_assets": ["BTC/USD", "FLR/USD", "XRP/USD", "ETH/USD", "DOGE/USD"],
        "signals": ["STRONGLY_BUY", "BUY", "HOLD", "SELL", "STRONGLY_SELL"],
        "auto_bid_enabled": _agent.auto_bid_enabled if _agent else False,
        "max_concurrent_jobs": _agent.max_concurrent_jobs if _agent else 3,
    }


@app.post("/predict", response_model=SignalResponse)
async def generate_prediction(request: PredictionRequest):
    """
    Generate a market prediction signal based on user strategy.
    
    This is the main API endpoint for getting trading signals.
    Returns JSON formatted for chat display.
    """
    try:
        from .services.ftso_data import get_ftso_time_series, get_current_ftso_price, compute_derived_features
        from .services.signal_generator import generate_market_signal
        from .services.external_data import get_external_indicators
        
        # Get user strategy or use defaults
        strategy = request.user_strategy or UserStrategy()
        
        # 1. Get current FTSO price
        current_price_data = await get_current_ftso_price(request.asset)
        current_price = current_price_data["price"]
        
        # 2. Fetch FTSO time series
        time_series = await get_ftso_time_series(
            request.asset, 
            request.horizon_minutes * 2
        )
        
        # 3. Compute derived features
        derived = compute_derived_features(time_series)
        
        # 4. Get external indicators (optional)
        external = {}
        if request.include_external:
            external = await get_external_indicators(request.asset)
        
        # 5. Generate signal with user strategy context
        signal_input = {
            "asset": request.asset,
            "current_price": current_price,
            "horizon_minutes": request.horizon_minutes,
            "ftso_time_series": time_series,
            "derived_features": derived,
            "external_indicators": external,
            "risk_profile": strategy.risk_tolerance,
            "user_strategy": {
                "risk_tolerance": strategy.risk_tolerance,
                "investment_goal": strategy.investment_goal,
                "time_horizon": strategy.time_horizon,
                "max_position_size_pct": strategy.max_position_size_pct,
                "stop_loss_pct": strategy.stop_loss_pct,
                "take_profit_pct": strategy.take_profit_pct,
                "avoid_high_volatility": strategy.avoid_high_volatility,
                "require_confirmation": strategy.require_confirmation,
            },
            "user_question": request.user_question,
        }
        
        result = await generate_market_signal(signal_input)
        
        # Calculate entry zones based on strategy
        entry_zone = f"${current_price * 0.99:.2f} - ${current_price * 1.01:.2f}" if current_price > 1 else f"${current_price * 0.99:.6f} - ${current_price * 1.01:.6f}"
        stop_loss = f"${current_price * (1 - strategy.stop_loss_pct/100):.2f}" if current_price > 1 else f"${current_price * (1 - strategy.stop_loss_pct/100):.6f}"
        take_profit = f"${current_price * (1 + strategy.take_profit_pct/100):.2f}" if current_price > 1 else f"${current_price * (1 + strategy.take_profit_pct/100):.6f}"
        
        # Generate chat summary
        signal_emoji = {"STRONGLY_BUY": "🚀", "BUY": "📈", "HOLD": "⏸️", "SELL": "📉", "STRONGLY_SELL": "🔻"}.get(result.get("signal", "HOLD"), "⏸️")
        chat_summary = f"{signal_emoji} **{result.get('signal', 'HOLD')}** {request.asset} @ ${current_price:.2f if current_price > 1 else current_price:.6f}\n\n"
        chat_summary += f"📊 Confidence: {result.get('confidence', 0.5)*100:.0f}%\n"
        chat_summary += f"💡 {result.get('reasoning_short', 'Analysis complete.')}\n\n"
        chat_summary += f"🎯 Entry Zone: {entry_zone}\n"
        chat_summary += f"🛑 Stop Loss: {stop_loss}\n"
        chat_summary += f"✅ Take Profit: {take_profit}\n\n"
        if result.get("risk_flags"):
            chat_summary += f"⚠️ Risks: {', '.join(result.get('risk_flags', []))}"
        
        # Strategy alignment message
        strategy_alignment = f"Signal aligned with your {strategy.risk_tolerance} risk profile and {strategy.investment_goal} goal."
        if strategy.avoid_high_volatility and derived.get("volatility_60m", 0) > 0.05:
            strategy_alignment = "⚠️ High volatility detected. Your strategy prefers lower volatility - consider waiting."
        
        # Position suggestion
        position_pct = strategy.max_position_size_pct
        if result.get("confidence", 0.5) < 0.6:
            position_pct = position_pct * 0.5
        position_suggestion = f"Suggested position: {position_pct:.1f}% of portfolio"
        
        return SignalResponse(
            success=True,
            asset=request.asset,
            current_price=current_price,
            signal=result.get("signal", "HOLD"),
            confidence=result.get("confidence", 0.5),
            reasoning_short=result.get("reasoning_short", ""),
            reasoning_detailed=result.get("reasoning_detailed", ""),
            risk_flags=result.get("risk_flags", []),
            recommended_action=result.get("recommended_action", ""),
            time_horizon_minutes=result.get("time_horizon_minutes", request.horizon_minutes),
            strategy_alignment=strategy_alignment,
            position_suggestion=position_suggestion,
            entry_zone=entry_zone,
            stop_loss=stop_loss,
            take_profit=take_profit,
            chat_summary=chat_summary,
        )
        
    except Exception as e:
        logger.exception("Error generating prediction: %s", e)
        return SignalResponse(
            success=False,
            asset=request.asset,
            current_price=0.0,
            signal="HOLD",
            confidence=0.0,
            reasoning_short=f"Error: {str(e)}",
            reasoning_detailed="An error occurred during signal generation.",
            risk_flags=["Prediction error"],
            recommended_action="Do not change position until valid signal is available.",
            time_horizon_minutes=0,
            error=str(e)
        )


@app.get("/prices/{asset}")
async def get_prices(asset: str, lookback_minutes: int = 120):
    """
    Get FTSO price data for an asset.
    """
    try:
        from .services.ftso_data import get_ftso_time_series
        
        time_series = await get_ftso_time_series(asset, lookback_minutes)
        
        return {
            "success": True,
            "asset": asset,
            "data_points": len(time_series),
            "time_series": time_series
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/indicators/{asset}")
async def get_indicators(asset: str):
    """
    Get external indicators for an asset.
    """
    try:
        from .services.external_data import get_external_indicators
        
        indicators = await get_external_indicators(asset)
        
        return {
            "success": True,
            "asset": asset,
            "indicators": indicators,
            "note": "These indicators could be integrated on-chain via FDC."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# A2A messaging endpoint
@app.post("/a2a")
async def a2a_message(message: dict):
    """
    Agent-to-Agent messaging endpoint.
    Receives job assignments and returns results.
    """
    if not _agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    msg_type = message.get("type")
    
    if msg_type == "job_assigned":
        # Handle job assignment
        job_id = message.get("job_id")
        params = message.get("params", {})
        
        result = await _agent.execute_job_direct(job_id, params)
        return {"status": "completed", "result": result}
    
    elif msg_type == "status_check":
        return {
            "status": "active",
            "active_jobs": len(_agent.active_jobs),
            "auto_bid_enabled": _agent.auto_bid_enabled,
        }
    
    else:
        return {"status": "unknown_message_type", "type": msg_type}


def run_server():
    """Run the Flare Predictor server."""
    import uvicorn
    
    port = int(os.getenv("FLARE_PREDICTOR_PORT", "3009"))
    host = os.getenv("FLARE_PREDICTOR_HOST", "0.0.0.0")
    
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_server()
