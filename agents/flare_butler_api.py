"""
SOTA Flare Butler API — FastAPI Bridge

Exposes HTTP endpoints for the ElevenLabs voice agent and web frontend.
Internally delegates to the OpenAI-backed Butler Agent and in-memory marketplace.

Endpoints:
  POST /api/flare/chat      — Chat with OpenAI-backed Butler Agent
  POST /api/flare/query     — Alias for /api/flare/chat (backward compat)
  POST /api/flare/quote     — Get FTSO price quote (USD → FLR)
  POST /api/flare/create    — Create + fund a job on Flare
  POST /api/flare/status    — Check job status + FDC attestation
  POST /api/flare/release   — Release payment (FDC-gated)
  GET  /api/flare/price     — Current FLR/USD from FTSO
  GET  /api/flare/marketplace/jobs     — List marketplace jobs
  GET  /api/flare/marketplace/bids/{id} — Get bids for a job
  GET  /api/flare/marketplace/workers  — List registered workers
"""

import os
import sys
import time
import asyncio
import logging
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
try:
    from agents.src.shared.database import Database
except ImportError:
    Database = None  # type: ignore

# New: OpenAI Butler Agent + JobBoard marketplace
from agents.src.butler.agent import ButlerAgent, create_butler_agent
from agents.src.shared.job_board import JobBoard, JobStatus

# Worker agents — created in-process for JobBoard bidding
from agents.src.hackathon.agent import HackathonAgent, create_hackathon_agent
from agents.src.caller.agent import CallerAgent

# Flare Predictor — market signals using FTSO data
try:
    from src.flare_predictor.agent import FlarePredictor, create_flare_predictor_agent
except ImportError:
    FlarePredictor = None  # type: ignore
    create_flare_predictor_agent = None

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
butler_agent: Optional[ButlerAgent] = None
job_board: Optional[JobBoard] = None
hackathon_agent: Optional[HackathonAgent] = None
caller_agent: Optional[CallerAgent] = None
flare_predictor_agent: Optional["FlarePredictor"] = None  # Market signal agent


# ─── Request / Response Models ────────────────────────────────

class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    timestamp: Optional[int] = None


class ChatResponse(BaseModel):
    response: str
    session_id: Optional[str] = None
    model: str = "gpt-4o-mini"

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


class MarketplacePostRequest(BaseModel):
    """Accept the raw job JSON from ElevenLabs and post to marketplace."""
    model_config = {"extra": "allow"}

    task: str
    location: Optional[str] = None
    date_range: Optional[str] = None
    online_or_in_person: Optional[str] = None
    theme_technology_focus: Optional[Any] = None
    # Booking fields
    city: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    guests: Optional[int] = None
    cuisine: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    room_type: Optional[str] = None
    budget: Optional[str] = None
    budget_usd: float = 0.02  # USD — FTSO converts to ~2 C2FLR on-chain
    deadline_hours: int = 24
    wallet_address: Optional[str] = None


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


class PredictorRequest(BaseModel):
    """Request for Flare Predictor trading signal."""
    asset: str = "FLR/USD"
    horizon_minutes: int = 60
    risk_profile: str = "moderate"  # conservative, moderate, aggressive
    # User strategy (optional)
    risk_tolerance: Optional[str] = None
    investment_goal: Optional[str] = None
    time_horizon: Optional[str] = None
    position_size_percent: Optional[float] = None
    max_loss_percent: Optional[float] = None
    question: Optional[str] = None  # User's specific question


class PriceResponse(BaseModel):
    flr_usd: float
    timestamp: int
    network: str


