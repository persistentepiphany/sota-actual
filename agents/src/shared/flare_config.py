"""
Flare Network Configuration for SOTA Agents

Replaces NeoX config with Flare Coston2 (testnet) and Flare mainnet.
Loads contract addresses from the Flare deployment JSON.
"""

import os
import json
from enum import IntEnum
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


# ─── Network Definitions ─────────────────────────────────────

@dataclass
class NetworkConfig:
    """Blockchain network configuration"""
    rpc_url: str
    chain_id: int
    explorer_url: str
    native_currency: str = "FLR"


@dataclass
class FlareContractAddresses:
    """Deployed Flare contract addresses"""
    ftso_price_consumer: str = ""
    fdc_verifier: str = ""
    flare_order_book: str = ""
    flare_escrow: str = ""
    agent_registry: str = ""


@dataclass
class AgentEndpoints:
    """A2A endpoint URLs for each agent"""
    manager: str = "http://localhost:3001"
    caller: str = "http://localhost:3003"
    hackathon: str = "http://localhost:3005"


# ─── Flare Networks ──────────────────────────────────────────

FLARE_COSTON2 = NetworkConfig(
    rpc_url=os.getenv("FLARE_RPC_URL", "https://coston2-api.flare.network/ext/C/rpc"),
    chain_id=114,
    explorer_url="https://coston2-explorer.flare.network",
    native_currency="C2FLR",
)

FLARE_MAINNET = NetworkConfig(
    rpc_url="https://flare-api.flare.network/ext/C/rpc",
    chain_id=14,
    explorer_url="https://flare-explorer.flare.network",
    native_currency="FLR",
)

HARDHAT_LOCAL = NetworkConfig(
    rpc_url="http://127.0.0.1:8545",
    chain_id=31337,
    explorer_url="",
    native_currency="ETH",
)


def get_network() -> NetworkConfig:
    """Get the current network configuration based on FLARE_CHAIN_ID env."""
    chain_id = int(os.getenv("FLARE_CHAIN_ID", "114"))
    if chain_id == 14:
        return FLARE_MAINNET
    elif chain_id == 31337:
        return HARDHAT_LOCAL
    return FLARE_COSTON2


def get_contract_addresses() -> FlareContractAddresses:
    """
    Load contract addresses from env vars or the Flare deployment JSON.
    Tries the latest deployment file matching the current chain ID.
    """
    # Try env vars first
    order_book = os.getenv("FLARE_ORDERBOOK_ADDRESS")
    if order_book:
        return FlareContractAddresses(
            ftso_price_consumer=os.getenv("FLARE_FTSO_ADDRESS", ""),
            fdc_verifier=os.getenv("FLARE_FDC_VERIFIER_ADDRESS", ""),
            flare_order_book=order_book,
            flare_escrow=os.getenv("FLARE_ESCROW_ADDRESS", ""),
            agent_registry=os.getenv("FLARE_AGENT_REGISTRY_ADDRESS", ""),
        )

    # Try deployment file
    network = get_network()
    deployment_names = [
        f"flare-coston2-{network.chain_id}.json",
        f"hardhat-local-{network.chain_id}.json",
        f"flare-mainnet-{network.chain_id}.json",
    ]

    contracts_dir = Path(__file__).parent.parent.parent.parent / "contracts" / "deployments"
    for name in deployment_names:
        path = contracts_dir / name
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                c = data.get("contracts", {})
                return FlareContractAddresses(
                    ftso_price_consumer=c.get("FTSOPriceConsumer", ""),
                    fdc_verifier=c.get("FDCVerifier", ""),
                    flare_order_book=c.get("FlareOrderBook", ""),
                    flare_escrow=c.get("FlareEscrow", ""),
                    agent_registry=c.get("AgentRegistry", ""),
                )

    # Empty fallback
    return FlareContractAddresses()


def get_agent_endpoints() -> AgentEndpoints:
    """Get agent A2A endpoints from environment."""
    return AgentEndpoints(
        manager=os.getenv("MANAGER_ENDPOINT", "http://localhost:3001"),
        caller=os.getenv("CALLER_ENDPOINT", "http://localhost:3003"),
        hackathon=os.getenv("HACKATHON_ENDPOINT", "http://localhost:3005"),
    )


# ─── Job / Agent Types ───────────────────────────────────────

class JobType(IntEnum):
    """Job types supported by SOTA agents"""
    HOTEL_BOOKING = 0
    RESTAURANT_BOOKING = 1
    HACKATHON_REGISTRATION = 2
    CALL_VERIFICATION = 5
    GENERIC = 6


JOB_TYPE_LABELS = {
    JobType.HOTEL_BOOKING: "Hotel Booking",
    JobType.RESTAURANT_BOOKING: "Restaurant Booking",
    JobType.HACKATHON_REGISTRATION: "Hackathon Registration",
    JobType.CALL_VERIFICATION: "Call Verification",
    JobType.GENERIC: "Generic Task",
}


AGENT_CAPABILITIES = {
    "BUTLER": ["job_planning", "agent_coordination", "user_interaction"],
    "CALLER": ["phone_call", "voice_verification", "reservation_booking"],
    "HACKATHON": ["hackathon_search", "web_scraping", "event_filtering"],
}


def get_private_key(agent_type: str = "butler") -> Optional[str]:
    """Get the private key for a specific agent type."""
    key_map = {
        "butler": "FLARE_PRIVATE_KEY",
        "worker": "WORKER_PRIVATE_KEY",
        "caller": "CALLER_PRIVATE_KEY",
        "hackathon": "HACKATHON_PRIVATE_KEY",
    }
    env_var = key_map.get(agent_type.lower(), "FLARE_PRIVATE_KEY")
    return os.getenv(env_var)
