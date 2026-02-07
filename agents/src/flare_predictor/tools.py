"""
Flare Market Predictor Tools

Tools for fetching FTSO data, external indicators, and generating trading signals.
These are EXECUTION tools — bidding is handled by shared bidding_tools.
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from pydantic import Field

from ..shared.tool_base import BaseTool

logger = logging.getLogger(__name__)


class GetFTSOPricesTool(BaseTool):
    """
    Tool to fetch FTSO price data from Flare network.
    Returns time-series data for the specified asset.
    """
    name: str = "get_ftso_prices"
    description: str = """
    Fetch FTSO (Flare Time Series Oracle) price data for an asset.
    
    Returns recent price history from Flare's decentralized oracle system.
    Supports assets like BTC/USD, FLR/USD, XRP/USD, ETH/USD, etc.
    
    Use this to get on-chain verified price data for market analysis.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "asset": {
                "type": "string",
                "description": "Asset pair to fetch (e.g., 'BTC/USD', 'FLR/USD', 'XRP/USD')"
            },
            "lookback_minutes": {
                "type": "integer",
                "description": "How many minutes of historical data to fetch (default 120)"
            },
            "interval_minutes": {
                "type": "integer",
                "description": "Interval between data points in minutes (default 5)"
            }
        },
        "required": ["asset"]
    }

    async def execute(
        self,
        asset: str,
        lookback_minutes: int = 120,
        interval_minutes: int = 5
    ) -> str:
        """Fetch FTSO price data for an asset"""
        try:
            from .services.ftso_data import get_ftso_time_series
        except ImportError as e:
            return json.dumps({
                "success": False,
                "error": f"FTSO service not available: {e}"
            })
        
        try:
            time_series = await get_ftso_time_series(
                asset, 
                lookback_minutes, 
                interval_minutes
            )
            
            return json.dumps({
                "success": True,
                "asset": asset,
                "data_points": len(time_series),
                "lookback_minutes": lookback_minutes,
                "time_series": time_series
            })
            
        except Exception as e:
            logger.exception("Error fetching FTSO data: %s", e)
            return json.dumps({
                "success": False,
                "error": str(e)
            })


