#!/usr/bin/env python3
"""
Test script for Flare Predictor Agent
"""
import asyncio
import json

from src.flare_predictor.services.ftso_data import get_ftso_time_series, compute_derived_features
from src.flare_predictor.services.signal_generator import generate_market_signal
from src.flare_predictor.services.external_data import get_external_indicators


async def test_all_assets():
    assets = ["BTC/USD", "FLR/USD", "ETH/USD", "XRP/USD"]
    print("=" * 60)
    print("FLARE PREDICTOR - MARKET SIGNAL TEST")
    print("=" * 60)
    
    for asset in assets:
        # Get FTSO time series
        ts = await get_ftso_time_series(asset, 60)
        
        # Compute derived features
        features = compute_derived_features(ts)
        
        # Get external indicators
        external = await get_external_indicators(asset)
        
        # Generate signal
        signal_input = {
            "asset": asset,
            "horizon_minutes": 60,
            "ftso_time_series": ts,
            "derived_features": features,
            "external_indicators": external,
            "risk_profile": "moderate"
        }
        
        result = await generate_market_signal(signal_input)
        
        print(f"\n📊 {asset}:")
        print(f"   Signal: {result['signal']} (Confidence: {result['confidence']:.1%})")
        print(f"   Reasoning: {result['reasoning_short']}")
        print(f"   Action: {result['recommended_action']}")
        print(f"   Risk Flags: {', '.join(result['risk_flags'])}")
    
    print("\n" + "=" * 60)
    print("✅ All tests completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_all_assets())
