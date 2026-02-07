"""
Butler Agent Tools

Tools for the Butler to:
- Query RAG (Qdrant + Mem0) — degrades gracefully if not configured
- Fill slots with slot_questioning
- Post jobs to FlareOrderBook
- Monitor job status and deliveries
- Handle data requests from worker agents
"""

import os
import json
import time
import asyncio
from typing import Any, Optional, Dict, List
from pydantic import Field

from ..shared.tool_base import BaseTool, ToolManager

# Import shared tools — graceful fallback for contracts
try:
    from ..shared.contracts import (
        get_contracts, post_job, get_bids_for_job, accept_bid, get_job_status,
        create_job, fund_job, assign_provider, mark_completed, place_bid,
        get_job, get_escrow_deposit, is_delivery_confirmed, manual_confirm_delivery,
        release_payment, register_agent, is_agent_active,
    )
except Exception:
    get_contracts = None  # type: ignore
    post_job = None  # type: ignore
    get_bids_for_job = None  # type: ignore
    accept_bid = None  # type: ignore
    get_job_status = None  # type: ignore
    create_job = None  # type: ignore
    fund_job = None  # type: ignore
    assign_provider = None  # type: ignore
    mark_completed = None  # type: ignore
    place_bid = None  # type: ignore
    get_job = None  # type: ignore
    get_escrow_deposit = None  # type: ignore
    is_delivery_confirmed = None  # type: ignore
    manual_confirm_delivery = None  # type: ignore
    release_payment = None  # type: ignore
    register_agent = None  # type: ignore
    is_agent_active = None  # type: ignore

# Optional slot filler — may not be available
try:
    from ..shared.slot_questioning import SlotFiller
except Exception:
    SlotFiller = None  # type: ignore

from ..shared.butler_comms import ButlerDataExchange


