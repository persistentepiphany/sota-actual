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
import asyncio
from typing import Optional, List, Dict, Any

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
from agents.src.shared.butler_comms import ButlerDataExchange
from agents.src.shared.database import Database

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
db: Optional[Database] = None


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
    global contracts, db
    network = get_network()
    print(f"🚀 Starting SOTA Flare Butler API...")
    print(f"🌐 Network: {network.rpc_url} (chain {network.chain_id})")

    # ── Connect to PostgreSQL ────────────────────────────────
    try:
        db = await Database.connect()
        print("✅ Connected to PostgreSQL")
    except Exception as e:
        print(f"⚠️ PostgreSQL unavailable — running without persistence: {e}")

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


# ═════════════════════════════════════════════════════════════
#  Agent ↔ Butler Communication
# ═════════════════════════════════════════════════════════════
# These endpoints let worker agents (Hackathon, Caller, etc.)
# request additional data from the user via the Butler and
# push status updates back.
# ─────────────────────────────────────────────────────────────

# In-memory fallback for user context (used when DB is unavailable)
_user_context: Dict[str, Dict[str, Any]] = {}


class AgentDataRequest(BaseModel):
    """Incoming data request from a worker agent."""
    request_id: str
    job_id: str
    data_type: str          # user_profile, preference, confirmation, clarification, custom
    question: str
    fields: List[str] = []
    context: str = ""
    agent: str = ""


class AgentDataAnswer(BaseModel):
    """Butler's answer to an agent data request."""
    request_id: str
    data: Dict[str, Any] = {}
    message: str = ""


class AgentUpdate(BaseModel):
    """Status update pushed by a worker agent."""
    job_id: str
    status: str             # in_progress, partial_result, completed, error
    message: str
    data: Dict[str, Any] = {}
    agent: str = ""


class SetUserContextRequest(BaseModel):
    """Set user context that agents can retrieve."""
    user_id: str = "default"
    profile: Dict[str, Any] = {}


@app.post("/api/agent/set-user-context")
async def set_user_context(req: SetUserContextRequest):
    """
    Set the user context/profile that worker agents can retrieve.

    Call this BEFORE posting a job so the hackathon agent (or any
    worker) can access the user's info when it asks for it.
    Persists to PostgreSQL and keeps an in-memory cache.
    """
    # Always keep in-memory copy for fast reads
    _user_context[req.user_id] = req.profile

    # Persist to DB
    if db:
        try:
            await db.upsert_user_profile(req.user_id, req.profile)
        except Exception as e:
            print(f"⚠️ DB upsert_user_profile failed: {e}")

    return {"success": True, "user_id": req.user_id, "fields": list(req.profile.keys())}


@app.get("/api/agent/user-context/{user_id}")
async def get_user_context(user_id: str = "default"):
    """Get stored user context (DB first, then in-memory fallback)."""
    # Try DB first
    if db:
        try:
            profile = await db.get_user_profile(user_id)
            if profile:
                return profile
        except Exception as e:
            print(f"⚠️ DB get_user_profile failed: {e}")

    # Fallback to in-memory
    return _user_context.get(user_id, {})