class GetExternalIndicatorsTool(BaseTool):
    """
    Tool to fetch external market indicators that could be brought on-chain via FDC.
    """
    name: str = "get_external_indicators"
    description: str = """
    Fetch external market indicators for enhanced signal generation.
    
    Returns data like funding rates, fear/greed index, open interest changes.
    These indicators could be integrated on-chain via Flare Data Connector (FDC).
    
    Use this to enhance market predictions with off-chain sentiment data.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "asset": {
                "type": "string",
                "description": "Asset to fetch indicators for (e.g., 'BTC/USD')"
            },
            "indicators": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific indicators to fetch: 'funding_rate', 'fear_greed_index', 'open_interest'"
            }
        },
        "required": ["asset"]
    }

    async def execute(
        self,
        asset: str,
        indicators: Optional[List[str]] = None
    ) -> str:
        """Fetch external market indicators"""
        try:
            from .services.external_data import get_external_indicators
        except ImportError as e:
            return json.dumps({
                "success": False,
                "error": f"External data service not available: {e}"
            })
        
        try:
            data = await get_external_indicators(asset, indicators)
            
            return json.dumps({
                "success": True,
                "asset": asset,
                "indicators": data,
                "note": "These indicators could be integrated on-chain via FDC for trustless verification."
            })
            
        except Exception as e:
            logger.exception("Error fetching external indicators: %s", e)
            return json.dumps({
                "success": False,
                "error": str(e)
            })


class GenerateSignalTool(BaseTool):
    """
    Tool to generate a market trading signal based on FTSO data and indicators.
    """
    name: str = "generate_signal"
    description: str = """
    Generate a discrete market signal for an asset based on FTSO price data and indicators.
    
    Returns one of: STRONGLY_BUY, BUY, HOLD, SELL, STRONGLY_SELL
    with confidence score, reasoning, risk flags, and recommended on-chain action.
    
    This signal can be used by smart contract strategies on Flare.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "asset": {
                "type": "string",
                "description": "Asset pair to analyze (e.g., 'BTC/USD', 'FLR/USD')"
            },
            "horizon_minutes": {
                "type": "integer",
                "description": "Prediction time horizon in minutes (default 60)"
            },
            "risk_profile": {
                "type": "string",
                "enum": ["conservative", "moderate", "aggressive"],
                "description": "Risk tolerance for the signal"
            },
            "include_external": {
                "type": "boolean",
                "description": "Whether to include external indicators (default true)"
            }
        },
        "required": ["asset"]
    }

    async def execute(
        self,
        asset: str,
        horizon_minutes: int = 60,
        risk_profile: str = "moderate",
        include_external: bool = True
    ) -> str:
        """Generate a market trading signal"""
        try:
            from .services.ftso_data import get_ftso_time_series, compute_derived_features
            from .services.signal_generator import generate_market_signal
            from .services.external_data import get_external_indicators
        except ImportError as e:
            return json.dumps({
                "signal": "HOLD",
                "confidence": 0.0,
                "reasoning_short": f"Services not available: {e}",
                "reasoning_detailed": "Required prediction services could not be loaded.",
                "risk_flags": ["Service unavailable"],
                "recommended_action": "Do not change position until services are available.",
                "time_horizon_minutes": 0
            })
        
        try:
            # 1. Fetch FTSO time series
            time_series = await get_ftso_time_series(asset, horizon_minutes * 2)
            
            # 2. Compute derived features
            derived = compute_derived_features(time_series)
            
            # 3. Get external indicators (optional)
            external = {}
            if include_external:
                external = await get_external_indicators(asset)
            
            # 4. Generate signal
            signal_input = {
                "asset": asset,
                "horizon_minutes": horizon_minutes,
                "ftso_time_series": time_series,
                "derived_features": derived,
                "external_indicators": external,
                "risk_profile": risk_profile,
            }
            
            result = await generate_market_signal(signal_input)
            
            return json.dumps(result)
            
        except Exception as e:
            logger.exception("Error generating signal: %s", e)
            return json.dumps({
                "signal": "HOLD",
                "confidence": 0.0,
                "reasoning_short": f"Error generating signal: {str(e)}",
                "reasoning_detailed": "An error occurred during signal generation.",
                "risk_flags": ["Prediction error"],
                "recommended_action": "Do not change position until valid signal is available.",
                "time_horizon_minutes": 0
            })


class ComputeDerivedFeaturesTool(BaseTool):
    """
    Tool to compute derived technical features from price data.
    """
    name: str = "compute_features"
    description: str = """
    Compute derived technical features from FTSO price time series.
    
    Returns: returns (5m, 15m, 60m), volatility, SMA, RSI indicators.
    These features are used for signal generation.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "time_series": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "timestamp": {"type": "string"},
                        "price": {"type": "number"}
                    }
                },
                "description": "Array of {timestamp, price} data points"
            }
        },
        "required": ["time_series"]
    }

    async def execute(self, time_series: List[Dict[str, Any]]) -> str:
        """Compute derived technical features"""
        try:
            from .services.ftso_data import compute_derived_features
        except ImportError as e:
            return json.dumps({
                "success": False,
                "error": f"Feature computation service not available: {e}"
            })
        
        try:
            features = compute_derived_features(time_series)
            return json.dumps({
                "success": True,
                "features": features
            })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e)
            })


def create_flare_predictor_tools() -> List[BaseTool]:
    """Create and return all Flare Predictor tools."""
    return [
        GetFTSOPricesTool(),
        GetExternalIndicatorsTool(),
        GenerateSignalTool(),
        ComputeDerivedFeaturesTool(),
    ]
