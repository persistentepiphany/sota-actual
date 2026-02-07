"""
Signal Generator Service

Generates discrete market signals using LLM reasoning over FTSO data
and external indicators. Outputs signals suitable for on-chain strategies.
Incorporates user strategy preferences for personalized signals.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Signal levels
SIGNALS = ["STRONGLY_SELL", "SELL", "HOLD", "BUY", "STRONGLY_BUY"]

# System prompt for signal generation with user strategy
SIGNAL_SYSTEM_PROMPT = """You are an on-chain trading advisor for the Flare blockchain.
Analyze the provided FTSO price data, indicators, and USER STRATEGY to generate a personalized market signal.

USER STRATEGY CONSIDERATIONS:
- Adjust signal strength based on user's risk_tolerance (conservative = mild signals, aggressive = stronger signals)
- Consider user's investment_goal (income = focus on stability, speculation = focus on momentum)
- Match time_horizon (scalp = immediate signals, long = trend-following)
- Respect max_position_size and stop_loss preferences in recommendations

OUTPUT FORMAT (JSON only):
{
  "signal": "STRONGLY_BUY | BUY | HOLD | SELL | STRONGLY_SELL",
  "confidence": 0.0-1.0,
  "reasoning_short": "One-sentence summary.",
  "reasoning_detailed": "2-4 bullet-style sentences explaining the analysis.",
  "risk_flags": ["List of risk concerns for this user's strategy"],
  "recommended_action": "Specific action considering user's strategy",
  "time_horizon_minutes": 60
}

GUIDELINES:
- Err on HOLD when indicators conflict or data is sparse
- For conservative users, prefer HOLD over weak BUY/SELL signals
- For aggressive users, be more decisive when momentum is clear
- Focus on momentum, volatility, mean reversion vs breakout
- Mention when indicators could be verified on-chain via FDC
- Never guarantee profits - probabilistic guidance only
- If user asked a specific question, address it directly"""


async def generate_market_signal(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a market trading signal using LLM reasoning.
    
    Args:
        input_data: Dictionary containing:
            - asset: Asset pair
            - horizon_minutes: Prediction horizon
            - ftso_time_series: Price history
            - derived_features: Technical indicators
            - external_indicators: Off-chain data
            - risk_profile: conservative/moderate/aggressive
            
    Returns:
        Signal dictionary with signal, confidence, reasoning, etc.
    """
    asset = input_data.get("asset", "Unknown")
    horizon = input_data.get("horizon_minutes", 60)
    time_series = input_data.get("ftso_time_series", [])
    derived = input_data.get("derived_features", {})
    external = input_data.get("external_indicators", {})
    risk_profile = input_data.get("risk_profile", "moderate")
    
    # Validate input
    if not time_series:
        return {
            "signal": "HOLD",
            "confidence": 0.0,
            "reasoning_short": "Insufficient or malformed input data.",
            "reasoning_detailed": "No FTSO time series data provided. Cannot generate signal without price history.",
            "risk_flags": ["Missing or invalid time series"],
            "recommended_action": "Do not change position until valid data is available.",
            "time_horizon_minutes": 0
        }
    
    try:
        # Try using OpenAI for intelligent signal generation
        signal = await _generate_signal_with_llm(input_data)
        return signal
    except Exception as e:
        logger.warning("LLM signal generation failed, using rule-based: %s", e)
        # Fallback to rule-based signal generation
        return _generate_signal_rule_based(input_data)


