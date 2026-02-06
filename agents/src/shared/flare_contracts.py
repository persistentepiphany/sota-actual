"""
Flare Contract Bridge for SOTA Agents

Web3.py wrapper for interacting with FlareOrderBook, FlareEscrow,
FTSOPriceConsumer, FDCVerifier, and AgentRegistry on Flare.
"""

import json
import time
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass

from web3 import Web3
from web3.contract import Contract
from eth_account import Account
from eth_account.signers.local import LocalAccount

from .flare_config import get_network, get_contract_addresses, FlareContractAddresses


# ─── ABI Loading ──────────────────────────────────────────────

def _artifacts_dir() -> Path:
    """Path to compiled Hardhat artifacts"""
    return Path(__file__).parent.parent.parent.parent / "contracts" / "artifacts" / "contracts"


def load_abi(contract_name: str) -> list:
    """Load ABI from Hardhat artifacts (artifacts/contracts/<name>.sol/<name>.json)"""
    # Try artifacts directory first
    artifact_path = _artifacts_dir() / f"{contract_name}.sol" / f"{contract_name}.json"
    if artifact_path.exists():
        with open(artifact_path) as f:
            data = json.load(f)
            return data.get("abi", data)

    # Try mocks subdirectory
    mock_path = _artifacts_dir() / "mocks" / f"{contract_name}.sol" / f"{contract_name}.json"
    if mock_path.exists():
        with open(mock_path) as f:
            data = json.load(f)
            return data.get("abi", data)

    # Try integrations/spoon/abi (legacy)
    legacy_path = Path(__file__).parent.parent.parent.parent / "contracts" / "integrations" / "spoon" / "abi" / f"{contract_name}.json"
    if legacy_path.exists():
        with open(legacy_path) as f:
            data = json.load(f)
            return data if isinstance(data, list) else data.get("abi", [])

    raise FileNotFoundError(f"ABI not found for {contract_name}")


# ─── Contract Container ──────────────────────────────────────

@dataclass
class FlareContracts:
    """Container for all Flare contract instances"""
    w3: Web3
    account: Optional[LocalAccount]
    ftso: Contract
    fdc_verifier: Contract
    order_book: Contract
    escrow: Contract
    agent_registry: Contract
    addresses: FlareContractAddresses


def get_flare_contracts(private_key: Optional[str] = None) -> FlareContracts:
    """
    Initialise Web3 + all Flare contract instances.

    Args:
        private_key: Optional private key for signing transactions.

    Returns:
        FlareContracts with all connections ready.
    """
    network = get_network()
    addresses = get_contract_addresses()

    if not addresses.flare_order_book:
        raise ValueError(
            "Flare contract addresses not configured. "
            "Deploy contracts first and set FLARE_ORDERBOOK_ADDRESS or "
            "ensure deployments/flare-coston2-114.json exists."
        )

    w3 = Web3(Web3.HTTPProvider(network.rpc_url))

    account = None
    if private_key:
        account = Account.from_key(private_key)
        w3.eth.default_account = account.address

    def _contract(name: str, addr: str) -> Contract:
        return w3.eth.contract(
            address=Web3.to_checksum_address(addr),
            abi=load_abi(name),
        )

    return FlareContracts(
        w3=w3,
        account=account,
        ftso=_contract("FTSOPriceConsumer", addresses.ftso_price_consumer),
        fdc_verifier=_contract("FDCVerifier", addresses.fdc_verifier),
        order_book=_contract("FlareOrderBook", addresses.flare_order_book),
        escrow=_contract("FlareEscrow", addresses.flare_escrow),
        agent_registry=_contract("AgentRegistry", addresses.agent_registry),
        addresses=addresses,
    )


# ─── Transaction Helpers ─────────────────────────────────────

def _send_tx(contracts: FlareContracts, fn: Any, value: int = 0) -> str:
    """Build, sign, send a contract call. Returns tx hash hex."""
    if not contracts.account:
        raise ValueError("No account configured for signing")

    tx = fn.build_transaction({
        "from": contracts.account.address,
        "nonce": contracts.w3.eth.get_transaction_count(contracts.account.address),
        "gas": 600_000,
        "gasPrice": contracts.w3.eth.gas_price,
        "value": value,
    })
    signed = contracts.w3.eth.account.sign_transaction(tx, contracts.account.key)
    tx_hash = contracts.w3.eth.send_raw_transaction(signed.raw_transaction)
    return tx_hash.hex()


def _wait(contracts: FlareContracts, tx_hash: str, timeout: int = 120):
    """Wait for transaction receipt."""
    return contracts.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)


# ─── FTSO Helpers ─────────────────────────────────────────────

def get_flr_usd_price(contracts: FlareContracts) -> float:
    """Get current FLR/USD price from FTSO. Returns price as a float."""
    price_wei, _ts = contracts.ftso.functions.getFlrUsdPrice().call()
    return float(Web3.from_wei(price_wei, "ether"))


def quote_usd_to_flr(contracts: FlareContracts, usd_amount: float) -> float:
    """Convert USD to FLR using the on-chain FTSO quote. Returns FLR as float."""
    usd_wei = Web3.to_wei(usd_amount, "ether")
    flr_wei = contracts.order_book.functions.quoteUsdToFlr(usd_wei).call()
    return float(Web3.from_wei(flr_wei, "ether"))


# ─── Job Lifecycle ────────────────────────────────────────────

