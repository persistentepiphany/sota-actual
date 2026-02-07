"""
Database — Async interface for SOTA agents.

Now backed by Firebase Firestore (was PostgreSQL / asyncpg).

The public API is unchanged — every caller (butler_comms, flare_butler_api,
hackathon agent, caller agent) keeps working without modification.

Usage::

    from agents.src.shared.database import Database

    db = await Database.connect()
    profile = await db.get_user_profile("default")
    await db.upsert_user_profile("default", {"full_name": "Alice", "email": "alice@example.com"})
    await db.close()
"""

# Re-export the Firestore-backed implementation under the same name
from agents.src.shared.database_firestore import Database  # noqa: F401

__all__ = ["Database"]
