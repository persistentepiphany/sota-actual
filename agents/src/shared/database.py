"""
Database — Async PostgreSQL interface for SOTA agents.

Thin wrapper around ``asyncpg`` that provides helpers for the
agent-marketplace tables:

  MarketplaceJob, UserProfile, AgentDataRequest, AgentJobUpdate

All functions accept / return plain dicts so they stay framework-agnostic.

Usage::

    from agents.src.shared.database import Database

    db = await Database.connect()
    profile = await db.get_user_profile("default")
    await db.upsert_user_profile("default", {"full_name": "Alice", "email": "alice@example.com"})
    await db.close()
"""

from __future__ import annotations

import os
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Database:
    """Async PostgreSQL helper (singleton-capable)."""

    _instance: Optional["Database"] = None

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    # ── Connection ──────────────────────────────────────────

    @classmethod
    async def connect(cls, dsn: str | None = None) -> "Database":
        """Create (or return cached) Database instance."""
        if cls._instance is not None:
            return cls._instance

        dsn = dsn or os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:admin@localhost:5432/sota",
        )
        pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
        cls._instance = cls(pool)
        logger.info("🗄️  Connected to PostgreSQL")
        return cls._instance

    async def close(self):
        if self._pool:
            await self._pool.close()
            logger.info("🗄️  PostgreSQL pool closed")
        Database._instance = None

    @classmethod
    def reset(cls):
        cls._instance = None

    # ═════════════════════════════════════════════════════════
    #  UserProfile
    # ═════════════════════════════════════════════════════════

    async def get_user_profile(self, user_id: str = "default") -> dict | None:
        """Return profile dict or None."""
        row = await self._pool.fetchrow(
            'SELECT * FROM "UserProfile" WHERE "userId" = $1', user_id,
        )
        return dict(row) if row else None

    async def upsert_user_profile(self, user_id: str, data: dict) -> dict:
        """Create or update a user profile. Returns the stored row."""
        # Map flat keys to column names (camelCase as per Prisma)
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

        # Separate known columns from extra
        known = {}
        extra = {}
        prefs = data.pop("preferences", None)

        for k, v in data.items():
            if k in col_map:
                known[col_map[k]] = v
            elif k in col_map.values():
                known[k] = v
            else:
                extra[k] = v

        # Build SET clause
        sets = ['"updatedAt" = NOW()']
        args: list[Any] = [user_id]
        idx = 2

        for col, val in known.items():
            sets.append(f'"{col}" = ${idx}')
            args.append(val)
            idx += 1

        if prefs is not None:
            sets.append(f'"preferences" = ${idx}::jsonb')
            args.append(json.dumps(prefs))
            idx += 1

        if extra:
            sets.append(f'"extra" = ${idx}::jsonb')
            args.append(json.dumps(extra))
            idx += 1

        set_clause = ", ".join(sets)

        # Upsert
        await self._pool.execute(f'''
            INSERT INTO "UserProfile" ("userId", "createdAt", "updatedAt")
            VALUES ($1, NOW(), NOW())
            ON CONFLICT ("userId") DO UPDATE SET {set_clause}
        ''', *args)

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
        row = await self._pool.fetchrow('''
            INSERT INTO "MarketplaceJob"
                ("jobId", "description", "tags", "budgetUsdc", "poster", "metadata",
                 "createdAt", "updatedAt")
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, NOW(), NOW())
            RETURNING *
        ''', job_id, description, tags, budget_usdc, poster,
            json.dumps(metadata or {}))
        return dict(row)

    async def update_job_status(
        self, job_id: str, status: str,
        winner: str | None = None, winner_price: float | None = None,
    ) -> dict | None:
        row = await self._pool.fetchrow('''
            UPDATE "MarketplaceJob"
            SET "status" = $2, "winner" = COALESCE($3, "winner"),
                "winnerPrice" = COALESCE($4, "winnerPrice"), "updatedAt" = NOW()
            WHERE "jobId" = $1
            RETURNING *
        ''', job_id, status, winner, winner_price)
        return dict(row) if row else None

    async def get_job(self, job_id: str) -> dict | None:
        row = await self._pool.fetchrow(
            'SELECT * FROM "MarketplaceJob" WHERE "jobId" = $1', job_id,
        )
        return dict(row) if row else None

    async def list_jobs(self, status: str | None = None, limit: int = 50) -> list[dict]:
        if status:
            rows = await self._pool.fetch(
                'SELECT * FROM "MarketplaceJob" WHERE "status" = $1 ORDER BY "createdAt" DESC LIMIT $2',
                status, limit,
            )
        else:
            rows = await self._pool.fetch(
                'SELECT * FROM "MarketplaceJob" ORDER BY "createdAt" DESC LIMIT $1',
                limit,
            )
        return [dict(r) for r in rows]

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
        row = await self._pool.fetchrow('''
            INSERT INTO "AgentDataRequest"
                ("requestId", "jobId", "agent", "dataType", "question",
                 "fields", "context", "createdAt")
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            RETURNING *
        ''', request_id, job_id, agent, data_type, question,
            fields or [], context)
        return dict(row)

    async def answer_data_request(
        self, request_id: str, answer_data: dict, message: str = "",
    ) -> dict | None:
        row = await self._pool.fetchrow('''
            UPDATE "AgentDataRequest"
            SET "status" = 'answered', "answerData" = $2::jsonb,
                "answerMsg" = $3, "answeredAt" = NOW()
            WHERE "requestId" = $1
            RETURNING *
        ''', request_id, json.dumps(answer_data), message)
        return dict(row) if row else None

    async def get_pending_requests(self, job_id: str | None = None) -> list[dict]:
        if job_id:
            rows = await self._pool.fetch('''
                SELECT * FROM "AgentDataRequest"
                WHERE "jobId" = $1 AND "status" = 'pending'
                ORDER BY "createdAt"
            ''', job_id)
        else:
            rows = await self._pool.fetch('''
                SELECT * FROM "AgentDataRequest"
                WHERE "status" = 'pending'
                ORDER BY "createdAt"
            ''')
        return [dict(r) for r in rows]

    async def get_data_request(self, request_id: str) -> dict | None:
        row = await self._pool.fetchrow(
            'SELECT * FROM "AgentDataRequest" WHERE "requestId" = $1',
            request_id,
        )
        return dict(row) if row else None

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
        row = await self._pool.fetchrow('''
            INSERT INTO "AgentJobUpdate"
                ("jobId", "agent", "status", "message", "data", "createdAt")
            VALUES ($1, $2, $3, $4, $5::jsonb, NOW())
            RETURNING *
        ''', job_id, agent, status, message, json.dumps(data or {}))
        return dict(row)

    async def get_updates(self, job_id: str) -> list[dict]:
        rows = await self._pool.fetch('''
            SELECT * FROM "AgentJobUpdate"
            WHERE "jobId" = $1
            ORDER BY "createdAt"
        ''', job_id)
        return [dict(r) for r in rows]