class RAGSearchTool(BaseTool):
    """
    Search knowledge base (Qdrant + Mem0) for relevant information.
    """
    name: str = "rag_search"
    description: str = """
    Search the knowledge base for relevant information to answer user questions.
    
    Use this when the user asks informational questions that might be answered
    from existing knowledge (restaurants, services, general info).
    
    Returns: List of relevant knowledge items with context.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query"
            },
            "user_id": {
                "type": "string",
                "description": "User ID for personalized results (optional)"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results (default 5)"
            }
        },
        "required": ["query"]
    }
    
    async def execute(self, query: str, user_id: str = "anonymous", limit: int = 5) -> str:
        """Search RAG knowledge base — degrades gracefully if Qdrant/Mem0 not configured."""
        results = {
            "query": query,
            "qdrant_results": [],
            "mem0_results": [],
        }

        # Try Qdrant
        qdrant_url = os.getenv("QDRANT_URL")
        if qdrant_url:
            try:
                from qdrant_client import QdrantClient
                qdrant = QdrantClient(
                    url=qdrant_url,
                    api_key=os.getenv("QDRANT_API_KEY")
                )
                # Placeholder search — would be real vector search in production
                results["qdrant_results"] = []
            except Exception as e:
                results["qdrant_error"] = str(e)
        else:
            results["qdrant_note"] = "Qdrant not configured — skipped"

        # Try Mem0
        mem0_key = os.getenv("MEM0_API_KEY")
        if mem0_key:
            try:
                from mem0 import MemoryClient
                mem0_client = MemoryClient(api_key=mem0_key)
                mem_results = mem0_client.search(query, user_id=user_id, limit=limit)
                if mem_results:
                    results["mem0_results"] = [m.get("memory") for m in mem_results if "memory" in m]
            except Exception as e:
                results["mem0_error"] = str(e)
        else:
            results["mem0_note"] = "Mem0 not configured — skipped"

        if results["qdrant_results"] or results["mem0_results"]:
            results["status"] = "match"
            results["instruction"] = "Use the information above to answer the user's question. Do NOT call any more tools. STOP."
        else:
            results["status"] = "no_match"
            results["instruction"] = "No relevant info found in knowledge base. DECIDE: If user wants a job -> `fill_slots`. If unclear -> Ask user to clarify. STOP."

        return json.dumps(results, indent=2)


class SlotFillingTool(BaseTool):
    """
    Fill missing slots for job posting using slot_questioning.
    """
    name: str = "fill_slots"
    description: str = """
    Analyze user request and identify missing required parameters (slots).
    
    Use this when the user wants to post a job but hasn't provided all details.
    Returns: Missing slots and suggested clarifying questions.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "user_message": {
                "type": "string",
                "description": "The user's request"
            },
            "current_slots": {
                "type": "object",
                "description": "Already collected slot values"
            },
            "candidate_tools": {
                "type": "array",
                "description": "Available tools/job types",
                "items": {
                    "type": "object"
                }
            }
        },
        "required": ["user_message"]
    }
    
    async def execute(
        self, 
        user_message: str, 
        current_slots: Optional[Dict] = None,
        candidate_tools: Optional[List] = None
    ) -> str:
        """Fill slots using SlotFiller — falls back to basic extraction if unavailable"""
        try:
            if candidate_tools is None:
                candidate_tools = [
                    {"name": "hackathon_registration", "required_params": ["location", "theme", "date_range", "online_or_in_person"]},
                    {"name": "hotel_booking", "required_params": ["location", "dates", "guests"]},
                    {"name": "restaurant_booking", "required_params": ["location", "cuisine", "date", "guests"]},
                    {"name": "call_verification", "required_params": ["phone_number", "purpose"]},
                    {"name": "web_scraping", "required_params": ["url", "data_points"]},
                    {"name": "data_analysis", "required_params": ["data_source", "analysis_type"]},
                ]
            
            current_slots = current_slots or {}
            
            # Try to use SlotFiller if available
            if SlotFiller is not None:
                try:
                    filler = SlotFiller(user_id="butler")
                    missing_slots, questions, chosen_tool = filler.fill(
                        user_message=user_message,
                        current_slots=current_slots,
                        candidate_tools=candidate_tools
                    )
                    
                    result = {
                        "tool": chosen_tool,
                        "current_slots": current_slots,
                        "missing_slots": missing_slots,
                        "questions": questions,
                        "ready": len(missing_slots) == 0
                    }
                    
                    if not result["ready"]:
                        result["instruction"] = "CRITICAL: Ask the user the questions in the 'questions' list naturally. Do NOT call this tool again until the user responds."
                    else:
                        result["instruction"] = (
                            "All details gathered. Summarize what you will do and ask the user: "
                            "'Shall I go ahead?' Do NOT mention jobs, bids, or posting. "
                            "IMPORTANT: When the user confirms, you MUST call the `post_job` tool "
                            "with description, tool, and parameters. NEVER output JSON as text."
                        )
                    
                    return json.dumps(result, indent=2)
                    
                except Exception as e:
                    pass  # Fall through to basic extraction

            # Basic slot extraction fallback (no SlotFiller dependency)
            msg_lower = user_message.lower()
            chosen_tool = "general_task"
            for ct in candidate_tools:
                name = ct.get("name", "")
                if any(kw in msg_lower for kw in name.replace("_", " ").split()):
                    chosen_tool = name
                    break

            tool_def = next((ct for ct in candidate_tools if ct["name"] == chosen_tool), candidate_tools[0])
            required = tool_def.get("required_params", [])
            missing = [p for p in required if p not in current_slots]
            questions = [f"Could you provide the {p.replace('_', ' ')}?" for p in missing]

            result = {
                "tool": chosen_tool,
                "current_slots": current_slots,
                "missing_slots": missing,
                "questions": questions,
                "ready": len(missing) == 0,
            }
            if not result["ready"]:
                result["instruction"] = "CRITICAL: Ask the user the questions in the 'questions' list naturally. Do NOT call this tool again until the user responds."
            else:
                result["instruction"] = (
                    "All details gathered. Summarize what you will do and ask the user: "
                    "'Shall I go ahead?' Do NOT mention jobs, bids, or posting. "
                    "IMPORTANT: When the user confirms, you MUST call the `post_job` tool "
                    "with description, tool, and parameters. NEVER output JSON as text."
                )

            return json.dumps(result, indent=2)
                
        except Exception as e:
            return json.dumps({"error": str(e)})


