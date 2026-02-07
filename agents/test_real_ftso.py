#!/usr/bin/env python3
"""Test real FTSO connection to Flare Coston2"""
import asyncio
import os

os.environ['FLARE_RPC_URL'] = 'https://coston2-api.flare.network/ext/C/rpc'

from src.flare_predictor.services.ftso_data import get_current_ftso_price, get_ftso_time_series

async def test():
    print("Testing REAL Flare FTSO connection...")
    print("=" * 50)
    
    # Test current prices
    for asset in ["FLR/USD", "BTC/USD", "ETH/USD", "XRP/USD"]:
        try:
            result = await get_current_ftso_price(asset)
            price = result["price"]
            source = result["source"]
            print(f"{asset}: ${price:.6f} (source: {source})")
        except Exception as e:
            print(f"{asset}: ERROR - {e}")
    
    print()
    print("Testing time series with real anchor price...")
    ts = await get_ftso_time_series("BTC/USD", 30)
    print(f"Got {len(ts)} data points")
    print(f"Latest: ${ts[-1]['price']}")

if __name__ == "__main__":
    asyncio.run(test())
