#!/usr/bin/env python3
"""
Demo: User Strategy -> Flare FTSO -> LLM Signal

Shows how the Flare Predictor:
1. Takes user's trading strategy as input
2. Fetches REAL prices from Flare FTSO oracle
3. Uses LLM to generate personalized signal based on user's preferences
"""
import asyncio
import json
import os

os.environ['FLARE_RPC_URL'] = 'https://coston2-api.flare.network/ext/C/rpc'

from src.flare_predictor.services.ftso_data import get_current_ftso_price, get_ftso_time_series, compute_derived_features
from src.flare_predictor.services.signal_generator import generate_market_signal
from src.flare_predictor.services.external_data import get_external_indicators


async def demo_conservative_user():
    """Conservative user asking about BTC"""
    print("\n" + "=" * 70)
    print("🧑 USER 1: Conservative Investor")
    print("=" * 70)
    
    user_strategy = {
        "risk_tolerance": "conservative",
        "investment_goal": "income",
        "time_horizon": "long",
        "max_position_size_pct": 5.0,
        "stop_loss_pct": 2.0,
        "take_profit_pct": 5.0,
        "avoid_high_volatility": True,
        "require_confirmation": True,
    }
    user_question = "Should I buy BTC now or wait for a dip?"
    asset = "BTC/USD"
    
    print(f"\n📋 Strategy: {user_strategy['risk_tolerance']} risk, {user_strategy['investment_goal']} goal")
    print(f"❓ Question: {user_question}")
    
    result = await get_personalized_signal(asset, user_strategy, user_question)
    print_signal(result, asset)


async def demo_aggressive_user():
    """Aggressive user asking about FLR"""
    print("\n" + "=" * 70)
    print("🧑 USER 2: Aggressive Speculator")
    print("=" * 70)
    
    user_strategy = {
        "risk_tolerance": "aggressive",
        "investment_goal": "speculation",
        "time_horizon": "scalp",
        "max_position_size_pct": 25.0,
        "stop_loss_pct": 5.0,
        "take_profit_pct": 15.0,
        "avoid_high_volatility": False,
        "require_confirmation": False,
    }
    user_question = "I want to make a quick trade on FLR. What's the move?"
    asset = "FLR/USD"
    
    print(f"\n📋 Strategy: {user_strategy['risk_tolerance']} risk, {user_strategy['investment_goal']} goal")
    print(f"❓ Question: {user_question}")
    
    result = await get_personalized_signal(asset, user_strategy, user_question)
    print_signal(result, asset)


async def get_personalized_signal(asset: str, user_strategy: dict, user_question: str) -> dict:
    """Get personalized signal using Flare FTSO + LLM"""
    
    # 1. Get REAL price from Flare FTSO
    print(f"\n🔗 Fetching from Flare FTSO...")
    ftso_price = await get_current_ftso_price(asset)
    current_price = ftso_price["price"]
    
    print(f"   └─ {asset}: ${current_price:,.6f}" if current_price < 1 else f"   └─ {asset}: ${current_price:,.2f}")
    print(f"   └─ Source: {ftso_price['source']} (Flare Coston2)")
    
    # 2. Get time series and compute features
    ts = await get_ftso_time_series(asset, 120)
    features = compute_derived_features(ts)
    
    print(f"\n📊 FTSO Technical Indicators:")
    print(f"   └─ RSI (14): {features['rsi_14']:.1f}")
    print(f"   └─ Volatility: {features['volatility_60m']*100:.2f}%")
    print(f"   └─ 5min Return: {features['return_5m']*100:.3f}%")
    
    # 3. Get external indicators (FDC-compatible)
    external = await get_external_indicators(asset)
    print(f"\n🌐 FDC External Indicators:")
    print(f"   └─ Fear/Greed Index: {external['fear_greed_index']}")
    print(f"   └─ Funding Rate: {external['funding_rate']*100:.3f}%")
    
    # 4. Generate signal with LLM + user strategy
    print(f"\n🤖 Generating personalized signal...")
    result = await generate_market_signal({
        "asset": asset,
        "current_price": current_price,
        "horizon_minutes": 60,
        "ftso_time_series": ts,
        "derived_features": features,
        "external_indicators": external,
        "risk_profile": user_strategy["risk_tolerance"],
        "user_strategy": user_strategy,
        "user_question": user_question,
    })
    
    result["current_price"] = current_price
    return result


def print_signal(result: dict, asset: str):
    """Pretty print the signal result"""
    signal_emoji = {
        "STRONGLY_BUY": "🚀", "BUY": "📈", "HOLD": "⏸️", 
        "SELL": "📉", "STRONGLY_SELL": "🔻"
    }.get(result.get("signal", "HOLD"), "⏸️")
    
    price = result.get("current_price", 0)
    price_str = f"${price:,.6f}" if price < 1 else f"${price:,.2f}"
    
    print(f"\n{'='*70}")
    print(f"{signal_emoji} SIGNAL: {result['signal']} | Confidence: {result['confidence']*100:.0f}%")
    print(f"{'='*70}")
    print(f"\n💰 Current Price: {price_str}")
    print(f"\n💡 Summary: {result['reasoning_short']}")
    print(f"\n📝 Analysis: {result['reasoning_detailed']}")
    print(f"\n🎯 Action: {result['recommended_action']}")
    
    if result.get("risk_flags"):
        print(f"\n⚠️ Risks: {', '.join(result['risk_flags'])}")


async def main():
    print("=" * 70)
    print("🔮 FLARE PREDICTOR - Personalized Signal Demo")
    print("   Using REAL Flare FTSO data + User Strategy + LLM")
    print("=" * 70)
    
    await demo_conservative_user()
    await demo_aggressive_user()
    
    print("\n" + "=" * 70)
    print("✅ Demo complete! Same data, different signals based on user strategy.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