class PostJobTool(BaseTool):
    """
    Post a job to the marketplace and auto-select the best bid.
    """
    name: str = "post_job"
    description: str = """
    Post a job to the SOTA marketplace.

    This will:
    1. Broadcast the job to all registered worker agents
    2. Collect bids for 60 seconds
    3. Auto-select the best offer (lowest price under budget)
    4. Optionally accept the winning bid on-chain

    Use after slots are filled and user confirms.
    Returns the winning bid (or "no bids" if none arrived).
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "Job description"
            },
            "tool": {
                "type": "string",
                "description": "Tool/job type (e.g., hotel_booking, call_verification)"
            },
            "parameters": {
                "type": "object",
                "description": "Job parameters as key-value pairs"
            },
            "budget_usd": {
                "type": "number",
                "description": "Maximum budget in USD — FTSO converts to C2FLR on-chain (default 0.02 ≈ 2 C2FLR)"
            },
            "deadline_hours": {
                "type": "integer",
                "description": "Deadline in hours from now (default 24)"
            }
        },
        "required": ["description", "tool", "parameters"]
    }

    async def execute(
        self,
        description: str,
        tool: str,
        parameters: Dict[str, Any],
        budget_usd: float = 0.02,
        deadline_hours: int = 24,
    ) -> str:
        """
        Post job ON-CHAIN → broadcast to in-process JobBoard for worker
        matching → return escrow funding info so the USER's wallet can
        lock C2FLR. Backend does NOT fund escrow (user's money, user's wallet).
        """
        from ..shared.job_board import JobBoard, JobListing, BidResult
        import uuid

        try:
            pk = os.getenv("FLARE_PRIVATE_KEY")
            poster = "0x0"
            on_chain_job_id = None
            escrow_address = None
            flr_required = 2.0  # fallback: ~2 C2FLR

            # ── 1. Create job on-chain via FlareOrderBook ────────
            if pk and create_job is not None:
                try:
                    c = get_contracts(pk)
                    poster = c.account.address
                    escrow_address = c.addresses.flare_escrow
                    metadata_uri = f"ipfs://sota-{tool}-{int(time.time())}"
                    on_chain_job_id = create_job(
                        c,
                        metadata_uri=metadata_uri,
                        max_price_usd=budget_usd,
                        deadline_seconds=deadline_hours * 3600,
                    )
                    print(f"✅ On-chain job created: #{on_chain_job_id}")

                    # Get FTSO quote: convert USD budget → C2FLR for escrow
                    try:
                        from ..shared.flare_contracts import quote_usd_to_flr
                        flr_required = quote_usd_to_flr(c, budget_usd)
                        # Add 5% buffer for price movement
                        flr_required = round(flr_required * 1.05, 4)
                        print(f"💰 FTSO quote: ${budget_usd} USD → {flr_required} C2FLR (with 5% buffer)")
                    except Exception as q_err:
                        print(f"⚠️ FTSO quote failed: {q_err}")
                        flr_required = 2.0

                    # NOTE: Escrow funding is NOT done here.
                    # The user's connected wallet will fund the escrow
                    # via the frontend after bid acceptance.

                except Exception as chain_err:
                    print(f"⚠️ On-chain creation failed (continuing off-chain): {chain_err}")

            # ── 2. Broadcast to in-memory JobBoard for worker matching ──
            job_id_str = str(on_chain_job_id) if on_chain_job_id else str(uuid.uuid4())[:8]
            deadline = int(time.time()) + (deadline_hours * 3600)

            listing = JobListing(
                job_id=job_id_str,
                description=description,
                tags=[tool],
                budget_flr=flr_required,  # bids are in C2FLR (FTSO-converted)
                deadline_ts=deadline,
                poster=poster,
                metadata={
                    "tool": tool,
                    "parameters": parameters,
                    "on_chain_job_id": on_chain_job_id,
                    "posted_at": time.time(),
                },
                bid_window_seconds=30,  # 30s for in-process workers
            )

            print(f"📢 Job {job_id_str} posted — collecting bids for {listing.bid_window_seconds}s…")

            # On-chain accept callback: assigns provider on-chain
            async def _accept_on_chain(winning_bid):
                if on_chain_job_id and pk and assign_provider is not None:
                    try:
                        c = get_contracts(pk)
                        addr = winning_bid.bidder_address
                        if addr and addr != "0x0":
                            assign_provider(c, on_chain_job_id, addr)
                            print(f"✅ On-chain provider assigned: {addr[:10]}…")
                    except Exception as exc:
                        print(f"⚠️ On-chain assign skipped: {exc}")

            board = JobBoard.instance()
            result: BidResult = await board.post_and_select(
                listing,
                on_chain_accept=_accept_on_chain,
            )

            # ── 3. After winner selected → return result with escrow info ──
            if result.winning_bid:
                w = result.winning_bid
                # Start async monitoring for delivery
                asyncio.create_task(
                    self._monitor_and_release(on_chain_job_id, job_id_str)
                )
                return json.dumps({
                    "success": True,
                    "job_id": job_id_str,
                    "on_chain_job_id": on_chain_job_id,
                    "winning_bid": {
                        "bidder": w.bidder_id,
                        "address": w.bidder_address,
                        "price_flr": w.amount_flr,
                        "eta_seconds": w.estimated_seconds,
                        "tags": w.tags,
                    },
                    "total_bids": len(result.all_bids),
                    "reason": result.reason,
                    "escrow": {
                        "address": escrow_address,
                        "flr_required": flr_required,
                        "budget_usd": budget_usd,
                        "needs_user_funding": True,
                    },
                    "instruction": (
                        "Great news — a specialist has been assigned and is working on it now. "
                        f"Estimated time: about {w.estimated_seconds // 60} minutes. "
                        f"The escrow requires {flr_required:.4f} C2FLR (${budget_usd} USD via FTSO) to lock the payment. "
                        "Tell the user you're on it and they can check back for updates. "
                        "Do NOT mention bids, workers, or job IDs."
                    ),
                }, indent=2)
            else:
                return json.dumps({
                    "success": False,
                    "job_id": job_id_str,
                    "on_chain_job_id": on_chain_job_id,
                    "total_bids": len(result.all_bids),
                    "reason": result.reason,
                    "instruction": (
                        "No one is available right now. Tell the user: "
                        "'I wasn't able to find anyone available at the moment — "
                        "would you like me to try again in a few minutes?' "
                        "Do NOT mention bids, marketplace, or technical details."
                    ),
                }, indent=2)

        except Exception as e:
            return json.dumps({"error": f"Failed to post job: {str(e)}"})

    async def _monitor_and_release(self, on_chain_job_id: Optional[int], board_job_id: str):
        """Background task: poll job status → auto-confirm delivery → release payment."""
        if not on_chain_job_id:
            return
        pk = os.getenv("FLARE_PRIVATE_KEY")
        if not pk or get_job is None:
            return

        try:
            for _ in range(60):  # Poll for up to 10 minutes (every 10s)
                await asyncio.sleep(10)
                try:
                    c = get_contracts(pk)
                    job_data = get_job(c, on_chain_job_id)
                    status = job_data.get("status", 0)

                    # Status 2 = COMPLETED (worker submitted delivery)
                    if status >= 2:
                        # FDC bypass for testnet: manually confirm delivery
                        if manual_confirm_delivery is not None:
                            try:
                                manual_confirm_delivery(c, on_chain_job_id)
                                print(f"✅ FDC delivery confirmed (manual bypass) for job #{on_chain_job_id}")
                            except Exception:
                                pass  # Already confirmed or not owner

                        # Release escrow payment
                        if release_payment is not None and is_delivery_confirmed is not None:
                            try:
                                if is_delivery_confirmed(c, on_chain_job_id):
                                    release_payment(c, on_chain_job_id)
                                    print(f"💰 Payment released for job #{on_chain_job_id}")
                            except Exception as rel_err:
                                print(f"⚠️ Release skipped: {rel_err}")
                        return

                    # Status 3+ = RELEASED/CANCELLED — done
                    if status >= 3:
                        return

                except Exception:
                    pass  # Network error, retry

        except Exception as e:
            print(f"⚠️ Monitor task error: {e}")


class GetBidsTool(BaseTool):
    """
    Get bids for a job.
    """
    name: str = "get_bids"
    description: str = """
    Retrieve all bids for a specific job.
    
    Use after posting a job to see which agents have bid.
    Returns: List of bids with prices, agents, and delivery times.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "job_id": {
                "type": "integer",
                "description": "The job ID"
            }
        },
        "required": ["job_id"]
    }
    
    async def execute(self, job_id: int) -> str:
        """Get bids for job — tries on-chain first, falls back to JobBoard."""
        try:
            # Try on-chain bids first
            pk = os.getenv("FLARE_PRIVATE_KEY")
            if pk and get_bids_for_job is not None:
                try:
                    contracts = get_contracts(pk)
                    bids = get_bids_for_job(contracts, job_id)

                    formatted_bids = []
                    for bid in bids:
                        formatted_bids.append({
                            "bid_id": bid[0],
                            "bidder": bid[2],
                            "price_flr": bid[3] / 1e6,
                            "delivery_time_hours": bid[4] / 3600,
                            "reputation": bid[5],
                            "accepted": bid[8]
                        })
                    formatted_bids.sort(key=lambda x: x["price_flr"])

                    return json.dumps({
                        "job_id": job_id,
                        "source": "on_chain",
                        "total_bids": len(formatted_bids),
                        "bids": formatted_bids,
                        "best_bid": formatted_bids[0] if formatted_bids else None,
                        "instruction": "Update the user on progress. Do NOT expose bid IDs, prices, or technical details. STOP."
                    }, indent=2)
                except Exception:
                    pass

            # Fallback: check in-memory JobBoard
            from ..shared.job_board import JobBoard
            board = JobBoard.instance()
            board_bids = board.get_bids(str(job_id))
            if board_bids:
                formatted = [{
                    "bidder": b.bidder_id,
                    "price_flr": b.amount_flr,
                    "eta_seconds": b.estimated_seconds,
                } for b in board_bids]
                return json.dumps({
                    "job_id": job_id,
                    "source": "job_board",
                    "total_bids": len(formatted),
                    "bids": formatted,
                    "instruction": "Update the user on progress. STOP."
                }, indent=2)

            return json.dumps({"job_id": job_id, "total_bids": 0, "bids": []}, indent=2)

        except Exception as e:
            return json.dumps({"error": f"Failed to get bids: {str(e)}"})


