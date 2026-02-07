"""
CV Magic Agent Server

FastAPI server that:
1. Exposes A2A endpoints for agent communication
2. Runs the event listener for blockchain events
3. Provides health/status endpoints
"""

import os
import asyncio
import logging
import json
from contextlib import asynccontextmanager
from typing import Optional

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

from .agent import CVMagicAgent, create_cv_magic_agent
from ..shared.contracts import submit_delivery
from ..shared.base_agent import ActiveJob

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global agent instance
agent: Optional[CVMagicAgent] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global agent
    
    logger.info("📋 Starting SOTA CV Magic Agent...")
    
    # Initialize and start agent
    agent = await create_cv_magic_agent()
    await agent.start()
    
    yield
    
    # Cleanup
    if agent:
        agent.stop()
    logger.info("👋 CV Magic Agent stopped")


app = FastAPI(
    title="SOTA CV Magic Agent",
    description="Job scouring agent for SOTA on Flare",
    version="0.1.0",
    lifespan=lifespan
)


# ─── Health & Status Endpoints ───────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "agent": "cv_magic"}


@app.get("/status")
async def get_status():
    """Get agent status"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    return {
        "agent_type": agent.agent_type,
        "agent_name": agent.agent_name,
        "wallet_address": agent.wallet.address if agent.wallet else None,
        "capabilities": [c.value for c in agent.capabilities],
        "supported_job_types": [jt.name for jt in agent.supported_job_types],
        "active_jobs": len(agent.active_jobs),
        "max_concurrent_jobs": agent.max_concurrent_jobs,
        "auto_bid_enabled": agent.auto_bid_enabled,
    }


@app.get("/jobs")
async def get_jobs():
    """Get active jobs"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    jobs = []
    for job_id, job in agent.active_jobs.items():
        jobs.append({
            "job_id": job_id,
            "status": job.status,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "parameters": {k: "..." if k == "document_base64" else v 
                          for k, v in (job.parameters or {}).items()},
        })
    
    return {"jobs": jobs}


# ─── A2A Messaging Endpoint ──────────────────────────────────

@app.post("/a2a")
async def handle_a2a_message(request: Request):
    """Handle Agent-to-Agent messages"""
    if not agent:
        return create_error_response(
            A2AErrorCode.SERVER_ERROR,
            "Agent not initialized"
        )
    
    try:
        body = await request.json()
        message = A2AMessage(**body)
        
        # Verify message signature
        if not verify_message(message):
            return create_error_response(
                A2AErrorCode.INVALID_SIGNATURE,
                "Invalid message signature"
            )
        
        # Check message freshness
        if not is_message_fresh(message):
            return create_error_response(
                A2AErrorCode.MESSAGE_EXPIRED,
                "Message has expired"
            )
        
        # Route by method
        if message.method == A2AMethod.EXECUTE_JOB:
            return await _handle_execute_job(message)
        elif message.method == A2AMethod.GET_STATUS:
            return await _handle_get_status(message)
        elif message.method == A2AMethod.CANCEL_JOB:
            return await _handle_cancel_job(message)
        else:
            return create_error_response(
                A2AErrorCode.METHOD_NOT_FOUND,
                f"Unknown method: {message.method}"
            )
            
    except Exception as e:
        logger.exception("Error handling A2A message: %s", e)
        return create_error_response(
            A2AErrorCode.SERVER_ERROR,
            str(e)
        )


async def _handle_execute_job(message: A2AMessage) -> dict:
    """Handle job execution request"""
    params = message.params or {}
    job_id = params.get("job_id")
    
    if not job_id:
        return create_error_response(
            A2AErrorCode.INVALID_PARAMS,
            "Missing job_id"
        )
    
    # Create active job
    job = ActiveJob(
        job_id=job_id,
        parameters=params.get("parameters", {}),
        requester=message.sender,
    )
    
    # Execute asynchronously
    asyncio.create_task(_execute_and_deliver(job))
    
    return create_success_response({
        "status": "accepted",
        "job_id": job_id,
        "message": "Job scouring started"
    })


async def _execute_and_deliver(job: ActiveJob):
    """Execute job and submit delivery"""
    try:
        # Track active job
        agent.active_jobs[job.job_id] = job
        
        # Execute the job
        result = await agent.execute_job(job)
        
        # Submit delivery if successful
        if result.get("success"):
            # Compute proof hash
            result_json = json.dumps(result, sort_keys=True)
            proof_hash = agent.compute_proof_hash(result_json)
            
            # Submit to blockchain
            try:
                await submit_delivery(
                    agent._contracts,
                    job.job_id,
                    proof_hash,
                    f"ipfs://cv_magic-result-{job.job_id}"
                )
                logger.info("Delivery submitted for job %s", job.job_id)
            except Exception as e:
                logger.warning("Failed to submit delivery: %s", e)
        
    except Exception as e:
        logger.exception("Error executing job %s: %s", job.job_id, e)
    finally:
        # Remove from active jobs
        agent.active_jobs.pop(job.job_id, None)


async def _handle_get_status(message: A2AMessage) -> dict:
    """Handle status request"""
    return create_success_response({
        "agent_type": agent.agent_type,
        "active_jobs": len(agent.active_jobs),
        "capacity": agent.max_concurrent_jobs - len(agent.active_jobs),
    })


async def _handle_cancel_job(message: A2AMessage) -> dict:
    """Handle job cancellation"""
    job_id = (message.params or {}).get("job_id")
    
    if job_id in agent.active_jobs:
        # Mark as cancelled (actual cancellation depends on implementation)
        agent.active_jobs.pop(job_id, None)
        return create_success_response({
            "status": "cancelled",
            "job_id": job_id
        })
    
    return create_error_response(
        A2AErrorCode.JOB_NOT_FOUND,
        f"Job {job_id} not found"
    )


# ─── Direct API Endpoints (for testing) ─────────────────────

class ScourRequest(BaseModel):
    document_base64: str
    document_filename: str = "resume.pdf"
    job_title: str
    location: str
    seniority: Optional[str] = None
    remote: Optional[bool] = None
    employment_type: Optional[str] = None
    include_keywords: Optional[list] = None
    exclude_keywords: Optional[list] = None
    num_openings: int = 100


@app.post("/scour")
async def direct_scour(request: ScourRequest):
    """
    Direct job scouring endpoint for testing.
    In production, use A2A messaging through the marketplace.
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    from .tools import ScourJobsTool
    tool = ScourJobsTool()
    
    result_json = await tool.execute(
        document_base64=request.document_base64,
        document_filename=request.document_filename,
        job_title=request.job_title,
        location=request.location,
        seniority=request.seniority,
        remote=request.remote,
        employment_type=request.employment_type,
        include_keywords=request.include_keywords,
        exclude_keywords=request.exclude_keywords,
        num_openings=request.num_openings
    )
    
    return json.loads(result_json)


class ExtractRequest(BaseModel):
    document_base64: str
    document_filename: str = "resume.pdf"


@app.post("/extract-profile")
async def direct_extract(request: ExtractRequest):
    """
    Direct profile extraction endpoint for testing.
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    from .tools import ExtractProfileTool
    tool = ExtractProfileTool()
    
    result_json = await tool.execute(
        document_base64=request.document_base64,
        document_filename=request.document_filename
    )
    
    return json.loads(result_json)


# ─── Entry Point ─────────────────────────────────────────────

def main():
    """Run the CV Magic agent server"""
    port = int(os.getenv("CV_MAGIC_PORT", "3007"))
    host = os.getenv("CV_MAGIC_HOST", "0.0.0.0")
    
    logger.info("Starting CV Magic Agent on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
