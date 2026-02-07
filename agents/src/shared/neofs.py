"""
NeoFS Stub — Placeholder for removed NeoFS storage.

NeoFS is no longer used in the Flare-based SOTA system.
All functions return stubs or raise NotImplementedError
so that existing callers don't crash on import.

Metadata is now stored via IPFS URIs or on-chain directly.
"""

import json
import hashlib
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

_WARNING_EMITTED = False


def _warn_once() -> None:
    global _WARNING_EMITTED
    if not _WARNING_EMITTED:
        logger.warning(
            "NeoFS is deprecated in SOTA. Calls are stubbed. "
            "Metadata should use IPFS URIs or on-chain storage."
        )
        _WARNING_EMITTED = True


class NeoFSClient:
    """Stub NeoFS client — all operations are no-ops."""

    def __init__(self, *args: Any, **kwargs: Any):
        _warn_once()

    async def download_object(self, object_id: str, container_id: str) -> bytes:
        _warn_once()
        return json.dumps({"stub": True, "object_id": object_id}).encode()

    async def upload_object(self, data: bytes, container_id: str, **kwargs: Any) -> str:
        _warn_once()
        digest = hashlib.sha256(data).hexdigest()[:16]
        return f"stub-{digest}"

    async def close(self) -> None:
        pass


def get_neofs_client(*args: Any, **kwargs: Any) -> NeoFSClient:
    """Return a stub NeoFS client."""
    return NeoFSClient()


def upload_object(
    content: str,
    attributes: Optional[dict] = None,
    filename: Optional[str] = None,
) -> str:
    """Stub: return a fake object ID derived from content hash."""
    _warn_once()
    digest = hashlib.sha256(content.encode()).hexdigest()[:16]
    return f"stub-{digest}"


def upload_job_metadata(metadata: dict, **kwargs: Any) -> str:
    """Stub: return an IPFS-style URI for the metadata."""
    _warn_once()
    raw = json.dumps(metadata, sort_keys=True)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"ipfs://sota-metadata-{digest}"