# ─── Startup ──────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    global contracts, butler_agent, job_board, hackathon_agent, caller_agent
    network = get_network()
    print(f"🚀 Starting SOTA Flare Butler API...")
    print(f"🌐 Network: {network.rpc_url} (chain {network.chain_id})")

    # ── Connect to PostgreSQL ────────────────────────────────
    if Database is not None:
        try:
            db = await Database.connect()
            print("✅ Connected to PostgreSQL")
        except Exception as e:
            print(f"⚠️ PostgreSQL unavailable — running without persistence: {e}")
    else:
        print("⚠️ Database module not available — running without persistence")

    pk = get_private_key("butler")
    if not pk:
        print("⚠️ FLARE_PRIVATE_KEY not set. Read-only mode.")
        return

    # ── Flare contracts ──────────────────────────────────────
    try:
        contracts = get_flare_contracts(pk)
        print(f"✅ Connected to Flare ({network.native_currency})")
        print(f"🧾 FlareOrderBook: {contracts.addresses.flare_order_book}")
        print(f"🧾 FlareEscrow:    {contracts.addresses.flare_escrow}")
        print(f"🧾 FTSOConsumer:   {contracts.addresses.ftso_price_consumer}")
        print(f"🧾 FDCVerifier:    {contracts.addresses.fdc_verifier}")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")

    # ── OpenAI Butler Agent ──────────────────────────────────
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            butler_agent = create_butler_agent(
                private_key=pk,
                openai_api_key=openai_key,
            )
            print(f"🤖 Butler Agent initialized (OpenAI gpt-4o-mini)")
        except Exception as e:
            print(f"⚠️ Butler Agent init failed: {e}")
    else:
        print("⚠️ OPENAI_API_KEY not set — Butler Agent disabled (Flare endpoints still work)")

    # ── JobBoard Marketplace ─────────────────────────────────
    job_board = JobBoard.instance()
    print(f"🏪 JobBoard marketplace ready (in-memory)")

    # ── Register Worker Agents (in-process for JobBoard) ─────
    # These run in the same process so they can receive broadcasts
    # from the JobBoard and auto-bid on matching jobs.

    try:
        hackathon_agent = await create_hackathon_agent()
        print(f"🏆 HackathonAgent registered on JobBoard (tags: hackathon_registration)")
    except Exception as e:
        print(f"⚠️ HackathonAgent init failed (non-critical): {e}")

    try:
        caller_agent = CallerAgent()
        await caller_agent.initialize()
        caller_agent.register_on_board()
        print(f"📞 CallerAgent registered on JobBoard (tags: call_verification, hotel_booking)")
    except Exception as e:
        print(f"⚠️ CallerAgent init failed (non-critical): {e}")

    # Flare Predictor — market signals using FTSO
    global flare_predictor_agent
    if create_flare_predictor_agent:
        try:
            flare_predictor_agent = await create_flare_predictor_agent()
            print(f"📈 FlarePredictor registered on JobBoard (tags: market_prediction, trading_signal)")
        except Exception as e:
            print(f"⚠️ FlarePredictor init failed (non-critical): {e}")

    # Log registered workers
    workers = job_board.workers
    print(f"📊 {len(workers)} worker(s) registered: {list(workers.keys())}")


@app.get("/")
async def root():
    return {"status": "SOTA Flare Butler API running", "version": "2.0"}


# ─── Butler Agent Chat (OpenAI) ──────────────────────────────

@app.post("/api/flare/chat")
async def chat_with_butler(req: ChatRequest):
    """
    Send a message to the OpenAI-backed Butler Agent.
    The Butler uses tool-calling to search knowledge, fill slots,
    post jobs to the marketplace, and track deliveries.

    Returns:
      - response: str — friendly text for user
      - job_posted: dict|null — structured job data if a job was posted on-chain
    """
    if not butler_agent:
        raise HTTPException(503, "Butler Agent not initialized. Check OPENAI_API_KEY.")
    try:
        result = await butler_agent.chat(
            message=req.query,
            user_id=req.user_id or "web_user",
        )
        return {
            "response": result["response"],
            "session_id": req.session_id,
            "model": "gpt-4o-mini",
            "job_posted": result.get("job_posted"),
        }
    except Exception as e:
        logger.error("Butler chat error: %s", e)
        raise HTTPException(500, f"Butler chat failed: {e}")


@app.post("/api/flare/query")
async def query_butler_compat(req: ChatRequest):
    """Backward-compatible alias for /api/flare/chat."""
    result = await chat_with_butler(req)
    return {
        "response": result["response"],
        "message": result["response"],
        "session_id": result.get("session_id"),
        "job_posted": result.get("job_posted"),
    }


# ─── Marketplace Endpoints ───────────────────────────────────

