"""
End-to-End Marketplace Test

Verifies the full flow:
  1. Workers register on the JobBoard with tags
  2. Butler posts a job
  3. Only matching workers place bids (within 60 s window)
  4. Board auto-selects the best bid (lowest price)

Run:
    cd agents
    python -m test_marketplace
"""

import asyncio
import logging
import sys
import time

# ── Path fix so we can import agents.src.shared ──────────────
sys.path.insert(0, ".")

from src.shared.job_board import (
    JobBoard,
    JobListing,
    Bid,
    BidResult,
    RegisteredWorker,
    JobStatus,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("marketplace_test")

BID_WINDOW = 5  # seconds (short for tests)


# ─── Fake evaluators ─────────────────────────────────────────

async def booking_evaluator(job: JobListing):
    """Booking agent bids 75 % of budget on hotel/restaurant jobs."""
    await asyncio.sleep(0.1)  # simulate brief think time
    return Bid(
        bid_id="bk-001",
        job_id=job.job_id,
        bidder_id="booker",
        bidder_address="0xBOOKER",
        amount_flr=round(job.budget_flr * 0.75, 2),
        estimated_seconds=600,
        tags=["hotel_booking"],
    )


async def caller_evaluator(job: JobListing):
    """Caller bids 90 % of budget on any job."""
    await asyncio.sleep(0.2)
    return Bid(
        bid_id="cal-001",
        job_id=job.job_id,
        bidder_id="caller",
        bidder_address="0xCALLER",
        amount_flr=round(job.budget_flr * 0.90, 2),
        estimated_seconds=1800,
        tags=["call_verification"],
    )


async def generic_evaluator(job: JobListing):
    """Generic worker — returns None (declines)."""
    return None


# ─── Test Cases ───────────────────────────────────────────────

async def test_matching_and_selection():
    """Only matching workers bid; lowest price wins."""
    print("\n" + "=" * 60)
    print("TEST 1: Tag matching + best-bid selection")
    print("=" * 60)

    JobBoard.reset()
    board = JobBoard.instance()

    # Register workers
    board.register_worker(RegisteredWorker(
        worker_id="booker",
        address="0xBOOKER",
        tags=["hotel_booking", "restaurant_booking"],
        evaluator=booking_evaluator,
    ))
    board.register_worker(RegisteredWorker(
        worker_id="caller",
        address="0xCALLER",
        tags=["call_verification", "hotel_booking",
              "restaurant_booking", "hackathon_registration", "generic"],
        evaluator=caller_evaluator,
    ))
    board.register_worker(RegisteredWorker(
        worker_id="generic",
        address="0xGENERIC",
        tags=["data_analysis"],       # doesn't match hotel_booking
        evaluator=generic_evaluator,
    ))

    job = JobListing(
        job_id="test-001",
        description="Book a hotel room in Paris for 2 nights",
        tags=["hotel_booking"],
        budget_flr=10.0,
        deadline_ts=int(time.time()) + 3600,
        poster="0xBUTLER",
        bid_window_seconds=BID_WINDOW,
    )

    result: BidResult = await board.post_and_select(job)

    assert result.winning_bid is not None, "Expected a winning bid"
    assert result.winning_bid.bidder_id == "booker", (
        f"Expected 'booker' to win (75 % < 90 %), got {result.winning_bid.bidder_id}"
    )
    assert result.winning_bid.amount_flr == 7.50
    assert len(result.all_bids) == 2, f"Expected 2 bids, got {len(result.all_bids)}"
    assert board.get_job("test-001").status == JobStatus.ASSIGNED

    print(f"  ✅ Winner: {result.winning_bid.bidder_id} @ {result.winning_bid.amount_flr} C2FLR")
    print(f"  ✅ Total bids: {len(result.all_bids)}")
    print(f"  ✅ Reason: {result.reason}")


async def test_no_matching_workers():
    """Job with no matching tags → expired."""
    print("\n" + "=" * 60)
    print("TEST 2: No matching workers → expired")
    print("=" * 60)

    JobBoard.reset()
    board = JobBoard.instance()

    board.register_worker(RegisteredWorker(
        worker_id="caller",
        address="0xCALLER",
        tags=["call_verification"],
        evaluator=caller_evaluator,
    ))

    job = JobListing(
        job_id="test-002",
        description="Register for an AI hackathon",
        tags=["hackathon_registration"],
        budget_flr=50.0,
        deadline_ts=int(time.time()) + 3600,
        poster="0xBUTLER",
        bid_window_seconds=BID_WINDOW,
    )

    result = await board.post_and_select(job)

    assert result.winning_bid is None, "Expected no winning bid"
    assert len(result.all_bids) == 0
    assert board.get_job("test-002").status == JobStatus.EXPIRED

    print(f"  ✅ No bids received — job expired as expected")
    print(f"  ✅ Reason: {result.reason}")


async def test_budget_filter():
    """All bids exceed budget → no winner."""
    print("\n" + "=" * 60)
    print("TEST 3: All bids exceed budget → no winner")
    print("=" * 60)

    JobBoard.reset()
    board = JobBoard.instance()

    async def expensive_evaluator(job: JobListing):
        return Bid(
            bid_id="exp-001",
            job_id=job.job_id,
            bidder_id="expensive",
            bidder_address="0xEXP",
            amount_flr=100.0,   # way over budget
            estimated_seconds=300,
            tags=["generic"],
        )

    board.register_worker(RegisteredWorker(
        worker_id="expensive",
        address="0xEXP",
        tags=["generic"],
        evaluator=expensive_evaluator,
    ))

    job = JobListing(
        job_id="test-003",
        description="Do a generic expensive task",
        tags=["generic"],
        budget_flr=5.0,
        deadline_ts=int(time.time()) + 3600,
        poster="0xBUTLER",
        bid_window_seconds=BID_WINDOW,
    )

    result = await board.post_and_select(job)

    assert result.winning_bid is None
    assert len(result.all_bids) == 1
    assert "exceeded the budget" in result.reason

    print(f"  ✅ Bid too expensive — correctly rejected")
    print(f"  ✅ Reason: {result.reason}")


async def test_capacity_limit():
    """Worker at capacity skipped."""
    print("\n" + "=" * 60)
    print("TEST 4: Worker at capacity → skipped")
    print("=" * 60)

    JobBoard.reset()
    board = JobBoard.instance()

    board.register_worker(RegisteredWorker(
        worker_id="busy_caller",
        address="0xBUSY",
        tags=["call_verification"],
        evaluator=caller_evaluator,
        max_concurrent=2,
        active_jobs=2,            # already full
    ))

    job = JobListing(
        job_id="test-004",
        description="Verify a phone number",
        tags=["call_verification"],
        budget_flr=10.0,
        deadline_ts=int(time.time()) + 3600,
        poster="0xBUTLER",
        bid_window_seconds=BID_WINDOW,
    )

    result = await board.post_and_select(job)

    assert result.winning_bid is None
    assert len(result.all_bids) == 0

    print(f"  ✅ Busy worker correctly skipped — no bids")


async def test_tie_breaking():
    """Same price → earliest submission wins."""
    print("\n" + "=" * 60)
    print("TEST 5: Tie-breaking (same price → earliest wins)")
    print("=" * 60)

    JobBoard.reset()
    board = JobBoard.instance()

    async def fast_eval(job: JobListing):
        return Bid(
            bid_id="fast-001",
            job_id=job.job_id,
            bidder_id="fast",
            bidder_address="0xFAST",
            amount_flr=5.0,
            estimated_seconds=300,
            tags=["hotel_booking"],
            submitted_at=time.time(),        # submitted first
        )

    async def slow_eval(job: JobListing):
        await asyncio.sleep(0.5)             # slight delay
        return Bid(
            bid_id="slow-001",
            job_id=job.job_id,
            bidder_id="slow",
            bidder_address="0xSLOW",
            amount_flr=5.0,                 # same price
            estimated_seconds=300,
            tags=["hotel_booking"],
            submitted_at=time.time(),        # submitted later
        )

    board.register_worker(RegisteredWorker(
        worker_id="fast", address="0xFAST",
        tags=["hotel_booking"], evaluator=fast_eval,
    ))
    board.register_worker(RegisteredWorker(
        worker_id="slow", address="0xSLOW",
        tags=["hotel_booking"], evaluator=slow_eval,
    ))

    job = JobListing(
        job_id="test-005",
        description="Book a hotel room",
        tags=["hotel_booking"],
        budget_flr=10.0,
        deadline_ts=int(time.time()) + 3600,
        poster="0xBUTLER",
        bid_window_seconds=BID_WINDOW,
    )

    result = await board.post_and_select(job)

    assert result.winning_bid is not None
    assert result.winning_bid.bidder_id == "fast", (
        f"Expected 'fast' (earlier), got {result.winning_bid.bidder_id}"
    )

    print(f"  ✅ Tie broken correctly — 'fast' wins")


# ─── Runner ──────────────────────────────────────────────────

async def main():
    print("🏪 SOTA Marketplace — End-to-End Tests")
    print(f"   Bid window = {BID_WINDOW}s (shortened for speed)\n")

    await test_matching_and_selection()
    await test_no_matching_workers()
    await test_budget_filter()
    await test_capacity_limit()
    await test_tie_breaking()

    print("\n" + "=" * 60)
    print("🎉 ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