class AcceptBidTool(BaseTool):
    """
    Accept a bid for a job.
    """
    name: str = "accept_bid"
    description: str = """
    Accept a specific bid for a job, locking funds in escrow.
    
    Use after reviewing bids and getting user confirmation.
    The agent will then start working on the job.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "job_id": {
                "type": "integer",
                "description": "The job ID"
            },
            "bid_id": {
                "type": "integer",
                "description": "The bid ID to accept"
            }
        },
        "required": ["job_id", "bid_id"]
    }
    
    async def execute(self, job_id: int, bid_id: int) -> str:
        """Accept a bid on-chain and fund escrow."""
        try:
            pk = os.getenv("FLARE_PRIVATE_KEY")
            if not pk or accept_bid is None:
                return json.dumps({"error": "Flare contracts not configured"})

            contracts = get_contracts(pk)

            tx_hash = accept_bid(
                contracts,
                job_id=job_id,
                bid_id=bid_id,
                response_uri=""
            )

            # Also fund escrow if not already funded
            if fund_job is not None:
                try:
                    job_data = get_job(contracts, job_id) if get_job else {}
                    budget_usd = job_data.get("max_price_usd", 10.0)
                    bid_data = get_bids_for_job(contracts, job_id) if get_bids_for_job else []
                    provider = "0x0"
                    for b in bid_data:
                        if b[0] == bid_id:
                            provider = b[2]
                            break
                    if provider != "0x0":
                        fund_job(contracts, job_id, provider, budget_usd)
                        print(f"✅ Escrow funded for job #{job_id}")
                except Exception as fund_err:
                    print(f"⚠️ Escrow funding after accept: {fund_err}")

            return json.dumps({
                "success": True,
                "job_id": job_id,
                "bid_id": bid_id,
                "tx_hash": tx_hash,
                "message": "Bid accepted! Funds locked in escrow. Agent will start work."
            }, indent=2)
            
        except Exception as e:
            return json.dumps({"error": f"Failed to accept bid: {str(e)}"})


class CheckJobStatusTool(BaseTool):
    """
    Check the status of a job.
    """
    name: str = "check_job_status"
    description: str = """
    Check the current status of a job (Open, InProgress, Completed, Cancelled).
    
    Use to monitor job progress or check if delivery is complete.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "job_id": {
                "type": "integer",
                "description": "The job ID"
            }
        },
        "required": ["job_id"]
    }
    
    async def execute(self, job_id: int) -> str:
        """Check job status from on-chain + FDC."""
        try:
            pk = os.getenv("FLARE_PRIVATE_KEY")
            if not pk or get_job is None:
                return json.dumps({"error": "Flare contracts not configured"})

            contracts = get_contracts(pk)
            job_data = get_job(contracts, job_id)

            status_names = ["OPEN", "ASSIGNED", "COMPLETED", "RELEASED", "CANCELLED"]
            status_idx = job_data.get("status", 0)
            status = status_names[status_idx] if status_idx < len(status_names) else "UNKNOWN"

            # Check FDC attestation
            fdc_ok = False
            if is_delivery_confirmed is not None:
                try:
                    fdc_ok = is_delivery_confirmed(contracts, job_id)
                except Exception:
                    pass

            # Check escrow
            escrow_info = {}
            if get_escrow_deposit is not None:
                try:
                    escrow_info = get_escrow_deposit(contracts, job_id)
                except Exception:
                    pass

            result = {
                "job_id": job_id,
                "status": status,
                "poster": job_data.get("poster", ""),
                "provider": job_data.get("provider", ""),
                "budget_usd": job_data.get("max_price_usd", 0),
                "budget_flr": job_data.get("max_price_flr", 0),
                "fdc_confirmed": fdc_ok,
                "escrow_funded": escrow_info.get("funded", False),
                "escrow_released": escrow_info.get("released", False),
                "delivery_proof": job_data.get("delivery_proof", ""),
            }
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return json.dumps({"error": f"Failed to check status: {str(e)}"})


