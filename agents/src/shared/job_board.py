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
    budget_flr: float                        # max budget in C2FLR
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
    amount_flr: float                        # quoted price in C2FLR
    estimated_seconds: int                   # estimated completion time
    tags: List[str]                          # what capabilities matched
    submitted_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def amount_wei(self) -> int:
        """Amount in wei (18 decimals) for on-chain C2FLR."""
        return int(self.amount_flr * 10**18)


@dataclass
class BidResult:
    """Outcome after the bid window closes."""
    job_id: str
    winning_bid: Optional[Bid]
    all_bids: List[Bid]
    reason: str                              # why this bid won (or why none)
    execution_result: Optional[Dict[str, Any]] = None  # Result from job execution


# Type aliases
WorkerEvaluator = Callable[[JobListing], Awaitable[Optional[Bid]]]
WorkerExecutor = Callable[[JobListing, "Bid"], Awaitable[Dict[str, Any]]]


# ─── Worker Registration ─────────────────────────────────────

@dataclass
class RegisteredWorker:
    """A worker agent that is registered on the board."""
    worker_id: str                           # e.g. "caller", "booker"
    address: str                             # wallet address
    tags: List[str]                          # capabilities / job type tags
    evaluator: WorkerEvaluator               # async fn that returns a Bid or None
    executor: Optional[WorkerExecutor] = None  # async fn to execute the job after winning
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
        self._winning_bids: Dict[str, Bid] = {}        # job_id → winning bid (for later retrieval)
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
        execute_after_accept: bool = True,
    ) -> BidResult:
        """
        Post a job, broadcast to workers, wait for the bid window,
        then select the best bid and optionally execute the job.

        Args:
            job: The job listing to post.
            on_chain_accept: Optional async callback to accept the bid
                on-chain (called with the winning Bid).
            execute_after_accept: If True, call the winning worker's executor
                after the bid is accepted.

        Returns:
            BidResult with the winner (or None if no bids).
        """
        self._jobs[job.job_id] = job
        self._bids[job.job_id] = []

        logger.info(
            "📢 Job posted: id=%s  tags=%s  budget=%.2f C2FLR  window=%ds",
            job.job_id, job.tags, job.budget_flr, job.bid_window_seconds,
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
            # Store winning bid for later retrieval (e.g., deferred execution)
            self._winning_bids[job.job_id] = result.winning_bid
            logger.info(
                "🏆 Winner for job %s: worker=%s  price=%.2f C2FLR  eta=%ds",
                job.job_id,
                result.winning_bid.bidder_id,
                result.winning_bid.amount_flr,
                result.winning_bid.estimated_seconds,
            )
            if on_chain_accept:
                try:
                    await on_chain_accept(result.winning_bid)
                except Exception as exc:
                    logger.error("On-chain accept failed: %s", exc)
            
            # ── 4. Execute the job if requested ──────────────
            if execute_after_accept:
                winning_worker = self._workers.get(result.winning_bid.bidder_id)
                if winning_worker and winning_worker.executor:
                    logger.info("🔄 Starting job execution for %s…", job.job_id)
                    try:
                        exec_result = await winning_worker.executor(job, result.winning_bid)
                        result.execution_result = exec_result
                        logger.info("✅ Job %s execution completed", job.job_id)
                    except Exception as exc:
                        logger.error("❌ Job execution failed: %s", exc)
                        result.execution_result = {"error": str(exc)}
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
                    "  💰 Bid received: worker=%s  price=%.2f C2FLR  eta=%ds",
                    worker.worker_id, bid.amount_flr, bid.estimated_seconds,
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

        eligible = [b for b in bids if b.amount_flr <= job.budget_flr]
        if not eligible:
            cheapest = min(bids, key=lambda b: b.amount_flr)
            return BidResult(
                job_id=job.job_id,
                winning_bid=None,
                all_bids=bids,
                reason=(
                    f"All {len(bids)} bid(s) exceeded the budget "
                    f"(cheapest: {cheapest.amount_flr:.2f} C2FLR vs "
                    f"budget {job.budget_flr:.2f} C2FLR)"
                ),
            )

        # Sort: lowest price → earliest submission
        eligible.sort(key=lambda b: (b.amount_flr, b.submitted_at))
        winner = eligible[0]

        return BidResult(
            job_id=job.job_id,
            winning_bid=winner,
            all_bids=bids,
            reason=(
                f"Lowest price: {winner.amount_flr:.2f} C2FLR "
                f"from {winner.bidder_id} "
                f"(out of {len(bids)} bid(s), {len(eligible)} under budget)"
            ),
        )

    # ── Queries ──────────────────────────────────────────────

    def get_job(self, job_id: str) -> Optional[JobListing]:
        return self._jobs.get(job_id)

    def get_bids(self, job_id: str) -> List[Bid]:
        return list(self._bids.get(job_id, []))

    def get_winning_bid(self, job_id: str) -> Optional[Bid]:
        """Get the winning bid for a job (if one was selected)."""
        return self._winning_bids.get(job_id)

    def list_open_jobs(self) -> List[JobListing]:
        return [j for j in self._jobs.values() if j.status == JobStatus.OPEN]

    def list_all_jobs(self) -> List[JobListing]:
        return list(self._jobs.values())
