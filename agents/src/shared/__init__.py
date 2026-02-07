"""
SOTA Agents — Shared Utilities

Provides common functionality used across all agents on Flare:
- flare_config: Flare network settings (Coston2, Mainnet)
- flare_contracts: Smart contract interaction (FlareOrderBook, FlareEscrow, etc.)
- a2a: Agent-to-Agent communication protocol
"""

from .flare_config import *
from .flare_contracts import *
from .a2a import *

# Legacy modules below still reference deleted config/contracts/neofs.
# They are importable individually but not re-exported here until migrated.
# from .wallet import *
# from .events import *
# from .base_agent import *
# from .wallet_tools import *
# from .bidding_tools import *
