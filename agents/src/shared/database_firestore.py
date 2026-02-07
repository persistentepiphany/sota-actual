"""
Database — Async Firestore interface for SOTA agents.

Drop-in replacement for the PostgreSQL ``Database`` class. Every public
method has the same signature and return shape so callers (butler_comms,
flare_butler_api, etc.) keep working unchanged.

Collections (mirroring Prisma schema):
  users, agents, marketplaceJobs, userProfiles,
  agentDataRequests, agentJobUpdates, callSummaries, counters

Usage::

    from agents.src.shared.database import Database

    db = await Database.connect()
    profile = await db.get_user_profile("default")
    await db.upsert_user_profile("default", {"full_name": "Alice"})
    await db.close()
"""

from __future__ import annotations

import os
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import firebase_admin                          # type: ignore
from firebase_admin import credentials, firestore  # type: ignore
from google.cloud.firestore_v1 import AsyncClient  # type: ignore

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


# ── Auto-increment helper ──────────────────────────────────────

async def _next_id(adb: AsyncClient, counter_name: str) -> int:
    """
    Atomic auto-increment counter stored in the ``counters`` collection.
    Mirrors the TypeScript ``nextId()`` in firestore.ts.
    """
    ref = adb.collection("counters").document(counter_name)
    from google.cloud.firestore_v1 import async_transactional  # type: ignore

    @async_transactional
    async def _increment(tx):
        snap = await ref.get(transaction=tx)
        current = snap.get("value") if snap.exists else 0
        nxt = current + 1
        tx.set(ref, {"value": nxt})
        return nxt

    tx = adb.transaction()
    return await _increment(tx)