class GetDeliveryTool(BaseTool):
    """
    Get delivery results.
    """
    name: str = "get_delivery"
    description: str = """
    Download and retrieve job delivery results.
    
    Use when job is completed to get the actual results/data.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "job_id": {
                "type": "integer",
                "description": "The job ID"
            }
        },
        "required": ["job_id"]
    }
    
    async def execute(self, job_id: int) -> str:
        """Get delivery — checks on-chain status and agent updates."""
        try:
            pk = os.getenv("FLARE_PRIVATE_KEY")
            result = {"job_id": job_id}

            # On-chain job data
            if pk and get_job is not None:
                try:
                    contracts = get_contracts(pk)
                    job_data = get_job(contracts, job_id)
                    status_names = ["OPEN", "ASSIGNED", "COMPLETED", "RELEASED", "CANCELLED"]
                    status_idx = job_data.get("status", 0)
                    result["status"] = status_names[status_idx] if status_idx < len(status_names) else "UNKNOWN"
                    result["provider"] = job_data.get("provider", "")
                    result["delivery_proof"] = job_data.get("delivery_proof", "")

                    # Check FDC
                    if is_delivery_confirmed is not None:
                        result["fdc_confirmed"] = is_delivery_confirmed(contracts, job_id)
                except Exception as e:
                    result["chain_error"] = str(e)

            # Check agent updates from ButlerDataExchange
            from ..shared.butler_comms import ButlerDataExchange
            exchange = ButlerDataExchange.instance()
            updates = exchange.get_updates(str(job_id))
            if updates:
                result["agent_updates"] = updates
                # Find completed update with results
                for u in reversed(updates):
                    if u.get("status") == "completed" and u.get("data"):
                        result["delivery_data"] = u["data"]
                        break

            if result.get("delivery_data") or result.get("status") in ("COMPLETED", "RELEASED"):
                result["instruction"] = (
                    "The task is done! Share the results with the user in a clear, "
                    "friendly summary. Do NOT mention technical details."
                )
            else:
                result["instruction"] = (
                    "The task is still in progress. Let the user know the agent "
                    "is working on it."
                )

            return json.dumps(result, indent=2)
            
        except Exception as e:
            return json.dumps({"error": f"Failed to get delivery: {str(e)}"})


# ═════════════════════════════════════════════════════════════
#  Agent ↔ Butler Communication Tools
# ═════════════════════════════════════════════════════════════

class CheckAgentRequestsTool(BaseTool):
    """
    Check for pending data requests from worker agents.
    """
    name: str = "check_agent_requests"
    description: str = """
    Check if any worker agent (hackathon, caller, etc.) is requesting
    additional data from the user.

    Worker agents call this when they need info during job execution —
    for example, the hackathon agent might ask for the user's email
    or location preference.

    Returns pending requests with questions to relay to the user.
    Use this after posting a job to see if the assigned agent needs
    anything.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": "Job ID to check requests for (optional — omit for all)"
            }
        },
        "required": []
    }

    async def execute(self, job_id: str = None) -> str:
        """Check pending requests from agents."""
        exchange = ButlerDataExchange.instance()
        pending = exchange.peek_pending_requests(job_id)

        if not pending:
            return json.dumps({
                "pending_requests": [],
                "count": 0,
                "instruction": "No pending requests from worker agents. The job is proceeding normally.",
            })

        formatted = []
        for req in pending:
            formatted.append({
                "request_id": req.get("request_id"),
                "agent": req.get("agent", "unknown"),
                "data_type": req.get("data_type"),
                "question": req.get("question"),
                "fields": req.get("fields", []),
            })

        return json.dumps({
            "pending_requests": formatted,
            "count": len(formatted),
            "instruction": (
                "Worker agent(s) need data from the user. "
                "Present the questions to the user and use `answer_agent_request` "
                "to relay their answers back. STOP and wait for user input."
            ),
        }, indent=2)


