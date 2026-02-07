"""
Blockchain Event Listener for Archive Agents

Watches for contract events like JobPosted, BidAccepted, etc.
Uses WebSocket for real-time updates with polling fallback.
"""

import os
import json
import asyncio
import logging
from typing import Callable, Awaitable, Optional, Any
from dataclasses import dataclass
from enum import Enum

from web3 import Web3, AsyncWeb3
from web3.contract import Contract

from .config import get_network, get_contract_addresses
from .contracts import load_abi

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Contract event types we care about (FlareOrderBook)"""
    JOB_POSTED = "JobCreated"        # FlareOrderBook emits JobCreated
    BID_PLACED = "BidPlaced"
    BID_ACCEPTED = "BidAccepted"
    DELIVERY_SUBMITTED = "JobCompleted"  # FlareOrderBook emits JobCompleted
    PROVIDER_ASSIGNED = "ProviderAssigned"
    JOB_RELEASED = "JobReleased"
    JOB_CANCELLED = "JobCancelled"
    AGENT_REGISTERED = "AgentRegistered"


@dataclass
class JobPostedEvent:
    """Parsed JobCreated event from FlareOrderBook"""
    job_id: int
    client: str        # poster
    job_type: int      # not in event; default 0
    budget: int        # maxPriceUsd
    budget_flr: int    # maxPriceFlr
    deadline: int      # not in event; default 0
    description: str   # not in event; default ''
    block_number: int
    tx_hash: str


@dataclass
class BidPlacedEvent:
    """Parsed BidPlaced event from FlareOrderBook"""
    job_id: int
    bid_id: int
    bidder: str        # agent address
    amount: int        # priceUsd
    amount_flr: int    # priceFlr
    estimated_time: int  # not in event; default 0
    block_number: int
    tx_hash: str


@dataclass
class BidAcceptedEvent:
    """Parsed BidAccepted event from FlareOrderBook"""
    job_id: int
    bid_id: int
    worker: str        # provider
    amount: int        # not in event; default 0
    block_number: int
    tx_hash: str


@dataclass
class DeliverySubmittedEvent:
    """Parsed JobCompleted event from FlareOrderBook"""
    job_id: int
    worker: str        # not in event; default ''
    result_uri: str    # not in event; default ''
    delivery_proof: str  # bytes32 hex
    timestamp: int     # not in event; default 0
    block_number: int
    tx_hash: str


# Aliases for convenience
BidSubmittedEvent = BidPlacedEvent


EventCallback = Callable[[Any], Awaitable[None]]


class EventListener:
    """
    Async event listener for Archive Protocol contracts.
    
    Watches for events and triggers callbacks for each agent type.
    """
    
    def __init__(
        self,
        poll_interval: int = 3,
        confirmations: int = 1
    ):
        """
        Initialize event listener.
        
        Args:
            poll_interval: Seconds between polls
            confirmations: Block confirmations required
        """
        self.network = get_network()
        self.addresses = get_contract_addresses()
        self.poll_interval = poll_interval
        self.confirmations = confirmations
        
        # Callbacks per event type
        self._callbacks: dict[EventType, list[EventCallback]] = {
            et: [] for et in EventType
        }
        
        # State
        self._running = False
        self._last_block: Optional[int] = None
        self._w3: Optional[Web3] = None
        self._order_book: Optional[Contract] = None
        self._agent_registry: Optional[Contract] = None
    
    def _setup_contracts(self):
        """Initialize Web3 and contract instances"""
        self._w3 = Web3(Web3.HTTPProvider(self.network.rpc_url))
        
        if self.addresses.flare_order_book:
            order_book_abi = load_abi("FlareOrderBook")
            self._order_book = self._w3.eth.contract(
                address=Web3.to_checksum_address(self.addresses.flare_order_book),
                abi=order_book_abi
            )
        
        if self.addresses.agent_registry:
            agent_registry_abi = load_abi("AgentRegistry")
            self._agent_registry = self._w3.eth.contract(
                address=Web3.to_checksum_address(self.addresses.agent_registry),
                abi=agent_registry_abi
            )
    
    def on_event(self, event_type: EventType, callback: EventCallback):
        """
        Register a callback for an event type.
        
        Args:
            event_type: Type of event to listen for
            callback: Async function to call when event occurs
        """
        self._callbacks[event_type].append(callback)
        logger.debug(f"Registered callback for {event_type.value}")
    
    def on_job_posted(self, callback: Callable[[JobPostedEvent], Awaitable[None]]):
        """Register callback for JobPosted events"""
        self.on_event(EventType.JOB_POSTED, callback)
    
    def on_bid_placed(self, callback: Callable[[BidPlacedEvent], Awaitable[None]]):
        """Register callback for BidPlaced events"""
        self.on_event(EventType.BID_PLACED, callback)
    
    # Alias for on_bid_placed
    on_bid_submitted = on_bid_placed
    
    def on_bid_accepted(self, callback: Callable[[BidAcceptedEvent], Awaitable[None]]):
        """Register callback for BidAccepted events"""
        self.on_event(EventType.BID_ACCEPTED, callback)
    
    def on_delivery_submitted(self, callback: Callable[[DeliverySubmittedEvent], Awaitable[None]]):
        """Register callback for DeliverySubmitted events"""
        self.on_event(EventType.DELIVERY_SUBMITTED, callback)
    
    async def _process_job_posted(self, event: dict):
        """Parse and dispatch JobCreated event"""
        args = event['args']
        parsed = JobPostedEvent(
            job_id=args.get('jobId', 0),
            client=args.get('poster', ''),
            job_type=0,  # not in JobCreated event
            budget=args.get('maxPriceUsd', 0),
            budget_flr=args.get('maxPriceFlr', 0),
            deadline=0,  # not in JobCreated event
            description='',  # not in JobCreated event
            block_number=event['blockNumber'],
            tx_hash=event['transactionHash'].hex() if event['transactionHash'] else ''
        )
        logger.info("JobCreated evt job_id=%s poster=%s budget_usd=%s budget_flr=%s tx=%s",
                    parsed.job_id, parsed.client, parsed.budget, parsed.budget_flr, parsed.tx_hash)
        for callback in self._callbacks[EventType.JOB_POSTED]:
            try:
                await callback(parsed)
            except Exception as e:
                logger.error(f"Error in JobCreated callback: {e}")
    
    async def _process_bid_placed(self, event: dict):
        """Parse and dispatch BidPlaced event"""
        args = event['args']
        parsed = BidPlacedEvent(
            job_id=args.get('jobId', 0),
            bid_id=args.get('bidId', 0),
            bidder=args.get('agent', ''),
            amount=args.get('priceUsd', 0),
            amount_flr=args.get('priceFlr', 0),
            estimated_time=0,  # not in BidPlaced event
            block_number=event['blockNumber'],
            tx_hash=event['transactionHash'].hex() if event['transactionHash'] else ''
        )
        logger.info("BidPlaced evt job_id=%s bid_id=%s agent=%s price_usd=%s tx=%s",
                    parsed.job_id, parsed.bid_id, parsed.bidder, parsed.amount, parsed.tx_hash)
        for callback in self._callbacks[EventType.BID_PLACED]:
            try:
                await callback(parsed)
            except Exception as e:
                logger.error(f"Error in BidPlaced callback: {e}")
    
    async def _process_bid_accepted(self, event: dict):
        """Parse and dispatch BidAccepted event"""
        args = event['args']
        parsed = BidAcceptedEvent(
            job_id=args.get('jobId', 0),
            bid_id=args.get('bidId', 0),
            worker=args.get('provider', ''),
            amount=0,  # not in BidAccepted event
            block_number=event['blockNumber'],
            tx_hash=event['transactionHash'].hex() if event['transactionHash'] else ''
        )
        logger.info("BidAccepted evt job_id=%s bid_id=%s provider=%s tx=%s",
                    parsed.job_id, parsed.bid_id, parsed.worker, parsed.tx_hash)
        for callback in self._callbacks[EventType.BID_ACCEPTED]:
            try:
                await callback(parsed)
            except Exception as e:
                logger.error(f"Error in BidAccepted callback: {e}")
    
    async def _process_delivery_submitted(self, event: dict):
        """Parse and dispatch JobCompleted event"""
        args = event['args']
        proof = args.get('deliveryProof', b'')
        proof_hex = proof.hex() if isinstance(proof, bytes) else str(proof)
        parsed = DeliverySubmittedEvent(
            job_id=args.get('jobId', 0),
            worker='',  # not in JobCompleted event
            result_uri='',  # not in JobCompleted event
            delivery_proof=proof_hex,
            timestamp=0,  # not in JobCompleted event
            block_number=event['blockNumber'],
            tx_hash=event['transactionHash'].hex() if event['transactionHash'] else ''
        )
        logger.info("JobCompleted evt job_id=%s proof=%s tx=%s",
                    parsed.job_id, parsed.delivery_proof[:16], parsed.tx_hash)
        for callback in self._callbacks[EventType.DELIVERY_SUBMITTED]:
            try:
                await callback(parsed)
            except Exception as e:
                logger.error(f"Error in DeliverySubmitted callback: {e}")

    async def _poll_events(self):
        """Poll for new events"""
        if not self._w3 or not self._order_book:
            return
        
        try:
            current_block = self._w3.eth.block_number
            safe_block = current_block - self.confirmations
            
            if self._last_block is None:
                self._last_block = safe_block - 1
            
            if safe_block <= self._last_block:
                return
            
            from_block = self._last_block + 1
            to_block = safe_block
            
            logger.debug(f"Polling blocks {from_block} to {to_block}")
            
            # Get JobCreated events
            if self._callbacks[EventType.JOB_POSTED]:
                try:
                    events = self._order_book.events.JobCreated.get_logs(
                        from_block=from_block,
                        to_block=to_block
                    )
                    for event in events:
                        await self._process_job_posted(event)
                except Exception as e:
                    logger.debug(f"No JobCreated events or error: {e}")
            
            # Get BidPlaced events
            if self._callbacks[EventType.BID_PLACED]:
                try:
                    events = self._order_book.events.BidPlaced.get_logs(
                        from_block=from_block,
                        to_block=to_block
                    )
                    for event in events:
                        await self._process_bid_placed(event)
                except Exception as e:
                    logger.debug(f"No BidPlaced events or error: {e}")
            
            # Get BidAccepted events
            if self._callbacks[EventType.BID_ACCEPTED]:
                try:
                    events = self._order_book.events.BidAccepted.get_logs(
                        from_block=from_block,
                        to_block=to_block
                    )
                    for event in events:
                        await self._process_bid_accepted(event)
                except Exception as e:
                    logger.debug(f"No BidAccepted events or error: {e}")
            
            # Get JobCompleted events
            if self._callbacks[EventType.DELIVERY_SUBMITTED]:
                try:
                    events = self._order_book.events.JobCompleted.get_logs(
                        from_block=from_block,
                        to_block=to_block
                    )
                    for event in events:
                        await self._process_delivery_submitted(event)
                except Exception as e:
                    logger.debug(f"No JobCompleted events or error: {e}")
            
            self._last_block = to_block
            
        except Exception as e:
            logger.error(f"Error polling events: {e}")
    
    async def start(self):
        """Start the event listener"""
        logger.info("Starting event listener...")
        self._setup_contracts()
        self._running = True
        
        while self._running:
            await self._poll_events()
            await asyncio.sleep(self.poll_interval)
    
    def stop(self):
        """Stop the event listener"""
        logger.info("Stopping event listener...")
        self._running = False

    async def catch_up(self, blocks_back: int = 20):
        """Process recent events immediately (e.g., jobs posted before agent startup)."""
        if not self._w3 or not self._order_book:
            self._setup_contracts()
        try:
            current_block = self._w3.eth.block_number
            safe_block = current_block - self.confirmations
            if safe_block <= 0:
                return
            from_block = max(0, safe_block - blocks_back)
            to_block = safe_block
            logger.info("Catching up events from block %s to %s", from_block, to_block)

            if self._callbacks[EventType.JOB_POSTED]:
                events = self._order_book.events.JobCreated.get_logs(
                    from_block=from_block,
                    to_block=to_block,
                )
                for event in events:
                    await self._process_job_posted(event)

            if self._callbacks[EventType.BID_PLACED]:
                events = self._order_book.events.BidPlaced.get_logs(
                    from_block=from_block,
                    to_block=to_block,
                )
                for event in events:
                    await self._process_bid_placed(event)

            if self._callbacks[EventType.BID_ACCEPTED]:
                events = self._order_book.events.BidAccepted.get_logs(
                    from_block=from_block,
                    to_block=to_block,
                )
                for event in events:
                    await self._process_bid_accepted(event)

            if self._callbacks[EventType.DELIVERY_SUBMITTED]:
                events = self._order_book.events.JobCompleted.get_logs(
                    from_block=from_block,
                    to_block=to_block,
                )
                for event in events:
                    await self._process_delivery_submitted(event)

            self._last_block = to_block
        except Exception as e:
            logger.error("Catch-up failed: %s", e)
    
    async def run_once(self):
        """Poll events once (for testing)"""
        self._setup_contracts()
        await self._poll_events()


def create_event_listener(poll_interval: int = 3) -> EventListener:
    """Create a new event listener instance"""
    return EventListener(poll_interval=poll_interval)
