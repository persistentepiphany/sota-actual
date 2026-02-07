"""
SOTA Agents — Shared Utilities

Provides common functionality used across all agents on Flare:
- flare_config: Flare network settings (Coston2, Mainnet)
- flare_contracts: Smart contract interaction (FlareOrderBook, FlareEscrow, etc.)
- a2a: Agent-to-Agent communication protocol
- config: Re-exports from flare_config (backward compat)
- contracts: Re-exports from flare_contracts (backward compat)
- agent_runner: OpenAI-powered tool-calling agent loop
- tool_base: BaseTool + ToolManager for function-calling tools
- job_board: In-memory marketplace (JobBoard singleton)
"""

from .flare_config import *
from .flare_contracts import *
from .a2a import *

# New modules — OpenAI agent infrastructure
from .agent_runner import AgentRunner, LLMClient
from .tool_base import BaseTool, ToolManager
from .job_board import JobBoard, JobListing, Bid, BidResult, JobStatus