class Database:
    """Async Firestore helper (singleton-capable, same API as old PG class)."""

    _instance: Optional["Database"] = None

    def __init__(self, adb: AsyncClient = None):
        self._adb = adb

    async def initialize(self):
        """Initialize Firestore connection (alternative to connect classmethod)."""
        if self._adb is not None:
            return
        cred_path = os.getenv(
            "FIREBASE_CREDENTIALS",
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "sota-firebase-sdk.json"),
        )
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        self._adb = AsyncClient()
        logger.info("🗄️  Connected to Firestore")

    # ── Connection ──────────────────────────────────────────

    @classmethod
    async def connect(cls, cred_path: str | None = None) -> "Database":
        """Create (or return cached) Database instance."""
        if cls._instance is not None:
            return cls._instance

        cred_path = cred_path or os.getenv(
            "FIREBASE_CREDENTIALS",
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "sota-firebase-sdk.json"),
        )

        # Initialise the Firebase app once
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)

        adb = AsyncClient()
        cls._instance = cls(adb)
        logger.info("🗄️  Connected to Firestore")
        return cls._instance

    async def close(self):
        """No-op — AsyncClient doesn't require explicit close."""
        logger.info("🗄️  Firestore client released")
        Database._instance = None

    @classmethod
    def reset(cls):
        cls._instance = None

    # ═════════════════════════════════════════════════════════
    #  UserProfile
    # ═════════════════════════════════════════════════════════

    async def get_user_profile(self, user_id: str = "default") -> dict | None:
        """Return profile dict or None."""
        docs = (
            self._adb.collection("userProfiles")
            .where("userId", "==", user_id)
            .limit(1)
        )
        results = [snap async for snap in docs.stream()]
        if not results:
            return None
        return results[0].to_dict()

    async def upsert_user_profile(self, user_id: str, data: dict) -> dict:
        """Create or update a user profile. Returns the stored doc."""
        col_map = {
            "full_name": "fullName",
            "email": "email",
            "phone": "phone",
            "location": "location",
            "skills": "skills",
            "experience_level": "experienceLevel",
            "github_url": "githubUrl",
            "linkedin_url": "linkedinUrl",
            "portfolio_url": "portfolioUrl",
            "bio": "bio",
        }

        known: dict[str, Any] = {}
        extra: dict[str, Any] = {}
        prefs = data.pop("preferences", None)

        for k, v in data.items():
            if k in col_map:
                known[col_map[k]] = v
            elif k in col_map.values():
                known[k] = v
            else:
                extra[k] = v

        update: dict[str, Any] = {**known, "updatedAt": _now()}
        if prefs is not None:
            update["preferences"] = prefs
        if extra:
            update["extra"] = extra

        # Find existing
        existing = await self.get_user_profile(user_id)
        if existing:
            doc_id = str(existing.get("id", ""))
            if doc_id:
                await self._adb.collection("userProfiles").document(doc_id).update(update)
            else:
                # Find by query and update
                docs = self._adb.collection("userProfiles").where("userId", "==", user_id).limit(1)
                async for snap in docs.stream():
                    await snap.reference.update(update)
                    break
        else:
            doc_id = await _next_id(self._adb, "userProfiles")
            profile = {
                "id": doc_id,
                "userId": user_id,
                **update,
                "createdAt": _now(),
            }
            await self._adb.collection("userProfiles").document(str(doc_id)).set(profile)

        return await self.get_user_profile(user_id) or {}

    # ═════════════════════════════════════════════════════════
    #  MarketplaceJob
    # ═════════════════════════════════════════════════════════

    async def create_job(
        self,
        job_id: str,
        description: str,
        tags: list[str],
        budget_usdc: float = 0,
        poster: str = "",
        metadata: dict | None = None,
    ) -> dict:
        now = _now()
        doc_id = await _next_id(self._adb, "marketplaceJobs")
        job = {
            "id": doc_id,
            "jobId": job_id,
            "description": description,
            "tags": tags,
            "budgetUsdc": budget_usdc,
            "status": "open",
            "poster": poster,
            "winner": None,
            "winnerPrice": None,
            "metadata": metadata or {},
            "createdAt": now,
            "updatedAt": now,
        }
        await self._adb.collection("marketplaceJobs").document(str(doc_id)).set(job)
        return job

    async def update_job_status(
        self, job_id: str, status: str,
        winner: str | None = None, winner_price: float | None = None,
    ) -> dict | None:
        docs = self._adb.collection("marketplaceJobs").where("jobId", "==", job_id).limit(1)
        async for snap in docs.stream():
            update: dict[str, Any] = {"status": status, "updatedAt": _now()}
            if winner is not None:
                update["winner"] = winner
            if winner_price is not None:
                update["winnerPrice"] = winner_price
            await snap.reference.update(update)
            refreshed = await snap.reference.get()
            return refreshed.to_dict()
        return None

    async def get_job(self, job_id: str) -> dict | None:
        docs = self._adb.collection("marketplaceJobs").where("jobId", "==", job_id).limit(1)
        async for snap in docs.stream():
            return snap.to_dict()
        return None

    async def list_jobs(self, status: str | None = None, limit: int = 50) -> list[dict]:
        q = self._adb.collection("marketplaceJobs")
        if status:
            q = q.where("status", "==", status)
        q = q.order_by("createdAt", direction=firestore.Query.DESCENDING).limit(limit)
        return [snap.to_dict() async for snap in q.stream()]

    # ═════════════════════════════════════════════════════════
    #  AgentDataRequest
    # ═════════════════════════════════════════════════════════

    async def create_data_request(
        self,
        request_id: str,
        job_id: str,
        agent: str,
        data_type: str,
        question: str,
        fields: list[str] | None = None,
        context: str = "",
    ) -> dict:
        doc_id = await _next_id(self._adb, "agentDataRequests")
        record = {
            "id": doc_id,
            "requestId": request_id,
            "jobId": job_id,
            "agent": agent,
            "dataType": data_type,
            "question": question,
            "fields": fields or [],
            "context": context,
            "status": "pending",
            "answerData": None,
            "answerMsg": None,
            "createdAt": _now(),
            "answeredAt": None,
        }
        await self._adb.collection("agentDataRequests").document(str(doc_id)).set(record)
        return record

    async def answer_data_request(
        self, request_id: str, answer_data: dict, message: str = "",
    ) -> dict | None:
        docs = self._adb.collection("agentDataRequests").where("requestId", "==", request_id).limit(1)
        async for snap in docs.stream():
            update = {
                "status": "answered",
                "answerData": answer_data,
                "answerMsg": message,
                "answeredAt": _now(),
            }
            await snap.reference.update(update)
            refreshed = await snap.reference.get()
            return refreshed.to_dict()
        return None

    async def get_pending_requests(self, job_id: str | None = None) -> list[dict]:
        q = self._adb.collection("agentDataRequests").where("status", "==", "pending")
        if job_id:
            q = q.where("jobId", "==", job_id)
        q = q.order_by("createdAt")
        return [snap.to_dict() async for snap in q.stream()]

    async def get_data_request(self, request_id: str) -> dict | None:
        docs = self._adb.collection("agentDataRequests").where("requestId", "==", request_id).limit(1)
        async for snap in docs.stream():
            return snap.to_dict()
        return None

    # ═════════════════════════════════════════════════════════
    #  AgentJobUpdate
    # ═════════════════════════════════════════════════════════

    async def create_update(
        self,
        job_id: str,
        agent: str,
        status: str,
        message: str,
        data: dict | None = None,
    ) -> dict:
        doc_id = await _next_id(self._adb, "agentJobUpdates")
        record = {
            "id": doc_id,
            "jobId": job_id,
            "agent": agent,
            "status": status,
            "message": message,
            "data": data or {},
            "createdAt": _now(),
        }
        await self._adb.collection("agentJobUpdates").document(str(doc_id)).set(record)
        return record

    async def get_updates(self, job_id: str) -> list[dict]:
        q = (
            self._adb.collection("agentJobUpdates")
            .where("jobId", "==", job_id)
            .order_by("createdAt")
        )
        return [snap.to_dict() async for snap in q.stream()]

    # ═════════════════════════════════════════════════════════
    #  CallSummary
    # ═════════════════════════════════════════════════════════

    async def create_call_summary(
        self,
        conversation_id: str | None = None,
        call_sid: str | None = None,
        status: str | None = None,
        summary: str | None = None,
        to_number: str | None = None,
        job_id: str | None = None,
        neofs_uri: str | None = None,
        payload: dict | None = None,
    ) -> dict:
        doc_id = await _next_id(self._adb, "callSummaries")
        record = {
            "id": doc_id,
            "conversationId": conversation_id,
            "callSid": call_sid,
            "status": status,
            "summary": summary,
            "toNumber": to_number,
            "jobId": job_id,
            "neofsUri": neofs_uri,
            "payload": payload,
            "createdAt": _now(),
        }
        await self._adb.collection("callSummaries").document(str(doc_id)).set(record)
        return record