class AnswerAgentRequestTool(BaseTool):
    """
    Answer a data request from a worker agent.
    """
    name: str = "answer_agent_request"
    description: str = """
    Send an answer back to a worker agent that requested data.

    After the user provides the requested information (profile data,
    preferences, confirmation, etc.), use this tool to relay the answer
    back to the waiting agent.

    Parameters:
      request_id: the ID from check_agent_requests
      data: key-value pairs of the answer data
      message: optional message
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "request_id": {
                "type": "string",
                "description": "The request ID to answer"
            },
            "data": {
                "type": "object",
                "description": "Answer data as key-value pairs"
            },
            "message": {
                "type": "string",
                "description": "Optional message"
            },
        },
        "required": ["request_id", "data"]
    }

    async def execute(self, request_id: str, data: dict, message: str = "") -> str:
        """Submit answer to agent request."""
        exchange = ButlerDataExchange.instance()
        exchange.submit_answer(request_id, {
            "request_id": request_id,
            "data": data,
            "message": message or "Answer provided by user via Butler",
        })

        # Also consume it from pending
        exchange.get_pending_requests()

        return json.dumps({
            "success": True,
            "request_id": request_id,
            "instruction": "Answer delivered to the worker agent. It will continue processing.",
        })


class GetAgentUpdatesTool(BaseTool):
    """
    Get status updates from worker agents.
    """
    name: str = "get_agent_updates"
    description: str = """
    Check for progress updates from worker agents executing jobs.

    Worker agents push updates like "Found 5 hackathons" or
    "Registration form filled — awaiting confirmation".

    Use this to keep the user informed about job progress.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": "Job ID to get updates for"
            }
        },
        "required": ["job_id"]
    }

    async def execute(self, job_id: str) -> str:
        """Get updates from agents."""
        exchange = ButlerDataExchange.instance()
        updates = exchange.get_updates(job_id)

        if not updates:
            return json.dumps({
                "updates": [],
                "count": 0,
                "instruction": "No new updates from the worker agent.",
            })

        return json.dumps({
            "updates": updates,
            "count": len(updates),
            "instruction": "Present these updates to the user. If there are questions, relay them.",
        }, indent=2)

def create_butler_tools() -> ToolManager:
    """Create and register all Butler tools"""
    tools = [
        # RAG and slot filling
        RAGSearchTool(),
        SlotFillingTool(),
        
        # Job posting and management
        PostJobTool(),
        GetBidsTool(),
        AcceptBidTool(),
        CheckJobStatusTool(),
        GetDeliveryTool(),

        # Agent ↔ Butler communication
        CheckAgentRequestsTool(),
        AnswerAgentRequestTool(),
        GetAgentUpdatesTool(),
    ]
    
    return ToolManager(tools=tools)
