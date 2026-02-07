"""
SOTA Butler — LangGraph Agent Orchestration

A state-machine-based agent that orchestrates the full job lifecycle:
  Intent → Plan → Quote (FTSO) → Confirm → Execute → Monitor (FDC)

This is the AI Middleware track entry: a multi-node agent swarm
with typed tools, guardrails, and constrained environment.
"""

from __future__ import annotations

import os
import time
import hashlib
from enum import Enum
from typing import Optional, List, Literal, Annotated
from dataclasses import dataclass, field

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from agents.src.shared.flare_config import get_private_key, JobType, JOB_TYPE_LABELS
from agents.src.shared.flare_contracts import (
    get_flare_contracts,
    FlareContracts,
    quote_usd_to_flr,
    get_flr_usd_price,
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


# ══════════════════════════════════════════════════════════════
#  State Schema
# ══════════════════════════════════════════════════════════════

class Phase(str, Enum):
    INTENT = "intent"
    PLAN = "plan"
    QUOTE = "quote"
    CONFIRM = "confirm"
    EXECUTE = "execute"
    MONITOR = "monitor"
    DONE = "done"
    ERROR = "error"


class ButlerState(BaseModel):
    """Typed state that flows through the LangGraph graph."""

    # ── User input ──
    user_message: str = ""
    user_id: str = "default"

    # ── Phase tracking ──
    phase: Phase = Phase.INTENT
    error: Optional[str] = None

    # ── Intent ──
    intent: Optional[str] = None           # e.g. "hotel_booking", "hackathon_reg"
    job_type: Optional[int] = None

    # ── Plan ──
    description: str = ""
    budget_usd: float = 0.0
    deadline_seconds: int = 86400          # 24h default
    metadata_uri: str = ""
    missing_params: List[str] = Field(default_factory=list)
    questions: List[str] = Field(default_factory=list)

    # ── Quote (FTSO) ──
    flr_price_usd: float = 0.0
    quote_flr: float = 0.0

    # ── Execution ──
    job_id: Optional[int] = None
    provider_address: str = ""
    tx_hash: str = ""

    # ── Monitor (FDC) ──
    fdc_confirmed: bool = False
    released: bool = False

    # ── Response to user ──
    response: str = ""

    class Config:
        arbitrary_types_allowed = True


# ══════════════════════════════════════════════════════════════
#  Guardrails
# ══════════════════════════════════════════════════════════════

# Budget bounds (safety constraint)
MIN_BUDGET_USD = 1.0
MAX_BUDGET_USD = 10_000.0

# Allowed contract functions the agent can call (whitelist)
ALLOWED_ACTIONS = {
    "createJob", "assignProvider", "fundJob",
    "markCompleted", "releaseToProvider",
    "manualConfirmDelivery", "quoteUsdToFlr",
}


def validate_budget(budget: float) -> None:
    """Guardrail: reject budgets outside safe bounds."""
    if budget < MIN_BUDGET_USD:
        raise ValueError(f"Budget ${budget} is below minimum ${MIN_BUDGET_USD}")
    if budget > MAX_BUDGET_USD:
        raise ValueError(f"Budget ${budget} exceeds maximum ${MAX_BUDGET_USD}")


# ══════════════════════════════════════════════════════════════
#  Graph Nodes
# ══════════════════════════════════════════════════════════════

def intent_node(state: ButlerState) -> dict:
    """
    IntentNode — Classify user request into a job type.
    In production, this would use an LLM. Here we use keyword matching.
    """
    msg = state.user_message.lower()

    intent_map = {
        "hotel": ("hotel_booking", JobType.HOTEL_BOOKING),
        "restaurant": ("restaurant_booking", JobType.RESTAURANT_BOOKING),
        "hackathon": ("hackathon_registration", JobType.HACKATHON_REGISTRATION),
        "call": ("call_verification", JobType.CALL_VERIFICATION),
    }

    for keyword, (intent, job_type) in intent_map.items():
        if keyword in msg:
            return {
                "intent": intent,
                "job_type": job_type,
                "phase": Phase.PLAN,
                "response": f"I understand you want: {JOB_TYPE_LABELS.get(job_type, intent)}. Let me plan this out.",
            }

    return {
        "intent": "generic",
        "job_type": JobType.GENERIC,
        "phase": Phase.PLAN,
        "response": "I'll help you with that. Let me plan the task.",
    }


def plan_node(state: ButlerState) -> dict:
    """
    PlanNode — Extract parameters and validate completeness.
    Determines budget, deadline, and metadata.
    """
    missing = []
    questions = []

    # Extract budget from message (simple pattern)
    budget = state.budget_usd
    if budget <= 0:
        import re
        nums = re.findall(r'\$(\d+(?:\.\d+)?)', state.user_message)
        if nums:
            budget = float(nums[0])
        else:
            budget = 50.0  # Default budget

    # Validate budget (guardrail)
    try:
        validate_budget(budget)
    except ValueError as e:
        return {
            "phase": Phase.ERROR,
            "error": str(e),
            "response": str(e),
        }

    description = state.description or state.user_message
    metadata_uri = f"ipfs://sota-job-{int(time.time())}"

    if not description or len(description) < 5:
        missing.append("description")
        questions.append("Could you describe what you need in more detail?")

    if missing:
        return {
            "missing_params": missing,
            "questions": questions,
            "phase": Phase.PLAN,
            "response": questions[0],
        }

    return {
        "description": description,
        "budget_usd": budget,
        "metadata_uri": metadata_uri,
        "missing_params": [],
        "questions": [],
        "phase": Phase.QUOTE,
        "response": f"Planning complete. Budget: ${budget:.2f}. Fetching FTSO quote...",
    }


def quote_node(state: ButlerState) -> dict:
    """
    QuoteNode — Call on-chain FTSO price feed to convert USD → FLR.
    This is the Flare MAIN track proof: meaningful FTSO usage.
    """
    try:
        pk = get_private_key("butler")
        contracts = get_flare_contracts(pk)

        flr_price = get_flr_usd_price(contracts)
        quote_flr = quote_usd_to_flr(contracts, state.budget_usd)

        return {
            "flr_price_usd": flr_price,
            "quote_flr": quote_flr,
            "phase": Phase.CONFIRM,
            "response": (
                f"FTSO Quote: ${state.budget_usd:.2f} USD ≈ {quote_flr:.2f} FLR "
                f"(FLR/USD: ${flr_price:.4f}). "
                f"Shall I proceed with creating this job?"
            ),
        }
    except Exception as e:
        return {
            "phase": Phase.ERROR,
            "error": f"FTSO quote failed: {e}",
            "response": f"I couldn't get a price quote: {e}",
        }


def confirm_node(state: ButlerState) -> dict:
    """
    ConfirmNode — Wait for user confirmation before executing.
    In production, this would use LangGraph's interrupt() mechanism.
    """
    msg = state.user_message.lower()
    if any(word in msg for word in ["yes", "confirm", "proceed", "go", "ok"]):
        return {
            "phase": Phase.EXECUTE,
            "response": "Confirmed! Creating your job on Flare...",
        }

    return {
        "phase": Phase.CONFIRM,
        "response": (
            f"Your quote: ${state.budget_usd:.2f} ≈ {state.quote_flr:.2f} FLR. "
            "Say 'confirm' to proceed or 'cancel' to abort."
        ),
    }


def execute_node(state: ButlerState) -> dict:
    """
    ExecuteNode — Call createJob + assignProvider + fundJob on-chain.
    Uses FTSO-validated pricing throughout.
    """
    try:
        pk = get_private_key("butler")
        contracts = get_flare_contracts(pk)

        # 1. Create job (FTSO derives FLR price)
        job_id = create_job(
            contracts,
            metadata_uri=state.metadata_uri,
            max_price_usd=state.budget_usd,
            deadline_seconds=state.deadline_seconds,
        )

        # 2. For demo: assign a provider (in production, agents bid)
        provider = state.provider_address or os.getenv(
            "DEFAULT_PROVIDER_ADDRESS",
            contracts.account.address if contracts.account else "",
        )

        if provider:
            assign_provider(contracts, job_id, provider)

            # 3. Fund escrow with FLR
            tx = fund_job(
                contracts,
                job_id=job_id,
                provider_address=provider,
                usd_budget=state.budget_usd,
            )

            return {
                "job_id": job_id,
                "provider_address": provider,
                "tx_hash": tx,
                "phase": Phase.MONITOR,
                "response": (
                    f"✅ Job #{job_id} created and funded on Flare!\n"
                    f"   Provider: {provider[:10]}...\n"
                    f"   Escrow: {state.quote_flr:.2f} FLR locked.\n"
                    f"   Tx: {tx}\n"
                    f"Monitoring for completion and FDC attestation..."
                ),
            }

        return {
            "job_id": job_id,
            "phase": Phase.MONITOR,
            "response": f"✅ Job #{job_id} created! Waiting for agent bids...",
        }

    except Exception as e:
        return {
            "phase": Phase.ERROR,
            "error": f"Execution failed: {e}",
            "response": f"❌ Failed to create job: {e}",
        }


def monitor_node(state: ButlerState) -> dict:
    """
    MonitorNode — Poll job state and FDC-driven delivery condition.
    When FDC confirms delivery, trigger escrow release.

    This is the Flare BONUS proof: escrow release is driven entirely
    by FDC-attested external data, not a trusted backend.
    """
    if not state.job_id:
        return {
            "phase": Phase.ERROR,
            "error": "No job ID to monitor",
            "response": "❌ No job to monitor.",
        }

    try:
        pk = get_private_key("butler")
        contracts = get_flare_contracts(pk)

        job = get_job(contracts, state.job_id)
        status_names = ["OPEN", "ASSIGNED", "COMPLETED", "RELEASED", "CANCELLED"]
        status_name = status_names[job["status"]] if job["status"] < len(status_names) else "UNKNOWN"

        # Check FDC delivery attestation
        fdc_confirmed = is_delivery_confirmed(contracts, state.job_id)

        if job["status"] == 3:  # RELEASED
            return {
                "fdc_confirmed": True,
                "released": True,
                "phase": Phase.DONE,
                "response": (
                    f"🎉 Job #{state.job_id} is complete and payment released!\n"
                    f"   FDC attestation: ✅ verified\n"
                    f"   Status: RELEASED"
                ),
            }

        if fdc_confirmed and job["status"] == 2:  # COMPLETED + FDC confirmed
            # Auto-release payment
            tx = release_payment(contracts, state.job_id)
            return {
                "fdc_confirmed": True,
                "released": True,
                "tx_hash": tx,
                "phase": Phase.DONE,
                "response": (
                    f"🎉 FDC confirmed delivery for job #{state.job_id}!\n"
                    f"   Payment auto-released to provider.\n"
                    f"   Tx: {tx}"
                ),
            }

        return {
            "fdc_confirmed": fdc_confirmed,
            "phase": Phase.MONITOR,
            "response": (
                f"📊 Job #{state.job_id} status: {status_name}\n"
                f"   FDC delivery attested: {'✅' if fdc_confirmed else '⏳ pending'}\n"
                f"   Checking again soon..."
            ),
        }

    except Exception as e:
        return {
            "phase": Phase.ERROR,
            "error": f"Monitor failed: {e}",
            "response": f"❌ Monitoring error: {e}",
        }


# ══════════════════════════════════════════════════════════════
#  Graph Router
# ══════════════════════════════════════════════════════════════

def route_next(state: ButlerState) -> str:
    """Route to the next node based on current phase."""
    if state.phase == Phase.INTENT:
        return "intent"
    elif state.phase == Phase.PLAN:
        return "plan"
    elif state.phase == Phase.QUOTE:
        return "quote"
    elif state.phase == Phase.CONFIRM:
        return "confirm"
    elif state.phase == Phase.EXECUTE:
        return "execute"
    elif state.phase == Phase.MONITOR:
        return "monitor"
    elif state.phase in (Phase.DONE, Phase.ERROR):
        return END
    return END


# ══════════════════════════════════════════════════════════════
#  Build Graph
# ══════════════════════════════════════════════════════════════

def build_butler_graph() -> StateGraph:
    """
    Build the LangGraph state machine for the SOTA Butler agent.

    Graph topology:
        START → intent → plan → quote → confirm → execute → monitor → END
                  ↑         ↓                                    ↓
                  └── (if missing params) ─── back to plan       └── END
    """
    graph = StateGraph(ButlerState)

    # Add nodes
    graph.add_node("intent", intent_node)
    graph.add_node("plan", plan_node)
    graph.add_node("quote", quote_node)
    graph.add_node("confirm", confirm_node)
    graph.add_node("execute", execute_node)
    graph.add_node("monitor", monitor_node)

    # Entry point
    graph.set_entry_point("intent")

    # Conditional edges based on phase
    graph.add_conditional_edges("intent", route_next)
    graph.add_conditional_edges("plan", route_next)
    graph.add_conditional_edges("quote", route_next)
    graph.add_conditional_edges("confirm", route_next)
    graph.add_conditional_edges("execute", route_next)
    graph.add_conditional_edges("monitor", route_next)

    return graph


def compile_butler():
    """Compile the butler graph into a runnable."""
    graph = build_butler_graph()
    return graph.compile()


# ══════════════════════════════════════════════════════════════
#  Convenience Runner
# ══════════════════════════════════════════════════════════════

def run_butler(message: str, user_id: str = "default") -> ButlerState:
    """
    Run a single message through the full butler pipeline.

    Returns the final state with response.
    """
    app = compile_butler()
    initial_state = ButlerState(
        user_message=message,
        user_id=user_id,
        phase=Phase.INTENT,
    )
    result = app.invoke(initial_state.model_dump())
    return ButlerState(**result)


if __name__ == "__main__":
    import sys

    message = " ".join(sys.argv[1:]) or "Book me a hotel near the Oxford AI Hackathon for $50"
    print(f"\n💬 User: {message}\n")

    state = run_butler(message)
    print(f"🤖 Butler: {state.response}")
    print(f"   Phase: {state.phase}")
    if state.job_id:
        print(f"   Job ID: {state.job_id}")
    if state.quote_flr:
        print(f"   Quote: {state.quote_flr:.2f} FLR")
    if state.error:
        print(f"   Error: {state.error}")
