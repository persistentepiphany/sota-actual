#!/usr/bin/env python3
"""Test Flare Predictor with user strategy - returns JSON for chat"""
import asyncio
import os
import json

os.environ['FLARE_RPC_URL'] = 'https://coston2-api.flare.network/ext/C/rpc'
os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY', '')

from src.flare_predictor.services.ftso_data import get_ftso_time_series, get_current_ftso_price, compute_derived_features
from src.flare_predictor.services.signal_generator import generate_market_signal
from src.flare_predictor.services.external_data import get_external_indicators


async def test_with_user_strategy():
    print("=" * 70)
    print("🔮 FLARE PREDICTOR - Personalized Signal Test")
    print("=" * 70)
    
    # User strategy - collected from user preferences
    user_strategy = {
        "risk_tolerance": "aggressive",  # conservative, moderate, aggressive
        "investment_goal": "speculation",  # income, growth, speculation, hedging
        "time_horizon": "short",  # scalp, short, medium, long
        "max_position_size_pct": 15.0,
        "stop_loss_pct": 3.0,
        "take_profit_pct": 8.0,
        "avoid_high_volatility": False,
        "require_confirmation": True,
    }
    
    # User's question
    user_question = "Is now a good time to buy FLR? I'm bullish on Flare long term."
    
    asset = "FLR/USD"
    horizon_minutes = 60
    
    print(f"\n📋 User Strategy:")
    print(f"   Risk Tolerance: {user_strategy['risk_tolerance']}")
    print(f"   Investment Goal: {user_strategy['investment_goal']}")
    print(f"   Time Horizon: {user_strategy['time_horizon']}")
    print(f"   Max Position: {user_strategy['max_position_size_pct']}%")
    print(f"   Stop Loss: {user_strategy['stop_loss_pct']}%")
    print(f"   Take Profit: {user_strategy['take_profit_pct']}%")
    print(f"\n❓ User Question: {user_question}")
    print("-" * 70)
    
    # Get real FTSO price
    current_price_data = await get_current_ftso_price(asset)
    current_price = current_price_data["price"]
    
    # Get time series
    ts = await get_ftso_time_series(asset, horizon_minutes * 2)
    features = compute_derived_features(ts)
    external = await get_external_indicators(asset)
    
    # Generate signal with user context
    signal_input = {
        "asset": asset,
        "current_price": current_price,
        "horizon_minutes": horizon_minutes,
        "ftso_time_series": ts,
        "derived_features": features,
        "external_indicators": external,
        "risk_profile": user_strategy["risk_tolerance"],
        "user_strategy": user_strategy,
        "user_question": user_question,
    }
    
    result = await generate_market_signal(signal_input)
    
    # Build chat summary (what would be displayed in chat)
    signal_emoji = {"STRONGLY_BUY": "🚀", "BUY": "📈", "HOLD": "⏸️", "SELL": "📉", "STRONGLY_SELL": "🔻"}.get(result.get("signal", "HOLD"), "⏸️")
    
    # Calculate entry zones
    entry_low = current_price * 0.99
    entry_high = current_price * 1.01
    stop_loss = current_price * (1 - user_strategy["stop_loss_pct"]/100)
    take_profit = current_price * (1 + user_strategy["take_profit_pct"]/100)
    
    print(f"\n{signal_emoji} **{result['signal']}** {asset} @ ${current_price:.6f}")
    print(f"\n📊 Confidence: {result['confidence']*100:.0f}%")
    print(f"💡 {result['reasoning_short']}")
    print(f"\n📝 Detailed Analysis:")
    print(f"   {result['reasoning_detailed']}")
    print(f"\n🎯 Entry Zone: ${entry_low:.6f} - ${entry_high:.6f}")
    print(f"🛑 Stop Loss: ${stop_loss:.6f}")
    print(f"✅ Take Profit: ${take_profit:.6f}")
    
    if result.get("risk_flags"):
        print(f"\n⚠️ Risks: {', '.join(result['risk_flags'])}")
    
    print(f"\n💼 Recommended Action:")
    print(f"   {result['recommended_action']}")
    
    # JSON output for API/chat
    print("\n" + "=" * 70)
    print("📤 JSON Response (for chat display):")
    print("=" * 70)
    
    json_response = {
        "success": True,
        "asset": asset,
        "current_price": current_price,
        "signal": result["signal"],
        "confidence": result["confidence"],
        "reasoning_short": result["reasoning_short"],
        "reasoning_detailed": result["reasoning_detailed"],
        "risk_flags": result["risk_flags"],
        "recommended_action": result["recommended_action"],
        "time_horizon_minutes": result.get("time_horizon_minutes", horizon_minutes),
        "entry_zone": f"${entry_low:.6f} - ${entry_high:.6f}",
        "stop_loss": f"${stop_loss:.6f}",
        "take_profit": f"${take_profit:.6f}",
        "strategy_alignment": f"Signal tailored for {user_strategy['risk_tolerance']} risk, {user_strategy['investment_goal']} goal",
    }
    
    print(json.dumps(json_response, indent=2))


if __name__ == "__main__":
    asyncio.run(test_with_user_strategy())
