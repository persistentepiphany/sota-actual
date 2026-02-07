"""
Butler Communication — Tools for worker agents to request data from Butler.

When a worker agent (e.g. HackathonAgent) wins a marketplace job, it may
need additional information from the user (via the Butler).  This module
provides:

1. ``RequestDataFromButlerTool`` — LLM-callable tool that sends an HTTP
   request to the Butler asking for specific data (user profile, preferences,
   dates, confirmation, etc.).

2. ``SendResultToButlerTool`` — LLM-callable tool that pushes final job
   results or status updates back to the Butler so it can relay them to
   the user in real time.

Communication happens over HTTP between the agent's FastAPI process and
the Butler's FastAPI process (flare_butler_api.py).

Flow:
  User ←→ Butler  ←—HTTP—→  WorkerAgent
              ↕                    ↕
         JobBoard             execute_job()
"""

from __future__ import annotations

import os
import json
import asyncio
import logging
from typing import Any, Optional

import httpx
from pydantic import Field

from .tool_base import BaseTool

logger = logging.getLogger(__name__)


# ─── In-memory store for pending requests (Butler side) ──────

class ButlerDataExchange:
    """
    Singleton data exchange that lives inside the Butler process.

    Worker agents POST data requests here.  The Butler polls / awaits
    them and relays questions to the user.  When the user responds the
    Butler writes the answer back, and the worker agent's long-poll
    resolves.
    """

    _instance: Optional["ButlerDataExchange"] = None

    def __init__(self):
        # job_id → list of pending requests
        self._pending: dict[str, list[dict]] = {}
        # request_id → asyncio.Event (signalled when answer arrives)
        self._events: dict[str, asyncio.Event] = {}
        # request_id → answer payload
        self._answers: dict[str, Any] = {}
        # job_id → list of status updates pushed by worker
        self._updates: dict[str, list[dict]] = {}
        # Database instance (lazily connected)
        self._db = None

    @classmethod
    def instance(cls) -> "ButlerDataExchange":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        cls._instance = None

    async def _get_db(self):
        """Lazily connect to the database."""
        if self._db is None:
            try:
                from .database import Database
                self._db = await Database.connect()
            except Exception as e:
                logger.debug("DB not available: %s", e)
        return self._db

    # ── Worker side: post a request ─────────────────────────

    def post_request(self, request_id: str, job_id: str, request: dict):
        """Store a data request from a worker agent."""
        self._pending.setdefault(job_id, []).append({
            "request_id": request_id,
            **request,
        })
        self._events[request_id] = asyncio.Event()
        logger.info("📩 Data request queued: req=%s job=%s type=%s",
                     request_id, job_id, request.get("data_type"))

        # Persist to DB (fire-and-forget)
        asyncio.ensure_future(self._persist_request(request_id, job_id, request))

    async def _persist_request(self, request_id: str, job_id: str, request: dict):
        try:
            db = await self._get_db()
            if db:
                await db.create_data_request(
                    request_id=request_id,
                    job_id=job_id,
                    agent=request.get("agent", "unknown"),
                    data_type=request.get("data_type", "custom"),
                    question=request.get("question", ""),
                    fields=request.get("fields"),
                    context=request.get("context", ""),
                )
        except Exception as e:
            logger.debug("DB persist request failed: %s", e)

    async def wait_for_answer(self, request_id: str, timeout: float = 300) -> Optional[dict]:
        """Block until the Butler supplies an answer (or timeout)."""
        event = self._events.get(request_id)
        if not event:
            return None
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return self._answers.pop(request_id, None)
        except asyncio.TimeoutError:
            logger.warning("⏰ Request %s timed out after %.0fs", request_id, timeout)
            return {"error": "timeout", "message": "User did not respond in time"}
        finally:
            self._events.pop(request_id, None)

    # ── Butler side: read & answer ──────────────────────────

    def get_pending_requests(self, job_id: str | None = None) -> list[dict]:
        """Return (and clear) pending requests for a job, or all."""
        if job_id:
            return self._pending.pop(job_id, [])
        all_reqs = []
        for jid in list(self._pending):
            all_reqs.extend(self._pending.pop(jid, []))
        return all_reqs

    def peek_pending_requests(self, job_id: str | None = None) -> list[dict]:
        """Return pending requests WITHOUT clearing them."""
        if job_id:
            return list(self._pending.get(job_id, []))
        all_reqs = []
        for reqs in self._pending.values():
            all_reqs.extend(reqs)
        return all_reqs

    def submit_answer(self, request_id: str, answer: dict):
        """Butler provides the answer; this unblocks the worker's wait."""
        self._answers[request_id] = answer
        event = self._events.get(request_id)
        if event:
            event.set()
            logger.info("✅ Answer submitted for request %s", request_id)
        else:
            logger.warning("⚠️ No waiter for request %s", request_id)

        # Persist to DB
        asyncio.ensure_future(self._persist_answer(request_id, answer))

    async def _persist_answer(self, request_id: str, answer: dict):
        try:
            db = await self._get_db()
            if db:
                await db.answer_data_request(
                    request_id=request_id,
                    answer_data=answer.get("data", answer),
                    message=answer.get("message", ""),
                )
        except Exception as e:
            logger.debug("DB persist answer failed: %s", e)

    # ── Worker → Butler status updates ──────────────────────

    def push_update(self, job_id: str, update: dict):
        """Worker pushes a status/progress update for the Butler."""
        self._updates.setdefault(job_id, []).append(update)
        # Persist to DB
        asyncio.ensure_future(self._persist_update(job_id, update))

    async def _persist_update(self, job_id: str, update: dict):
        try:
            db = await self._get_db()
            if db:
                await db.create_update(
                    job_id=job_id,
                    agent=update.get("agent", "unknown"),
                    status=update.get("status", "in_progress"),
                    message=update.get("message", ""),
                    data=update.get("data"),
                )
        except Exception as e:
            logger.debug("DB persist update failed: %s", e)

    def get_updates(self, job_id: str) -> list[dict]:
        """Butler drains updates for a job."""
        return self._updates.pop(job_id, [])


