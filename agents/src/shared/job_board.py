"""
Job Board — In-Memory Marketplace for SOTA Agents

Central hub where:
1. Butler posts a job → broadcast to all registered workers
2. Workers evaluate the job against their tags/capabilities
3. Workers place bids within a configurable window (default 60 s)
4. When the window closes the board auto-selects the best bid
   (lowest price wins; ties broken by earliest submission)
5. The winning bid is accepted on-chain and the result returned
   to the Butler

This is a **process-local** singleton.  In production you would
replace the in-memory dicts with Redis / a DB, but the interface
stays the same.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


# ─── Data Types ───────────────────────────────────────────────

class JobStatus(str, Enum):
    OPEN = "open"               # accepting bids
    SELECTING = "selecting"     # bid window closed, choosing winner
    ASSIGNED = "assigned"       # winner picked
    EXPIRED = "expired"         # no bids received
    CANCELLED = "cancelled"


@dataclass
class JobListing:
    """A job posted on the board."""
    job_id: str                              # unique id (on-chain id or uuid)
    description: str
    tags: List[str]                          # e.g. ["hotel_booking", "call_verification"]
    budget_usdc: float                       # max budget in USDC
    deadline_ts: int                         # unix timestamp
    poster: str                              # wallet address of poster
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: JobStatus = JobStatus.OPEN
    posted_at: float = field(default_factory=time.time)
    bid_window_seconds: int = 60             # how long to collect bids


@dataclass
class Bid:
    """A bid from a worker agent."""
    bid_id: str
    job_id: str
    bidder_id: str                           # agent identifier
    bidder_address: str                      # wallet address
    amount_usdc: float                       # quoted price
    estimated_seconds: int                   # estimated completion time
    tags: List[str]                          # what capabilities matched
    submitted_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def amount_micro(self) -> int:
        """Amount in on-chain micro-USDC (6 decimals)."""
        return int(self.amount_usdc * 1_000_000)


@dataclass
class BidResult:
    """Outcome after the bid window closes."""
    job_id: str
    winning_bid: Optional[Bid]
    all_bids: List[Bid]
    reason: str                              # why this bid won (or why none)


# Type aliases
WorkerEvaluator = Callable[[JobListing], Awaitable[Optional[Bid]]]


# ─── Worker Registration ─────────────────────────────────────

@dataclass
class RegisteredWorker:
    """A worker agent that is registered on the board."""
    worker_id: str                           # e.g. "caller", "booker"
    address: str                             # wallet address
    tags: List[str]                          # capabilities / job type tags
    evaluator: WorkerEvaluator               # async fn that returns a Bid or None
    max_concurrent: int = 5
    active_jobs: int = 0


# ─── Job Board (Singleton) ───────────────────────────────────

class JobBoard:
    """
    Process-local job marketplace.

    Usage::

        board = JobBoard.instance()

        # Worker side (at startup)
        board.register_worker(RegisteredWorker(
            worker_id="caller",
            address="0x...",
            tags=["call_verification", "hotel_booking"],
            evaluator=my_evaluate_fn,
        ))

        # Butler side
        result = await board.post_and_select(job)
        # → returns BidResult with the winning bid after 60 s
    """

    _instance: Optional["JobBoard"] = None

    def __init__(self):
        self._workers: Dict[str, RegisteredWorker] = {}
        self._jobs: Dict[str, JobListing] = {}
        self._bids: Dict[str, List[Bid]] = {}          # job_id → bids
        self._listeners: List[Callable] = []

    # ── Singleton ────────────────────────────────────────────

    @classmethod
    def instance(cls) -> "JobBoard":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset the singleton (for tests)."""
        cls._instance = None

    # ── Worker Management ────────────────────────────────────

    def register_worker(self, worker: RegisteredWorker):
        self._workers[worker.worker_id] = worker
        logger.info(
            "📋 Worker registered: %s  tags=%s  addr=%s",
            worker.worker_id, worker.tags, worker.address,
        )

    def unregister_worker(self, worker_id: str):
        self._workers.pop(worker_id, None)
        logger.info("Worker unregistered: %s", worker_id)

    @property
    def workers(self) -> Dict[str, RegisteredWorker]:
        return dict(self._workers)

    # ── Job Posting & Selection ──────────────────────────────

    async def post_and_select(
        self,
        job: JobListing,
        *,
        on_chain_accept: Optional[Callable[[Bid], Awaitable[None]]] = None,
    ) -> BidResult:
        """
        Post a job, broadcast to workers, wait for the bid window,
        then select the best bid.

        Args:
            job: The job listing to post.
            on_chain_accept: Optional async callback to accept the bid
                on-chain (called with the winning Bid).

        Returns:
            BidResult with the winner (or None if no bids).
        """
        self._jobs[job.job_id] = job
        self._bids[job.job_id] = []

        logger.info(
            "📢 Job posted: id=%s  tags=%s  budget=%.2f USDC  window=%ds",
            job.job_id, job.tags, job.budget_usdc, job.bid_window_seconds,
        )

        # ── 1. Broadcast to matching workers ─────────────────
        matching = self._find_matching_workers(job)
        logger.info(
            "  → %d matching worker(s): %s",
            len(matching), [w.worker_id for w in matching],
        )

        # Launch evaluations concurrently
        tasks = [
            asyncio.create_task(self._solicit_bid(worker, job))
            for worker in matching
        ]

        # ── 2. Wait for the bid window ───────────────────────
        logger.info("  ⏳ Bid window open for %d seconds…", job.bid_window_seconds)
        await asyncio.sleep(job.bid_window_seconds)
        job.status = JobStatus.SELECTING

        # Cancel any stragglers
        for t in tasks:
            if not t.done():
                t.cancel()

        # Give cancelled tasks a moment to settle
        await asyncio.sleep(0.1)

        # ── 3. Select the best bid ───────────────────────────
        bids = self._bids.get(job.job_id, [])
        result = self._select_best(job, bids)

        if result.winning_bid:
            job.status = JobStatus.ASSIGNED
            logger.info(
                "🏆 Winner for job %s: worker=%s  price=%.2f USDC  eta=%ds",
                job.job_id,
                result.winning_bid.bidder_id,
                result.winning_bid.amount_usdc,
                result.winning_bid.estimated_seconds,
            )
            if on_chain_accept:
                try:
                    await on_chain_accept(result.winning_bid)
                except Exception as exc:
                    logger.error("On-chain accept failed: %s", exc)
        else:
            job.status = JobStatus.EXPIRED
            logger.warning("⚠️ No bids received for job %s", job.job_id)

        return result

    # ── Internals ────────────────────────────────────────────

    def _find_matching_workers(self, job: JobListing) -> List[RegisteredWorker]:
        """Return workers whose tags overlap with the job's tags."""
        matching: List[RegisteredWorker] = []
        job_tags = set(t.lower() for t in job.tags)

        for worker in self._workers.values():
            # Skip workers at capacity
            if worker.active_jobs >= worker.max_concurrent:
                continue
            worker_tags = set(t.lower() for t in worker.tags)
            if job_tags & worker_tags:                    # at least 1 tag overlap
                matching.append(worker)

        return matching

    async def _solicit_bid(self, worker: RegisteredWorker, job: JobListing):
        """Ask a single worker to evaluate and optionally bid."""
        try:
            bid = await asyncio.wait_for(
                worker.evaluator(job),
                timeout=job.bid_window_seconds,
            )
            if bid is not None:
                bid.job_id = job.job_id            # ensure consistency
                bid.bidder_id = worker.worker_id
                bid.bidder_address = worker.address
                self._bids[job.job_id].append(bid)
                logger.info(
                    "  💰 Bid received: worker=%s  price=%.2f USDC  eta=%ds",
                    worker.worker_id, bid.amount_usdc, bid.estimated_seconds,
                )
        except asyncio.TimeoutError:
            logger.debug("  Worker %s timed out on job %s", worker.worker_id, job.job_id)
        except Exception as exc:
            logger.error(
                "  Worker %s evaluation failed for job %s: %s",
                worker.worker_id, job.job_id, exc,
            )

    @staticmethod
    def _select_best(job: JobListing, bids: List[Bid]) -> BidResult:
        """
        Pick the best bid.

        Strategy:
            1. Filter out bids above the budget.
            2. Sort by lowest price first.
            3. Break ties by earliest submitted_at.
        """
        if not bids:
            return BidResult(
                job_id=job.job_id,
                winning_bid=None,
                all_bids=bids,
                reason="No bids received within the window",
            )

        eligible = [b for b in bids if b.amount_usdc <= job.budget_usdc]
        if not eligible:
            cheapest = min(bids, key=lambda b: b.amount_usdc)
            return BidResult(
                job_id=job.job_id,
                winning_bid=None,
                all_bids=bids,
                reason=(
                    f"All {len(bids)} bid(s) exceeded the budget "
                    f"(cheapest: {cheapest.amount_usdc:.2f} USDC vs "
                    f"budget {job.budget_usdc:.2f} USDC)"
                ),
            )

        # Sort: lowest price → earliest submission
        eligible.sort(key=lambda b: (b.amount_usdc, b.submitted_at))
        winner = eligible[0]

        return BidResult(
            job_id=job.job_id,
            winning_bid=winner,
            all_bids=bids,
            reason=(
                f"Lowest price: {winner.amount_usdc:.2f} USDC "
                f"from {winner.bidder_id} "
                f"(out of {len(bids)} bid(s), {len(eligible)} under budget)"
            ),
        )

    # ── Queries ──────────────────────────────────────────────

    def get_job(self, job_id: str) -> Optional[JobListing]:
        return self._jobs.get(job_id)

    def get_bids(self, job_id: str) -> List[Bid]:
        return list(self._bids.get(job_id, []))

    def list_open_jobs(self) -> List[JobListing]:
        return [j for j in self._jobs.values() if j.status == JobStatus.OPEN]

    def list_all_jobs(self) -> List[JobListing]:
        return list(self._jobs.values())
