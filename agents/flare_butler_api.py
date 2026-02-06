"""
SOTA Flare Butler API — FastAPI Bridge

Exposes HTTP endpoints for the ElevenLabs voice agent and web frontend.
Internally delegates to the LangGraph butler graph.

Endpoints:
  POST /api/flare/quote     — Get FTSO price quote (USD → FLR)
  POST /api/flare/create    — Create + fund a job on Flare
  POST /api/flare/status    — Check job status + FDC attestation
  POST /api/flare/release   — Release payment (FDC-gated)
  GET  /api/flare/price     — Current FLR/USD from FTSO
"""

import os
import sys
import time
from typing import Optional, List, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.src.shared.flare_config import get_private_key, get_network
from agents.src.shared.flare_contracts import (
    get_flare_contracts,
    FlareContracts,
    get_flr_usd_price,
    quote_usd_to_flr,
    create_job,
    assign_provider,
    fund_job,
    mark_completed,
    release_payment,
    manual_confirm_delivery,
    is_delivery_confirmed,
    get_job,
    get_escrow_deposit,
)

load_dotenv()

app = FastAPI(title="SOTA Flare Butler API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Globals ──────────────────────────────────────────────────

contracts: Optional[FlareContracts] = None


# ─── Request / Response Models ────────────────────────────────

class QuoteRequest(BaseModel):
    budget_usd: float


class QuoteResponse(BaseModel):
    budget_usd: float
    flr_amount: float
    flr_price_usd: float
    message: str


class CreateJobRequest(BaseModel):
    description: str
    budget_usd: float
    deadline_seconds: int = 86400
    provider_address: Optional[str] = None
    metadata_uri: Optional[str] = None


class CreateJobResponse(BaseModel):
    job_id: int
    tx_hash: str
    budget_usd: float
    flr_locked: float
    provider: str
    message: str


class JobStatusRequest(BaseModel):
    job_id: int


class JobStatusResponse(BaseModel):
    job_id: int
    status: str
    poster: str
    provider: str
    budget_usd: float
    budget_flr: float
    fdc_confirmed: bool
    escrow_funded: bool
    escrow_released: bool
    message: str


class ReleaseRequest(BaseModel):
    job_id: int


class PriceResponse(BaseModel):
    flr_usd: float
    timestamp: int
    network: str


# ─── Startup ──────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    global contracts
    network = get_network()
    print(f"🚀 Starting SOTA Flare Butler API...")
    print(f"🌐 Network: {network.rpc_url} (chain {network.chain_id})")

    pk = get_private_key("butler")
    if not pk:
        print("⚠️ FLARE_PRIVATE_KEY not set. Read-only mode.")
        return

    try:
        contracts = get_flare_contracts(pk)
        print(f"✅ Connected to Flare ({network.native_currency})")
        print(f"🧾 FlareOrderBook: {contracts.addresses.flare_order_book}")
        print(f"🧾 FlareEscrow:    {contracts.addresses.flare_escrow}")
        print(f"🧾 FTSOConsumer:   {contracts.addresses.ftso_price_consumer}")
        print(f"🧾 FDCVerifier:    {contracts.addresses.fdc_verifier}")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")


@app.get("/")
async def root():
    return {"status": "SOTA Flare Butler API running", "version": "2.0"}


# ─── FTSO: Price & Quote ─────────────────────────────────────

@app.get("/api/flare/price", response_model=PriceResponse)
async def get_price():
    """Get current FLR/USD price from FTSO."""
    if not contracts:
        raise HTTPException(503, "Not connected to Flare")
    try:
        price = get_flr_usd_price(contracts)
        network = get_network()
        return PriceResponse(
            flr_usd=price,
            timestamp=int(time.time()),
            network=f"{network.native_currency} (chain {network.chain_id})",
        )
    except Exception as e:
        raise HTTPException(500, f"FTSO price fetch failed: {e}")


@app.post("/api/flare/quote", response_model=QuoteResponse)
async def get_quote(req: QuoteRequest):
    """Get FTSO-powered quote: USD → FLR conversion."""
    if not contracts:
        raise HTTPException(503, "Not connected to Flare")
    try:
        flr_price = get_flr_usd_price(contracts)
        flr_amount = quote_usd_to_flr(contracts, req.budget_usd)
        return QuoteResponse(
            budget_usd=req.budget_usd,
            flr_amount=flr_amount,
            flr_price_usd=flr_price,
            message=f"${req.budget_usd:.2f} ≈ {flr_amount:.2f} FLR (FLR/USD: ${flr_price:.4f})",
        )
    except Exception as e:
        raise HTTPException(500, f"Quote failed: {e}")


# ─── Job Lifecycle ────────────────────────────────────────────

@app.post("/api/flare/create", response_model=CreateJobResponse)
async def create_and_fund_job(req: CreateJobRequest):
    """Create a job, assign provider, and fund escrow with FLR."""
    if not contracts:
        raise HTTPException(503, "Not connected to Flare")

    try:
        metadata_uri = req.metadata_uri or f"ipfs://sota-job-{int(time.time())}"

        # 1. Create job (FTSO-priced)
        job_id = create_job(
            contracts,
            metadata_uri=metadata_uri,
            max_price_usd=req.budget_usd,
            deadline_seconds=req.deadline_seconds,
        )

        # 2. Assign provider
        provider = req.provider_address or (
            contracts.account.address if contracts.account else ""
        )
        if provider:
            assign_provider(contracts, job_id, provider)

        # 3. Fund escrow
        tx = fund_job(
            contracts,
            job_id=job_id,
            provider_address=provider,
            usd_budget=req.budget_usd,
        )

        flr_amount = quote_usd_to_flr(contracts, req.budget_usd)

        return CreateJobResponse(
            job_id=job_id,
            tx_hash=tx,
            budget_usd=req.budget_usd,
            flr_locked=flr_amount,
            provider=provider,
            message=f"Job #{job_id} created and funded with {flr_amount:.2f} FLR",
        )
    except Exception as e:
        raise HTTPException(500, f"Job creation failed: {e}")


@app.post("/api/flare/status", response_model=JobStatusResponse)
async def check_status(req: JobStatusRequest):
    """Check job status + FDC attestation state."""
    if not contracts:
        raise HTTPException(503, "Not connected to Flare")

    try:
        job = get_job(contracts, req.job_id)
        fdc_ok = is_delivery_confirmed(contracts, req.job_id)

        deposit = {"funded": False, "released": False}
        try:
            deposit = get_escrow_deposit(contracts, req.job_id)
        except Exception:
            pass

        status_names = ["OPEN", "ASSIGNED", "COMPLETED", "RELEASED", "CANCELLED"]
        status = status_names[job["status"]] if job["status"] < len(status_names) else "UNKNOWN"

        return JobStatusResponse(
            job_id=req.job_id,
            status=status,
            poster=job["poster"],
            provider=job["provider"],
            budget_usd=job["max_price_usd"],
            budget_flr=job["max_price_flr"],
            fdc_confirmed=fdc_ok,
            escrow_funded=deposit.get("funded", False),
            escrow_released=deposit.get("released", False),
            message=f"Job #{req.job_id}: {status} | FDC: {'✅' if fdc_ok else '⏳'}",
        )
    except Exception as e:
        raise HTTPException(500, f"Status check failed: {e}")


@app.post("/api/flare/release")
async def release_job_payment(req: ReleaseRequest):
    """Release escrow payment. Requires FDC attestation."""
    if not contracts:
        raise HTTPException(503, "Not connected to Flare")

    try:
        # Check FDC gate first
        fdc_ok = is_delivery_confirmed(contracts, req.job_id)
        if not fdc_ok:
            raise HTTPException(
                400,
                "Cannot release: delivery not attested by FDC. "
                "The escrow release is driven by FDC, not the backend.",
            )

        tx = release_payment(contracts, req.job_id)
        return {
            "job_id": req.job_id,
            "tx_hash": tx,
            "fdc_confirmed": True,
            "message": f"Payment released for job #{req.job_id}. FDC attestation verified.",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Release failed: {e}")


# ─── Demo / Testing ──────────────────────────────────────────

@app.post("/api/flare/demo/confirm-delivery")
async def demo_confirm_delivery(req: ReleaseRequest):
    """
    Demo endpoint: manually confirm FDC delivery (owner-only).
    In production, this happens via real FDC Merkle proof verification.
    """
    if not contracts:
        raise HTTPException(503, "Not connected to Flare")
    try:
        tx = manual_confirm_delivery(contracts, req.job_id)
        return {
            "job_id": req.job_id,
            "tx_hash": tx,
            "message": f"FDC delivery manually confirmed for job #{req.job_id}",
        }
    except Exception as e:
        raise HTTPException(500, f"Manual confirm failed: {e}")


if __name__ == "__main__":
    import uvicorn

    print("🚀 Starting SOTA Flare Butler API...")
    uvicorn.run(app, host="0.0.0.0", port=3001)