@app.post("/api/agent/request-data")
async def handle_agent_data_request(req: AgentDataRequest):
    """
    Receive a data request from a worker agent.

    The Butler tries to answer immediately from stored user context.
    If the data isn't available, it queues the request for the user
    to answer (via the chat interface or a future poll endpoint).

    This is the key endpoint that enables agent → butler communication
    when a job is selected via the marketplace.
    """
    exchange = ButlerDataExchange.instance()

    # ── Try to auto-answer from stored user context ──────────
    if req.data_type == "user_profile":
        # Try DB first, then in-memory fallback
        profile = None
        if db:
            try:
                profile = await db.get_user_profile("default")
            except Exception:
                pass

        if not profile:
            # Fallback: search in-memory context
            for uid, ctx in _user_context.items():
                if ctx:
                    profile = ctx
                    break

        if profile:
            if req.fields:
                filtered = {k: v for k, v in profile.items()
                            if k in req.fields and v is not None}
                if filtered:
                    return {
                        "request_id": req.request_id,
                        "data_type": "user_profile",
                        "data": filtered,
                        "source": "stored_context",
                        "message": f"Profile data retrieved ({len(filtered)} fields)",
                    }
            else:
                # Strip internal DB fields
                clean = {k: v for k, v in profile.items()
                         if v is not None and k not in ("id", "createdAt", "updatedAt")}
                return {
                    "request_id": req.request_id,
                    "data_type": "user_profile",
                    "data": clean,
                    "source": "stored_context",
                    "message": f"Full profile retrieved ({len(clean)} fields)",
                }

    if req.data_type == "preference":
        # Check DB for preferences
        prefs = None
        if db:
            try:
                profile = await db.get_user_profile("default")
                if profile:
                    prefs = profile.get("preferences")
                    if isinstance(prefs, str):
                        import json as _json
                        prefs = _json.loads(prefs)
            except Exception:
                pass

        if not prefs:
            # Fallback: check in-memory context
            for uid, ctx in _user_context.items():
                prefs = ctx.get("preferences", {})
                if prefs:
                    break

        if prefs and req.fields:
            matched = {k: v for k, v in prefs.items() if k in req.fields}
            if matched:
                return {
                    "request_id": req.request_id,
                    "data_type": "preference",
                    "data": matched,
                    "source": "stored_context",
                    "message": f"Preferences found ({len(matched)} fields)",
                }

    # ── Auto-answer confirmations as "proceed" in automated mode ──
    if req.data_type == "confirmation":
        auto_confirm = os.getenv("BUTLER_AUTO_CONFIRM", "true").lower() == "true"
        if auto_confirm:
            return {
                "request_id": req.request_id,
                "data_type": "confirmation",
                "data": {"confirmed": True},
                "source": "auto_confirm",
                "message": "Auto-confirmed (BUTLER_AUTO_CONFIRM=true)",
            }

    # ── Queue for human answer ───────────────────────────────
    exchange.post_request(req.request_id, req.job_id, req.model_dump())

    return {
        "request_id": req.request_id,
        "data_type": req.data_type,
        "data": {},
        "source": "queued",
        "message": (
            f"Request queued — awaiting user response. "
            f"Agent '{req.agent}' asked: {req.question}"
        ),
    }


@app.get("/api/agent/pending-requests")
async def get_pending_requests(job_id: Optional[str] = None):
    """
    Get pending data requests from worker agents.

    The frontend or Butler chat can poll this to see what agents
    are asking for and relay questions to the user.
    """
    exchange = ButlerDataExchange.instance()
    pending = exchange.peek_pending_requests(job_id)
    return {"pending": pending, "count": len(pending)}


@app.post("/api/agent/answer")
async def answer_agent_request(req: AgentDataAnswer):
    """
    Submit an answer to a pending agent data request.

    Called by the Butler (or frontend) after the user provides
    the requested information.
    """
    exchange = ButlerDataExchange.instance()
    exchange.submit_answer(req.request_id, {
        "request_id": req.request_id,
        "data": req.data,
        "message": req.message or "Answer provided",
    })
    return {"success": True, "request_id": req.request_id}


@app.post("/api/agent/update")
async def receive_agent_update(update: AgentUpdate):
    """
    Receive a status update from a worker agent.

    The Butler stores these so the user can be kept informed
    about job progress.
    """
    exchange = ButlerDataExchange.instance()
    exchange.push_update(update.job_id, update.model_dump())
    return {"received": True, "job_id": update.job_id, "status": update.status}


@app.get("/api/agent/updates/{job_id}")
async def get_agent_updates(job_id: str):
    """
    Get status updates from worker agents for a specific job.

    The frontend can poll this to show real-time progress.
    """
    exchange = ButlerDataExchange.instance()
    updates = exchange.get_updates(job_id)
    return {"job_id": job_id, "updates": updates, "count": len(updates)}


if __name__ == "__main__":
    import uvicorn

    print("🚀 Starting SOTA Flare Butler API...")
    uvicorn.run(app, host="0.0.0.0", port=3001)