# ═════════════════════════════════════════════════════════════
#  LLM-callable tools (worker agent side)
# ═════════════════════════════════════════════════════════════

class RequestDataFromButlerTool(BaseTool):
    """
    Request additional data from the Butler (and the user).

    The hackathon agent calls this when it needs information that
    wasn't included in the original job description — e.g. user
    profile, preferred dates, location constraints, confirmation
    to proceed, etc.

    The request is sent to the Butler's HTTP endpoint.  The Butler
    relays the question to the user and returns the answer.
    """

    name: str = "request_butler_data"
    description: str = """
    Request additional data from the Butler / user during job execution.

    Use this when you need information not provided in the job description:
    - "user_profile": get the user's name, email, skills, etc.
    - "preference": ask for a specific preference (dates, location, etc.)
    - "confirmation": ask the user to confirm before proceeding
    - "clarification": ask the user to clarify something
    - "custom": free-form question to the user

    The Butler will relay your question to the user and return their answer.

    Parameters:
      data_type: one of "user_profile", "preference", "confirmation",
                 "clarification", "custom"
      question:  the question or data description to send to the user
      fields:    (optional) list of specific fields you need
                 e.g. ["full_name", "email", "location"]
      job_id:    the current job ID
      context:   (optional) extra context to help the Butler
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "data_type": {
                "type": "string",
                "enum": ["user_profile", "preference", "confirmation",
                         "clarification", "custom"],
                "description": "Type of data being requested"
            },
            "question": {
                "type": "string",
                "description": "Question or description of what data you need"
            },
            "fields": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific fields needed (optional)"
            },
            "job_id": {
                "type": "string",
                "description": "The current job ID"
            },
            "context": {
                "type": "string",
                "description": "Additional context for the Butler"
            },
        },
        "required": ["data_type", "question", "job_id"]
    }

    async def execute(
        self,
        data_type: str,
        question: str,
        job_id: str,
        fields: list[str] | None = None,
        context: str | None = None,
    ) -> str:
        """Send request to Butler and wait for response."""
        import uuid

        butler_url = os.getenv("BUTLER_ENDPOINT", "http://localhost:3001")
        request_id = str(uuid.uuid4())[:8]

        payload = {
            "request_id": request_id,
            "job_id": job_id,
            "data_type": data_type,
            "question": question,
            "fields": fields or [],
            "context": context or "",
            "agent": "hackathon",
        }

        # ── Try HTTP call to Butler ──────────────────────────
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{butler_url}/api/agent/request-data",
                    json=payload,
                )
                if resp.status_code == 200:
                    result = resp.json()
                    logger.info("📬 Butler responded to request %s: %s",
                                request_id, json.dumps(result)[:200])
                    return json.dumps(result, indent=2)
                else:
                    logger.warning("Butler returned %d: %s",
                                   resp.status_code, resp.text[:200])
        except httpx.ConnectError:
            logger.warning("Cannot reach Butler at %s — trying in-process exchange",
                           butler_url)
        except Exception as e:
            logger.warning("HTTP request to Butler failed: %s", e)

        # ── Fallback: in-process ButlerDataExchange ──────────
        # (works when Butler and worker run in the same Python process)
        try:
            exchange = ButlerDataExchange.instance()
            exchange.post_request(request_id, job_id, payload)
            answer = await exchange.wait_for_answer(request_id, timeout=120)
            if answer:
                return json.dumps(answer, indent=2)
            return json.dumps({
                "error": "no_response",
                "message": "Butler did not respond. Try proceeding with available data.",
            })
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "message": "Could not communicate with Butler.",
            })


class SendUpdateToButlerTool(BaseTool):
    """
    Send a status update or intermediate result back to the Butler.

    Use this to keep the user informed during long-running jobs.
    """

    name: str = "notify_butler"
    description: str = """
    Send a progress update or partial result to the Butler so the user
    is kept informed.

    Use this when:
    - You've completed a significant step (e.g. "Found 5 hackathons")
    - You need to share intermediate results
    - The job is taking a while and you want to report progress

    Parameters:
      job_id:   the current job ID
      status:   "in_progress", "partial_result", "completed", "error"
      message:  human-readable status message
      data:     (optional) structured data to include
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": "The current job ID"
            },
            "status": {
                "type": "string",
                "enum": ["in_progress", "partial_result", "completed", "error"],
                "description": "Current status"
            },
            "message": {
                "type": "string",
                "description": "Human-readable status message for the user"
            },
            "data": {
                "type": "object",
                "description": "Structured data (optional)"
            },
        },
        "required": ["job_id", "status", "message"]
    }

    async def execute(
        self,
        job_id: str,
        status: str,
        message: str,
        data: dict | None = None,
    ) -> str:
        """Push update to Butler."""
        butler_url = os.getenv("BUTLER_ENDPOINT", "http://localhost:3001")

        update = {
            "job_id": job_id,
            "status": status,
            "message": message,
            "data": data or {},
            "agent": "hackathon",
        }

        # Try HTTP
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{butler_url}/api/agent/update",
                    json=update,
                )
                if resp.status_code == 200:
                    return json.dumps({"success": True, "delivered": True})
        except Exception:
            pass

        # Fallback: in-process
        try:
            exchange = ButlerDataExchange.instance()
            exchange.push_update(job_id, update)
            return json.dumps({"success": True, "delivered": True, "via": "in-process"})
        except Exception as e:
            return json.dumps({"error": str(e)})


# ─── Factory ─────────────────────────────────────────────────

def create_butler_comm_tools() -> list[BaseTool]:
    """Create all Butler communication tools."""
    return [
        RequestDataFromButlerTool(),
        SendUpdateToButlerTool(),
    ]