@app.get("/api/flare/marketplace/jobs")
async def list_marketplace_jobs(status: Optional[str] = None):
    """List all jobs on the in-memory marketplace."""
    board = JobBoard.instance()
    if status == "open":
        jobs = board.list_open_jobs()
    else:
        jobs = board.list_all_jobs()

    return {
        "total": len(jobs),
        "jobs": [
            {
                "job_id": j.job_id,
                "description": j.description,
                "tags": j.tags,
                "budget_flr": j.budget_flr,
                "status": j.status.value,
                "poster": j.poster,
                "posted_at": j.posted_at,
                "deadline_ts": j.deadline_ts,
                "metadata": j.metadata,
            }
            for j in jobs
        ],
    }


@app.get("/api/flare/marketplace/bids/{job_id}")
async def get_marketplace_bids(job_id: str):
    """Get all bids for a specific marketplace job."""
    board = JobBoard.instance()
    bids = board.get_bids(job_id)
    job = board.get_job(job_id)

    return {
        "job_id": job_id,
        "job_status": job.status.value if job else "not_found",
        "total_bids": len(bids),
        "bids": [
            {
                "bid_id": b.bid_id,
                "bidder_id": b.bidder_id,
                "bidder_address": b.bidder_address,
                "amount_flr": b.amount_flr,
                "estimated_seconds": b.estimated_seconds,
                "tags": b.tags,
                "submitted_at": b.submitted_at,
            }
            for b in bids
        ],
    }


@app.get("/api/flare/marketplace/workers")
async def list_marketplace_workers():
    """List all registered worker agents."""
    board = JobBoard.instance()
    workers = board.workers

    return {
        "total": len(workers),
        "workers": [
            {
                "worker_id": w.worker_id,
                "address": w.address,
                "tags": w.tags,
                "max_concurrent": w.max_concurrent,
                "active_jobs": w.active_jobs,
            }
            for w in workers.values()
        ],
    }


# ─── Marketplace Post (from ElevenLabs) ──────────────────────

@app.post("/api/flare/marketplace/post")
async def post_job_from_elevenlabs(req: MarketplacePostRequest):
    """
    Receive a structured job JSON from ElevenLabs voice agent
    and post it to the marketplace.
    
    This is the bridge: ElevenLabs gathers info → creates JSON →
    calls this endpoint → job is posted to JobBoard → workers bid.
    """
    from agents.src.butler.tools import PostJobTool

    # Coerce theme_technology_focus: string -> list
    if isinstance(req.theme_technology_focus, str):
        req.theme_technology_focus = [
            t.strip() for t in req.theme_technology_focus.replace("/", ",").split(",") if t.strip()
        ]

    # Build description and parameters from the raw job fields
    task = req.task
    params = req.model_dump(
        exclude={"task", "budget_usd", "deadline_hours", "wallet_address"},
        exclude_none=True,
    )
    
    # Map task name to a tool type
    task_lower = task.lower().replace(" ", "_")
    TASK_TO_TOOL = {
        "hackathon_discovery": "hackathon_registration",
        "hackathon_registration": "hackathon_registration",
        "hotel_booking": "hotel_booking",
        "restaurant_booking": "restaurant_booking",
        "call_verification": "call_verification",
    }
    tool_type = TASK_TO_TOOL.get(task_lower, task_lower)
    
    # Fallback substring matching
    if tool_type == task_lower and tool_type not in TASK_TO_TOOL.values():
        if "hackathon" in task_lower:
            tool_type = "hackathon_registration"
        elif "hotel" in task_lower:
            tool_type = "hotel_booking"
        elif "restaurant" in task_lower:
            tool_type = "restaurant_booking"
        elif "call" in task_lower:
            tool_type = "call_verification"

    description = f"{task}: {', '.join(f'{k}={v}' for k, v in params.items())}"

    logger.info(f"📢 ElevenLabs job received: {tool_type} — {description}")
    print(f"📢 ElevenLabs job received: task={task}, tool={tool_type}")
    print(f"   params={params}")

    try:
        post_tool = PostJobTool()
        result = await post_tool.execute(
            description=description,
            tool=tool_type,
            parameters=params,
            budget_usd=req.budget_usd,
            deadline_hours=req.deadline_hours,
        )
        print(f"✅ Marketplace post result: {result[:200]}")
        return {
            "success": True,
            "message": result,
            "tool_type": tool_type,
            "description": description,
        }
    except Exception as e:
        logger.error(f"Marketplace post failed: {e}")
        print(f"❌ Marketplace post failed: {e}")
        return {
            "success": False,
            "message": f"Failed to post job: {e}",
            "tool_type": tool_type,
        }


