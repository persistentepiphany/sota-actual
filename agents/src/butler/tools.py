"""
Butler Agent Tools

Tools for the Butler to:
- Query RAG (Qdrant + Mem0) — degrades gracefully if not configured
- Fill slots with slot_questioning
- Post jobs to FlareOrderBook
- Monitor job status and deliveries
"""

import os
import json
import time
from typing import Any, Optional, Dict, List
from pydantic import Field

from ..shared.tool_base import BaseTool, ToolManager

# Import shared tools — graceful fallback for contracts
try:
    from ..shared.contracts import get_contracts, post_job, get_bids_for_job, accept_bid, get_job_status
except Exception:
    get_contracts = None  # type: ignore
    post_job = None  # type: ignore
    get_bids_for_job = None  # type: ignore
    accept_bid = None  # type: ignore
    get_job_status = None  # type: ignore

# Optional slot filler — may not be available
try:
    from ..shared.slot_questioning import SlotFiller
except Exception:
    SlotFiller = None  # type: ignore


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
                    {"name": "call_verification", "required_params": ["phone_number", "purpose"]},
                    {"name": "hotel_booking", "required_params": ["location", "dates", "guests"]},
                    {"name": "data_analysis", "required_params": ["data_source", "analysis_type"]},
                    {"name": "web_scraping", "required_params": ["url", "data_points"]},
                    {"name": "social_media", "required_params": ["platform", "action", "target"]},
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
                        result["instruction"] = "All details gathered. Summarize what you will do and ask the user: 'Would you like me to go ahead and proceed with this?' Do NOT mention jobs, bids, or posting."
                    
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
                result["instruction"] = "All details gathered. Summarize what you will do and ask the user: 'Would you like me to go ahead and proceed with this?' Do NOT mention jobs, bids, or posting."

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
            "budget_usdc": {
                "type": "number",
                "description": "Maximum budget in USDC (default 10)"
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
        budget_usdc: float = 10.0,
        deadline_hours: int = 24,
    ) -> str:
        """Post job to the JobBoard → collect bids → pick winner."""
        from ..shared.job_board import JobBoard, JobListing, BidResult
        import hashlib, uuid

        try:
            # Poster address (best-effort)
            poster = "0x0"
            try:
                contracts = get_contracts(os.getenv("FLARE_PRIVATE_KEY"))
                poster = contracts.account.address
            except Exception:
                pass

            # Build the listing
            job_id = str(uuid.uuid4())[:8]
            deadline = int(time.time()) + (deadline_hours * 3600)

            listing = JobListing(
                job_id=job_id,
                description=description,
                tags=[tool],
                budget_usdc=budget_usdc,
                deadline_ts=deadline,
                poster=poster,
                metadata={
                    "tool": tool,
                    "parameters": parameters,
                    "posted_at": time.time(),
                },
                bid_window_seconds=60,
            )

            print(f"📢 Job {job_id} posted — collecting bids for 60 s…")

            # Optional on-chain accept callback
            async def _accept_on_chain(winning_bid):
                try:
                    c = get_contracts(os.getenv("FLARE_PRIVATE_KEY"))
                    from ..shared.contracts import accept_bid as chain_accept
                    chain_accept(c, job_id=int(winning_bid.job_id),
                                 bid_id=int(winning_bid.bid_id),
                                 response_uri="")
                except Exception as exc:
                    print(f"⚠️ On-chain accept skipped: {exc}")

            board = JobBoard.instance()
            result: BidResult = await board.post_and_select(
                listing,
                on_chain_accept=_accept_on_chain,
            )

            # Format result for LLM / user
            if result.winning_bid:
                w = result.winning_bid
                return json.dumps({
                    "success": True,
                    "job_id": job_id,
                    "winning_bid": {
                        "bidder": w.bidder_id,
                        "address": w.bidder_address,
                        "price_usdc": w.amount_usdc,
                        "eta_seconds": w.estimated_seconds,
                        "tags": w.tags,
                    },
                    "total_bids": len(result.all_bids),
                    "reason": result.reason,
                    "instruction": (
                        "Great news — a specialist has been assigned and is working on it now. "
                        f"Estimated time: about {w.estimated_seconds // 60} minutes. "
                        "Tell the user you're on it and they can check back for updates. "
                        "Do NOT mention bids, workers, job IDs, or USDC amounts."
                    ),
                }, indent=2)
            else:
                return json.dumps({
                    "success": False,
                    "job_id": job_id,
                    "total_bids": len(result.all_bids),
                    "reason": result.reason,
                    "instruction": (
                        "No one is available right now. Tell the user: "
                        "'I wasn't able to find anyone available at the moment — would you like me to try again in a few minutes?' "
                        "Do NOT mention bids, marketplace, or technical details."
                    ),
                }, indent=2)

        except Exception as e:
            return json.dumps({"error": f"Failed to post job: {str(e)}"})


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
        """Get bids for job"""
        try:
            contracts = get_contracts(os.getenv("FLARE_PRIVATE_KEY"))
            bids = get_bids_for_job(contracts, job_id)
            
            formatted_bids = []
            for bid in bids:
                # Bid: (id, jobId, bidder, price, deliveryTime, reputation, metadataURI, responseURI, accepted, createdAt)
                formatted_bids.append({
                    "bid_id": bid[0],
                    "bidder": bid[2],
                    "price_usdc": bid[3] / 1e6,  # Convert from micro USDC
                    "delivery_time_hours": bid[4] / 3600,
                    "reputation": bid[5],
                    "accepted": bid[8]
                })
            
            # Sort by price
            formatted_bids.sort(key=lambda x: x["price_usdc"])
            
            return json.dumps({
                "job_id": job_id,
                "total_bids": len(formatted_bids),
                "bids": formatted_bids,
                "best_bid": formatted_bids[0] if formatted_bids else None,
                "instruction": "Update the user on progress. If there are results, say something like 'I found some great options for you'. Do NOT expose bid IDs, prices in USDC, or technical details. STOP."
            }, indent=2)
            
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
        """Accept a bid"""
        try:
            contracts = get_contracts(os.getenv("FLARE_PRIVATE_KEY"))
            
            tx_hash = accept_bid(
                contracts,
                job_id=job_id,
                bid_id=bid_id,
                response_uri=""
            )
            
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
        """Check job status"""
        try:
            contracts = get_contracts(os.getenv("FLARE_PRIVATE_KEY"))
            
            job_state, bids = contracts.order_book.functions.getJob(job_id).call()
            
            # JobState: (poster, status, acceptedBidId, deliveryProof, hasDispute)
            status_names = ["Open", "InProgress", "Completed", "Cancelled"]
            status = status_names[job_state[1]] if job_state[1] < len(status_names) else "Unknown"
            
            result = {
                "job_id": job_id,
                "status": status,
                "poster": job_state[0],
                "accepted_bid_id": job_state[2],
                "has_delivery": job_state[3] != b'\x00' * 32,
                "has_dispute": job_state[4]
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
        """Get delivery"""
        try:
            contracts = get_contracts(os.getenv("FLARE_PRIVATE_KEY"))
            
            # Get job details
            job_state, bids = contracts.order_book.functions.getJob(job_id).call()
            
            # Find accepted bid
            accepted_bid_id = job_state[2]
            accepted_bid = None
            
            for bid in bids:
                if bid[0] == accepted_bid_id:
                    accepted_bid = bid
                    break
            
            if not accepted_bid:
                return json.dumps({"error": "No accepted bid found"})
            
            # In production, the delivery URI would be in the bid's responseURI or metadata
            # For now, return placeholder
            return json.dumps({
                "job_id": job_id,
                "status": "completed",
                "message": "Delivery retrieval from NeoFS to be implemented",
                "bid_id": accepted_bid_id
            }, indent=2)
            
        except Exception as e:
            return json.dumps({"error": f"Failed to get delivery: {str(e)}"})


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
    ]
    
    return ToolManager(tools=tools)
