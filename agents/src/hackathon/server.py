"""
Hackathon Agent Server

FastAPI server that:
1. Exposes A2A endpoints for agent communication
2. Provides health/status endpoints
3. Offers a direct /search endpoint for hackathon queries
   accepting time period, location, topics, and mode
"""

import os
import json
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import uvicorn

from ..shared.a2a import (
    A2AMessage,
    A2AResponse,
    A2AMethod,
    A2AErrorCode,
    verify_message,
    is_message_fresh,
    create_error_response,
    create_success_response,
)
from ..shared.butler_comms import ButlerDataExchange

from .agent import HackathonAgent, create_hackathon_agent
from ..shared.base_agent import ActiveJob

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global agent instance
agent: HackathonAgent = None


# ─── Request / Response Models ────────────────────────────────

class HackathonSearchRequest(BaseModel):
    """Direct search request (non-A2A).

    All four user-facing search parameters:
      - location:  city / region / country / "anywhere"
      - date_from: YYYY-MM-DD (default today)
      - date_to:   YYYY-MM-DD (default +3 months)
      - topics:    comma-separated themes (e.g. "AI, blockchain")
      - mode:      "online" | "in-person" | "both"
      - user_profile: optional user context dict
    """
    location: str = "anywhere"
    date_from: str | None = None
    date_to: str | None = None
    topics: str | None = None
    mode: str = "both"               # online | in-person | both
    keywords: str | None = None      # kept for backward compat
    user_profile: dict | None = None


class HackathonRegisterRequest(BaseModel):
    """Direct registration request."""
    hackathon_url: str
    user_profile: dict | None = None
    dry_run: bool = True


# ─── Lifespan ─────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global agent

    logger.info("Starting SOTA Hackathon Agent...")

    agent = await create_hackathon_agent()

    yield

    # Cleanup
    if agent:
        agent.stop()
    logger.info("Hackathon Agent stopped")


app = FastAPI(
    title="SOTA Hackathon Agent",
    description="Hackathon search & registration agent for SOTA on Flare",
    version="0.2.0",
    lifespan=lifespan,
)


# ─── Health & Status ──────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "agent": "hackathon"}


@app.get("/status")
async def get_status():
    """Get agent status."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return agent.get_status()


@app.get("/jobs")
async def get_active_jobs():
    """Get active jobs."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return {
        "active_jobs": [
            {
                "job_id": job.job_id,
                "status": job.status,
                "job_type": job.job_type,
            }
            for job in agent.active_jobs.values()
        ]
    }


# ─── Direct Search Endpoint ──────────────────────────────────

@app.post("/search")
async def search_hackathons(req: HackathonSearchRequest):
    """
    Direct hackathon search (bypasses JobBoard).
    Accepts time period, location, topics, mode.
    """
    if not agent or not agent.llm_agent:
        raise HTTPException(status_code=503, detail="Agent not ready")

    # Store user context if provided
    if req.user_profile:
        try:
            import httpx
            butler_url = os.getenv("BUTLER_ENDPOINT", "http://localhost:3001")
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{butler_url}/api/agent/set-user-context",
                    json={"user_id": "default", "profile": req.user_profile},
                )
        except Exception:
            pass  # Non-critical

    # Merge legacy `keywords` into `topics` if topics not set
    topics = req.topics or req.keywords

    # Build a natural-language prompt that carries all four parameters
    parts = [f"Search for upcoming hackathons"]
    if req.location and req.location.lower() not in ("anywhere", ""):
        parts.append(f"near {req.location}")
    if req.date_from:
        parts.append(f"from {req.date_from}")
    if req.date_to:
        parts.append(f"to {req.date_to}")
    if topics:
        parts.append(f"related to {topics}")
    if req.mode and req.mode != "both":
        parts.append(f"({req.mode} only)")
    parts.append(". Return a formatted summary of upcoming events only.")

    prompt = " ".join(parts)

    try:
        result = await agent.llm_agent.run(prompt)
        return {"success": True, "result": result}
    except Exception as e:
        logger.error("Search failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Direct Register Endpoint ────────────────────────────────

@app.post("/register")
async def register_for_hackathon(req: HackathonRegisterRequest):
    """
    Directly register a user for a hackathon.
    Bypasses the JobBoard for quick one-off registrations.
    """
    if not agent or not agent.llm_agent:
        raise HTTPException(status_code=503, detail="Agent not ready")

    profile_str = json.dumps(req.user_profile) if req.user_profile else "{}"
    dry_label = "DRY RUN -- " if req.dry_run else ""

    prompt = (
        f"{dry_label}Register me for the hackathon at {req.hackathon_url}.\n"
        f"My profile: {profile_str}\n"
        f"dry_run={'true' if req.dry_run else 'false'}"
    )

    try:
        result = await agent.llm_agent.run(prompt)
        return {"success": True, "dry_run": req.dry_run, "result": result}
    except Exception as e:
        logger.error("Registration failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ─── A2A RPC Endpoint ────────────────────────────────────────

@app.post("/v1/rpc")
async def rpc(request: Request):
    """Agent-to-Agent JSON-RPC endpoint."""
    try:
        body = await request.json()
        msg = A2AMessage(**body)
    except Exception:
        return create_error_response(
            "unknown", A2AErrorCode.INVALID_REQUEST, "Invalid A2A message"
        )

    logger.info("A2A request: method=%s id=%s", msg.method, msg.id)

    if msg.method == A2AMethod.EXECUTE:
        params = msg.params or {}
        description = params.get("description", "Find hackathons")
        job_id = params.get("job_id", 0)

        job = ActiveJob(
            job_id=job_id,
            bid_id=0,
            job_type=2,  # HACKATHON_REGISTRATION
            description=description,
            budget=params.get("budget", 1_000_000),
            deadline=params.get("deadline", 0),
        )

        result = await agent.execute_job(job)
        return create_success_response(msg.id, result)

    elif msg.method == A2AMethod.STATUS:
        return create_success_response(msg.id, agent.get_status())

    elif msg.method == A2AMethod.HEALTH:
        return create_success_response(msg.id, {"status": "healthy"})

    else:
        return create_error_response(
            msg.id, A2AErrorCode.METHOD_NOT_FOUND, f"Unknown method: {msg.method}"
        )


# ─── Entrypoint ──────────────────────────────────────────────

def run_server():
    """Start the Hackathon Agent server."""
    port = int(os.getenv("HACKATHON_AGENT_PORT", "3005"))
    logger.info("Hackathon Agent listening on port %d", port)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    run_server()