async def _generate_signal_with_llm(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate signal using OpenAI LLM."""
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("OpenAI not available")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    
    client = OpenAI(api_key=api_key)
    
    # Prepare input for LLM
    asset = input_data.get("asset")
    current_price = input_data.get("current_price", 0)
    horizon = input_data.get("horizon_minutes")
    time_series = input_data.get("ftso_time_series", [])
    derived = input_data.get("derived_features", {})
    external = input_data.get("external_indicators", {})
    risk_profile = input_data.get("risk_profile")
    user_strategy = input_data.get("user_strategy", {})
    user_question = input_data.get("user_question", "")
    
    # Get recent prices for context (last 5 data points)
    recent_prices = time_series[-5:] if len(time_series) >= 5 else time_series
    
    # Build user strategy section
    strategy_section = ""
    if user_strategy:
        strategy_section = f"""
USER STRATEGY (personalize your signal for this user):
- Risk Tolerance: {user_strategy.get('risk_tolerance', 'moderate')}
- Investment Goal: {user_strategy.get('investment_goal', 'growth')}
- Time Horizon: {user_strategy.get('time_horizon', 'short')}
- Max Position Size: {user_strategy.get('max_position_size_pct', 10)}% of portfolio
- Stop Loss: {user_strategy.get('stop_loss_pct', 5)}%
- Take Profit: {user_strategy.get('take_profit_pct', 10)}%
- Avoid High Volatility: {user_strategy.get('avoid_high_volatility', False)}
- Require Multiple Confirmations: {user_strategy.get('require_confirmation', True)}
"""
    
    # Build user question section
    question_section = ""
    if user_question:
        question_section = f"\nUSER'S QUESTION: {user_question}\nPlease address this in your analysis.\n"
    
    user_message = f"""Analyze this market data and generate a personalized trading signal:

Asset: {asset}
Current Price: ${current_price}
Prediction Horizon: {horizon} minutes
{strategy_section}
Recent FTSO Prices (last 5 data points from Flare oracle):
{json.dumps(recent_prices, indent=2)}

Derived Features (calculated from FTSO data):
- 5-minute return: {derived.get('return_5m', 'N/A')}
- 15-minute return: {derived.get('return_15m', 'N/A')}
- 60-minute return: {derived.get('return_60m', 'N/A')}
- 60-minute volatility: {derived.get('volatility_60m', 'N/A')}
- 15-minute SMA: {derived.get('sma_15m', 'N/A')}
- 60-minute SMA: {derived.get('sma_60m', 'N/A')}
- RSI (14): {derived.get('rsi_14', 'N/A')}

External Indicators (FDC-compatible off-chain data):
{json.dumps(external, indent=2)}
{question_section}
Generate a JSON response with signal, confidence, reasoning, risk_flags, and recommended_action tailored to this user's strategy."""

    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        messages=[
            {"role": "system", "content": SIGNAL_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        response_format={"type": "json_object"},
        temperature=0.3,  # Lower temperature for more consistent signals
        max_tokens=600,
    )
    
    result = json.loads(response.choices[0].message.content)
    
    # Ensure required fields
    result.setdefault("signal", "HOLD")
    result.setdefault("confidence", 0.5)
    result.setdefault("reasoning_short", "Signal generated from market analysis.")
    result.setdefault("reasoning_detailed", "Analysis based on FTSO price data and indicators.")
    result.setdefault("risk_flags", [])
    result.setdefault("recommended_action", "Monitor market conditions.")
    result.setdefault("time_horizon_minutes", horizon)
    
    return result


def _generate_signal_rule_based(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate signal using simple rule-based logic.
    Fallback when LLM is not available.
    """
    derived = input_data.get("derived_features", {})
    external = input_data.get("external_indicators", {})
    risk_profile = input_data.get("risk_profile", "moderate")
    horizon = input_data.get("horizon_minutes", 60)
    asset = input_data.get("asset", "Unknown")
    
    # Get indicators
    return_5m = derived.get("return_5m", 0)
    return_15m = derived.get("return_15m", 0)
    return_60m = derived.get("return_60m", 0)
    volatility = derived.get("volatility_60m", 0.02)
    rsi = derived.get("rsi_14", 50)
    sma_15m = derived.get("sma_15m", 0)
    sma_60m = derived.get("sma_60m", 0)
    
    fear_greed = external.get("fear_greed_index", 50)
    funding_rate = external.get("funding_rate", 0)
    
    # Scoring system
    score = 0  # -2 to +2 scale
    risk_flags = []
    reasoning_points = []
    
    # Momentum signals
    if return_15m > 0.01:
        score += 1
        reasoning_points.append(f"Positive 15m momentum (+{return_15m*100:.2f}%)")
    elif return_15m < -0.01:
        score -= 1
        reasoning_points.append(f"Negative 15m momentum ({return_15m*100:.2f}%)")
    
    # RSI signals
    if rsi > 70:
        score -= 0.5
        risk_flags.append("RSI indicates overbought conditions")
        reasoning_points.append(f"RSI at {rsi:.1f} suggests overbought")
    elif rsi < 30:
        score += 0.5
        reasoning_points.append(f"RSI at {rsi:.1f} suggests oversold (potential bounce)")
    
    # Trend analysis (SMA crossover)
    if sma_15m > sma_60m * 1.01:
        score += 0.5
        reasoning_points.append("Short-term SMA above long-term (bullish)")
    elif sma_15m < sma_60m * 0.99:
        score -= 0.5
        reasoning_points.append("Short-term SMA below long-term (bearish)")
    
    # Volatility check
    if volatility > 0.03:
        risk_flags.append("High short-term volatility")
    
    # Sentiment (external)
    if fear_greed < 25:
        score += 0.3
        reasoning_points.append("Extreme fear sentiment (contrarian bullish)")
    elif fear_greed > 75:
        score -= 0.3
        risk_flags.append("Extreme greed sentiment")
    
    # Funding rate
    if abs(funding_rate) > 0.0005:
        if funding_rate > 0:
            risk_flags.append("Positive funding rate (crowded longs)")
        else:
            reasoning_points.append("Negative funding (potential squeeze setup)")
    
    # Adjust for risk profile
    if risk_profile == "conservative":
        score *= 0.6
    elif risk_profile == "aggressive":
        score *= 1.3
    
    # Map score to signal
    if score >= 1.5:
        signal = "STRONGLY_BUY"
    elif score >= 0.7:
        signal = "BUY"
    elif score <= -1.5:
        signal = "STRONGLY_SELL"
    elif score <= -0.7:
        signal = "SELL"
    else:
        signal = "HOLD"
    
    # Calculate confidence
    confidence = min(0.9, max(0.1, 0.5 + abs(score) * 0.15))
    
    # Generate reasoning
    if not reasoning_points:
        reasoning_points = ["Mixed signals with no clear direction"]
    
    reasoning_detailed = " • ".join(reasoning_points)
    
    # Recommended action based on signal and risk profile
    action_map = {
        "STRONGLY_BUY": f"Increase {asset} allocation by 15-20% for {risk_profile} profile",
        "BUY": f"Increase {asset} allocation by 5-10%",
        "HOLD": f"Maintain current {asset} position; await clearer signals",
        "SELL": f"Reduce {asset} exposure by 5-10%",
        "STRONGLY_SELL": f"Reduce {asset} allocation by 15-20%; consider hedging",
    }
    
    return {
        "signal": signal,
        "confidence": round(confidence, 2),
        "reasoning_short": f"{signal} signal for {asset} based on momentum and sentiment analysis.",
        "reasoning_detailed": reasoning_detailed,
        "risk_flags": risk_flags if risk_flags else ["No significant risk flags"],
        "recommended_action": action_map.get(signal, "Monitor conditions"),
        "time_horizon_minutes": horizon
    }