# ─── Escrow Info (for frontend wallet funding) ───────────────

@app.get("/api/flare/escrow/info")
async def get_escrow_info():
    """
    Return the FlareEscrow contract address so the frontend
    can prompt the user to fund escrow from their own wallet.
    """
    if not contracts:
        raise HTTPException(503, "Not connected to Flare")
    return {
        "escrow_address": contracts.addresses.flare_escrow,
        "order_book_address": contracts.addresses.flare_order_book,
        "chain_id": get_network().chain_id,
        "native_currency": "C2FLR",
    }


@app.get("/api/flare/escrow/deposit/{job_id}")
async def get_escrow_deposit_info(job_id: int):
    """
    Check if a job's escrow has been funded and how much C2FLR is locked.
    """
    if not contracts:
        raise HTTPException(503, "Not connected to Flare")
    try:
        dep = get_escrow_deposit(contracts, job_id)
        return {
            "job_id": job_id,
            "funded": dep.get("funded", False),
            "amount_flr": dep.get("amount_flr", 0),
            "usd_value": dep.get("usd_value", 0),
            "released": dep.get("released", False),
            "refunded": dep.get("refunded", False),
            "poster": dep.get("poster", ""),
            "provider": dep.get("provider", ""),
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to get escrow deposit: {e}")


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


# ─── Flare Predictor Endpoint ────────────────────────────────

@app.post("/api/flare/predict")
async def predict_market_signal(req: PredictorRequest):
    """
    Generate trading signal using FTSO price data.
    
    Uses real-time Flare FTSO v2 prices and optional external indicators
    to produce actionable trading signals with LLM reasoning.
    
    Returns:
      - signal: STRONGLY_BUY | BUY | HOLD | SELL | STRONGLY_SELL
      - confidence: 0.0-1.0
      - reasoning: Detailed analysis
      - entry_zone, stop_loss, take_profit: Price levels
      - chat_summary: Human-friendly summary for chat display
    """
    try:
        from src.flare_predictor.services.ftso_data import (
            get_ftso_time_series, 
            compute_derived_features,
            get_current_ftso_price
        )
        from src.flare_predictor.services.signal_generator import generate_market_signal
        from src.flare_predictor.services.external_data import get_external_indicators
        
        # 1. Fetch current price and time series
        current_price = await get_current_ftso_price(req.asset)
        time_series = await get_ftso_time_series(req.asset, req.horizon_minutes * 2)
        
        # 2. Compute derived features (volatility, momentum, etc.)
        derived = compute_derived_features(time_series)
        
        # 3. Get external indicators via FDC
        external = await get_external_indicators(req.asset)
        
        # 4. Build user strategy context
        user_strategy = None
        if req.risk_tolerance or req.investment_goal:
            user_strategy = {
                "risk_tolerance": req.risk_tolerance or req.risk_profile,
                "investment_goal": req.investment_goal or "general_trading",
                "time_horizon": req.time_horizon or "short_term",
                "position_size_percent": req.position_size_percent or 5.0,
                "max_loss_percent": req.max_loss_percent or 2.0,
            }
        
        # 5. Generate signal via LLM
        signal_input = {
            "asset": req.asset,
            "horizon_minutes": req.horizon_minutes,
            "current_price": current_price,
            "ftso_time_series": time_series,
            "derived_features": derived,
            "external_indicators": external,
            "risk_profile": req.risk_profile,
            "user_strategy": user_strategy,
            "user_question": req.question,
        }
        
        result = await generate_market_signal(signal_input)
        
        logger.info("Generated %s signal for %s (confidence: %.2f)", 
                   result.get("signal"), req.asset, result.get("confidence", 0))
        
        return {
            "success": True,
            "asset": req.asset,
            "current_price": current_price,
            "horizon_minutes": req.horizon_minutes,
            **result
        }
        
    except Exception as e:
        logger.exception("Prediction error: %s", e)
        raise HTTPException(500, f"Prediction failed: {e}")


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
