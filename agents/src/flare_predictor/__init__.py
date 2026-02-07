"""
Flare Market Predictor Agent — On-chain Trading Signals for SOTA Marketplace

This agent consumes FTSO time-series data and external indicators via FDC
to generate discrete market signals (STRONGLY_BUY, BUY, HOLD, SELL, STRONGLY_SELL)
for smart contract strategies on Flare.
"""

from .agent import FlarePredictor, create_flare_predictor_agent

__all__ = ["FlarePredictor", "create_flare_predictor_agent"]
