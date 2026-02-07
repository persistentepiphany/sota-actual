"""
Butler Agent Tools

Tools for the Butler to:
- Query RAG (Qdrant + Mem0)
- Fill slots with slot_questioning
- Post jobs to FlareOrderBook
- Monitor job status and deliveries
- Handle data requests from worker agents
"""

import os
import json
import time
from typing import Any, Optional, Dict, List
from pydantic import Field

from ..shared.tool_base import BaseTool, ToolManager

# Import shared tools
from ..shared.contracts import get_contracts, post_job, get_bids_for_job, accept_bid, get_job_status
from ..shared.slot_questioning import SlotFiller
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
        """Search RAG knowledge base"""
        try:
            from qdrant_client import QdrantClient
            from mem0 import MemoryClient
            
            # Qdrant search
            qdrant = QdrantClient(
                url=os.getenv("QDRANT_URL"),
                api_key=os.getenv("QDRANT_API_KEY")
            )
            
            # Mem0 search
            mem0 = MemoryClient(api_key=os.getenv("MEM0_API_KEY"))
            
            results = {
                "query": query,
                "qdrant_results": [],
                "mem0_results": [],
            }
            
            # Try Qdrant
            try:
                # Placeholder: In production, this would be real search results.
                # For now, return empty to simulate "no match" unless query contains "test"
                if "test" in query.lower():
                    results["qdrant_results"] = ["This is a test result from Qdrant."]
                else:
                    results["qdrant_results"] = []
            except Exception as e:
                results["qdrant_error"] = str(e)
            
            # Try Mem0
            try:
                mem_results = mem0.search(query, user_id=user_id, limit=limit)
                if mem_results:
                    results["mem0_results"] = [m.get("memory") for m in mem_results if "memory" in m]
            except Exception as e:
                results["mem0_error"] = str(e)
            
            if results["qdrant_results"] or results["mem0_results"]:
                results["status"] = "match"
                results["instruction"] = "Use the information above to answer the user's question. Do NOT call any more tools. STOP."
            else:
                results["status"] = "no_match"
                results["instruction"] = "No relevant info found in knowledge base. DECIDE: If user wants a job -> `fill_slots`. If unclear -> Ask user to clarify. STOP."
            
            return json.dumps(results, indent=2)
            
        except Exception as e:
            return json.dumps({"error": f"RAG search failed: {str(e)}"})


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
        """Fill slots using SlotFiller"""
        try:
            if candidate_tools is None:
                candidate_tools = [
                    {"name": "call_verification", "required_params": ["phone_number", "purpose"]},
                    {"name": "hotel_booking", "required_params": ["location", "dates", "guests"]},
                    {"name": "data_analysis", "required_params": ["data_source", "analysis_type"]},
                ]
            
            current_slots = current_slots or {}
            
            # Try to use SlotFiller
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
                    result["instruction"] = "CRITICAL: You MUST ask the user the questions in the 'questions' list. Do NOT call this tool again until the user responds. OUTPUT THE QUESTIONS NOW."
                else:
                    result["instruction"] = "Slots are complete. Summarize the job details to the user and ask for confirmation to post."
                
                return json.dumps(result, indent=2)
                
            except Exception as e:
                # Fallback to basic extraction
                return json.dumps({
                    "error": f"SlotFiller unavailable: {e}",
                    "fallback": "basic",
                    "message": "Please provide job details manually"
                })
                
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
                        f"Job assigned to {w.bidder_id} for {w.amount_usdc:.2f} USDC. "
                        "The worker will start executing. Use `check_job_status` later to track progress."
                    ),
                }, indent=2)
            else:
                return json.dumps({
                    "success": False,
                    "job_id": job_id,
                    "total_bids": len(result.all_bids),
                    "reason": result.reason,
                    "instruction": "No suitable bids received. Ask the user if they want to increase the budget or try again later.",
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
                "instruction": "Present these bids to the user. Ask which one they want to accept (or if they want to wait). STOP."
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