def create_job(
    contracts: FlareContracts,
    metadata_uri: str,
    max_price_usd: float,
    deadline_seconds: int = 86400,
) -> int:
    """
    Create a new job on FlareOrderBook.
    Uses FTSO to derive FLR price from USD budget.

    Returns: job ID
    """
    usd_wei = Web3.to_wei(max_price_usd, "ether")
    deadline = int(time.time()) + deadline_seconds

    fn = contracts.order_book.functions.createJob(metadata_uri, usd_wei, deadline)
    tx_hash = _send_tx(contracts, fn)
    receipt = _wait(contracts, tx_hash)

    logs = contracts.order_book.events.JobCreated().process_receipt(receipt)
    if logs:
        return logs[0]["args"]["jobId"]
    raise ValueError("JobCreated event not found")


def assign_provider(
    contracts: FlareContracts,
    job_id: int,
    provider_address: str,
) -> str:
    """Assign an agent to a job. Returns tx hash."""
    fn = contracts.order_book.functions.assignProvider(
        job_id,
        Web3.to_checksum_address(provider_address),
    )
    tx_hash = _send_tx(contracts, fn)
    _wait(contracts, tx_hash)
    return tx_hash


def fund_job(
    contracts: FlareContracts,
    job_id: int,
    provider_address: str,
    usd_budget: float,
    flr_amount: Optional[float] = None,
) -> str:
    """
    Fund the escrow for a job with native FLR.
    If flr_amount is None, uses FTSO to calculate required amount (+ 5% buffer).

    Returns: tx hash
    """
    usd_wei = Web3.to_wei(usd_budget, "ether")

    if flr_amount is None:
        flr_wei = contracts.ftso.functions.usdToFlr(usd_wei).call()
        # Add 5% buffer for price movement
        flr_wei = (flr_wei * 105) // 100
    else:
        flr_wei = Web3.to_wei(flr_amount, "ether")

    fn = contracts.escrow.functions.fundJob(
        job_id,
        Web3.to_checksum_address(provider_address),
        usd_wei,
    )
    tx_hash = _send_tx(contracts, fn, value=flr_wei)
    _wait(contracts, tx_hash)
    return tx_hash


def mark_completed(
    contracts: FlareContracts,
    job_id: int,
    proof_hash: bytes,
) -> str:
    """Agent marks job as completed with delivery proof. Returns tx hash."""
    fn = contracts.order_book.functions.markCompleted(job_id, proof_hash)
    tx_hash = _send_tx(contracts, fn)
    _wait(contracts, tx_hash)
    return tx_hash


def release_payment(contracts: FlareContracts, job_id: int) -> str:
    """
    Release escrow payment (requires FDC attestation).
    Will revert if FDCVerifier has not confirmed delivery.
    Returns tx hash.
    """
    fn = contracts.escrow.functions.releaseToProvider(job_id)
    tx_hash = _send_tx(contracts, fn)
    _wait(contracts, tx_hash)
    return tx_hash


# ─── FDC Helpers ──────────────────────────────────────────────

def is_delivery_confirmed(contracts: FlareContracts, job_id: int) -> bool:
    """Check if FDC has attested delivery for a job."""
    return contracts.fdc_verifier.functions.isDeliveryConfirmed(job_id).call()


def manual_confirm_delivery(contracts: FlareContracts, job_id: int) -> str:
    """Owner-only: manually confirm delivery (for testing/demo)."""
    fn = contracts.fdc_verifier.functions.manualConfirmDelivery(job_id)
    tx_hash = _send_tx(contracts, fn)
    _wait(contracts, tx_hash)
    return tx_hash


# ─── Job Queries ──────────────────────────────────────────────

def get_job(contracts: FlareContracts, job_id: int) -> dict:
    """Get job details from FlareOrderBook."""
    job = contracts.order_book.functions.getJob(job_id).call()
    # Returns: (id, poster, provider, metadataURI, maxPriceUsd, maxPriceFlr,
    #           deadline, status, deliveryProof, createdAt)
    return {
        "id": job[0],
        "poster": job[1],
        "provider": job[2],
        "metadata_uri": job[3],
        "max_price_usd": float(Web3.from_wei(job[4], "ether")),
        "max_price_flr": float(Web3.from_wei(job[5], "ether")),
        "deadline": job[6],
        "status": job[7],  # 0=OPEN, 1=ASSIGNED, 2=COMPLETED, 3=RELEASED, 4=CANCELLED
        "delivery_proof": job[8].hex() if isinstance(job[8], bytes) else job[8],
        "created_at": job[9],
    }


def get_job_count(contracts: FlareContracts) -> int:
    """Get total number of jobs."""
    return contracts.order_book.functions.totalJobs().call()


def get_escrow_deposit(contracts: FlareContracts, job_id: int) -> dict:
    """Get escrow deposit details."""
    dep = contracts.escrow.functions.getDeposit(job_id).call()
    return {
        "poster": dep[0],
        "provider": dep[1],
        "amount_flr": float(Web3.from_wei(dep[2], "ether")),
        "usd_value": float(Web3.from_wei(dep[3], "ether")),
        "funded": dep[4],
        "released": dep[5],
        "refunded": dep[6],
    }


# ─── Agent Registry ──────────────────────────────────────────

def register_agent(
    contracts: FlareContracts,
    name: str,
    metadata_uri: str,
    capabilities: list[str],
) -> str:
    """Register as an agent on AgentRegistry. Returns tx hash."""
    fn = contracts.agent_registry.functions.registerAgent(
        name, metadata_uri, capabilities
    )
    tx_hash = _send_tx(contracts, fn)
    _wait(contracts, tx_hash)
    return tx_hash


def is_agent_active(contracts: FlareContracts, address: str) -> bool:
    """Check if an address is a registered active agent."""
    return contracts.agent_registry.functions.isAgentActive(
        Web3.to_checksum_address(address)
    ).call()
