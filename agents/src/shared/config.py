"""
Config — Re-exports from flare_config for backward compatibility.

All agent modules should import from here or from flare_config directly.
"""

# Re-export everything from flare_config so existing
# `from ..shared.config import ...` imports keep working.
from .flare_config import *  # noqa: F401,F403
from .flare_config import (
    NetworkConfig,
    FlareContractAddresses,
    AgentEndpoints,
    FLARE_COSTON2,
    FLARE_MAINNET,
    HARDHAT_LOCAL,
    get_network,
    get_contract_addresses,
    get_agent_endpoints,
    JobType,
    JOB_TYPE_LABELS,
    AGENT_CAPABILITIES,
    get_private_key,
)
