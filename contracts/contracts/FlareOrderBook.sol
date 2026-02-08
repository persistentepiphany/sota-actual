// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";
import "./FTSOPriceConsumer.sol";

/**
 * @title FlareOrderBook
 * @notice Job lifecycle with competitive bidding for the SOTA Flare marketplace.
 *
 *         Workflow:
 *           1. createJob()      — poster describes work + max USD budget (FTSO-priced)
 *           2. placeBid()       — agents bid with a price ≤ budget
 *           3. acceptBid()      — poster selects the winning bid → assigns provider
 *           4. markCompleted()  — agent declares work done
 *           5. markReleased()   — called by FlareEscrow after FDC-gated release
 *
 *         Price conversion uses FTSO (Flare MAIN track requirement).
 *         Escrow release is gated by FDC (handled in FlareEscrow).
 */
contract FlareOrderBook is Ownable {
    // ─── Types ──────────────────────────────────────────────

    enum JobStatus {
        OPEN,
        ASSIGNED,
        COMPLETED,
        RELEASED,
        CANCELLED,
        DISPUTED
    }

    struct Job {
        uint256 id;
        address poster;
        address provider;           // assigned agent (after acceptBid)
        string  metadataURI;        // IPFS / off-chain job description
        uint256 maxPriceUsd;        // budget in USD (18 decimals)
        uint256 maxPriceFlr;        // FTSO-derived FLR equivalent at creation
        uint64  deadline;
        JobStatus status;
        bytes32 deliveryProof;
        uint256 createdAt;
        uint256 acceptedBidId;      // winning bid ID
    }

    struct Bid {
        uint256 id;
        uint256 jobId;
        address agent;
        uint256 priceUsd;           // bid price in USD (18 decimals)
        uint256 priceFlr;           // FTSO-derived FLR at bid time
        uint256 estimatedTime;      // seconds to complete
        string  proposal;           // brief description of approach
        uint256 createdAt;
        bool    accepted;
    }

    // ─── State ──────────────────────────────────────────────

    uint256 private _nextJobId = 1;
    uint256 private _nextBidId = 1;
    mapping(uint256 => Job) public jobs;
    mapping(uint256 => Bid) public bids;
    mapping(uint256 => uint256[]) public jobBids;   // jobId → bidId[]
    uint256[] public jobIds;                         // for enumeration

    FTSOPriceConsumer public ftso;
    address public escrow;                           // FlareEscrow address

    // ─── Events ─────────────────────────────────────────────

    event JobCreated(
        uint256 indexed jobId,
        address indexed poster,
        uint256 maxPriceUsd,
        uint256 maxPriceFlr
    );
    event BidPlaced(
        uint256 indexed jobId,
        uint256 indexed bidId,
        address indexed agent,
        uint256 priceUsd,
        uint256 priceFlr
    );
    event BidAccepted(
        uint256 indexed jobId,
        uint256 indexed bidId,
        address indexed provider
    );
    event ProviderAssigned(
        uint256 indexed jobId,
        address indexed provider
    );
    event JobCompleted(
        uint256 indexed jobId,
        bytes32 deliveryProof
    );
    event JobReleased(uint256 indexed jobId);
    event JobCancelled(uint256 indexed jobId);
    event JobDisputed(uint256 indexed jobId, address indexed disputedBy);

    // ─── Constructor ────────────────────────────────────────

    constructor(
        address initialOwner,
        address ftsoConsumer
    ) Ownable(initialOwner) {
        ftso = FTSOPriceConsumer(ftsoConsumer);
    }

    // ─── Config ─────────────────────────────────────────────

    function setEscrow(address escrow_) external onlyOwner {
        escrow = escrow_;
    }

    function setFTSO(address ftsoConsumer) external onlyOwner {
        ftso = FTSOPriceConsumer(ftsoConsumer);
    }

    // ─── Core Functions ─────────────────────────────────────

    /**
     * @notice Post a new job with a max USD budget.
     *         FTSO is used to derive the FLR equivalent for on-chain pricing.
     */
    function createJob(
        string calldata metadataURI,
        uint256 maxPriceUsd,
        uint64 deadline
    ) external returns (uint256 jobId) {
        require(maxPriceUsd > 0, "FlareOrderBook: zero budget");
        require(deadline > block.timestamp, "FlareOrderBook: past deadline");

        // ── FTSO integration (Flare MAIN) ──
        uint256 flrEquivalent = ftso.usdToFlr(maxPriceUsd);
        require(flrEquivalent > 0, "FlareOrderBook: FTSO price error");

        jobId = _nextJobId++;

        jobs[jobId] = Job({
            id: jobId,
            poster: msg.sender,
            provider: address(0),
            metadataURI: metadataURI,
            maxPriceUsd: maxPriceUsd,
            maxPriceFlr: flrEquivalent,
            deadline: deadline,
            status: JobStatus.OPEN,
            deliveryProof: bytes32(0),
            createdAt: block.timestamp,
            acceptedBidId: 0
        });

        jobIds.push(jobId);
        emit JobCreated(jobId, msg.sender, maxPriceUsd, flrEquivalent);
    }

    /**
     * @notice Agent places a bid on an OPEN job.
     *         Bid price must be ≤ the job's max budget.
     *         FTSO converts the bid's USD price to FLR at bid time.
     */
    function placeBid(
        uint256 jobId,
        uint256 priceUsd,
        uint256 estimatedTime,
        string calldata proposal
    ) external returns (uint256 bidId) {
        Job storage job = jobs[jobId];
        require(job.status == JobStatus.OPEN, "FlareOrderBook: not open");
        require(block.timestamp < job.deadline, "FlareOrderBook: past deadline");
        require(priceUsd > 0, "FlareOrderBook: zero bid");
        require(priceUsd <= job.maxPriceUsd, "FlareOrderBook: bid exceeds budget");
        require(msg.sender != job.poster, "FlareOrderBook: poster cannot bid");

        uint256 flrEquivalent = ftso.usdToFlr(priceUsd);

        bidId = _nextBidId++;
        bids[bidId] = Bid({
            id: bidId,
            jobId: jobId,
            agent: msg.sender,
            priceUsd: priceUsd,
            priceFlr: flrEquivalent,
            estimatedTime: estimatedTime,
            proposal: proposal,
            createdAt: block.timestamp,
            accepted: false
        });

        jobBids[jobId].push(bidId);
        emit BidPlaced(jobId, bidId, msg.sender, priceUsd, flrEquivalent);
    }

    /**
     * @notice Poster accepts a bid and assigns the agent.
     *         After acceptance, the poster should call FlareEscrow.fundJob().
     */
    function acceptBid(uint256 jobId, uint256 bidId) external {
        Job storage job = jobs[jobId];
        require(job.poster == msg.sender, "FlareOrderBook: not poster");
        require(job.status == JobStatus.OPEN, "FlareOrderBook: not open");

        Bid storage bid = bids[bidId];
        require(bid.jobId == jobId, "FlareOrderBook: bid/job mismatch");
        require(!bid.accepted, "FlareOrderBook: bid already accepted");

        bid.accepted = true;
        job.provider = bid.agent;
        job.status = JobStatus.ASSIGNED;
        job.acceptedBidId = bidId;

        emit BidAccepted(jobId, bidId, bid.agent);
        emit ProviderAssigned(jobId, bid.agent);
    }

    /**
     * @notice Poster assigns an agent directly (without bidding).
     *         After assignment, the poster should call FlareEscrow.fundJob().
     */
    function assignProvider(
        uint256 jobId,
        address provider
    ) external {
        Job storage job = jobs[jobId];
        require(job.poster == msg.sender, "FlareOrderBook: not poster");
        require(job.status == JobStatus.OPEN, "FlareOrderBook: not open");
        require(provider != address(0), "FlareOrderBook: zero provider");

        job.provider = provider;
        job.status = JobStatus.ASSIGNED;

        emit ProviderAssigned(jobId, provider);
    }

    /**
     * @notice Poster or provider marks the job as completed.
     *         After this, the FDC proof must be submitted to FDCVerifier,
     *         then FlareEscrow.releaseToProvider() can be called.
     */
    function markCompleted(
        uint256 jobId,
        bytes32 deliveryProof
    ) external {
        Job storage job = jobs[jobId];
        require(
            job.provider == msg.sender || job.poster == msg.sender,
            "FlareOrderBook: not poster or provider"
        );
        require(job.status == JobStatus.ASSIGNED, "FlareOrderBook: not assigned");

        job.status = JobStatus.COMPLETED;
        job.deliveryProof = deliveryProof;

        emit JobCompleted(jobId, deliveryProof);
    }

    /**
     * @notice Called by FlareEscrow after successful payment release.
     */
    function markReleased(uint256 jobId) external {
        require(msg.sender == escrow, "FlareOrderBook: not escrow");
        jobs[jobId].status = JobStatus.RELEASED;
        emit JobReleased(jobId);
    }

    /**
     * @notice Poster can cancel an OPEN job (before assignment).
     */
    function cancelJob(uint256 jobId) external {
        Job storage job = jobs[jobId];
        require(job.poster == msg.sender, "FlareOrderBook: not poster");
        require(job.status == JobStatus.OPEN, "FlareOrderBook: not open");
        job.status = JobStatus.CANCELLED;
        emit JobCancelled(jobId);
    }

    /**
     * @notice Poster or provider can raise a dispute on an ASSIGNED or COMPLETED job.
     */
    function raiseDispute(uint256 jobId) external {
        Job storage job = jobs[jobId];
        require(
            msg.sender == job.poster || msg.sender == job.provider,
            "FlareOrderBook: not party"
        );
        require(
            job.status == JobStatus.ASSIGNED || job.status == JobStatus.COMPLETED,
            "FlareOrderBook: cannot dispute"
        );
        job.status = JobStatus.DISPUTED;
        emit JobDisputed(jobId, msg.sender);
    }

    // ─── Views ──────────────────────────────────────────────

    /**
     * @notice Get a quote: how much FLR is needed for a given USD amount.
     */
    function quoteUsdToFlr(
        uint256 usdAmount
    ) external view returns (uint256 flrAmount) {
        flrAmount = ftso.usdToFlr(usdAmount);
    }

    function getJob(uint256 jobId) external view returns (Job memory) {
        return jobs[jobId];
    }

    function getBid(uint256 bidId) external view returns (Bid memory) {
        return bids[bidId];
    }

    function getJobBidIds(uint256 jobId) external view returns (uint256[] memory) {
        return jobBids[jobId];
    }

    function getJobBidCount(uint256 jobId) external view returns (uint256) {
        return jobBids[jobId].length;
    }

    function totalJobs() external view returns (uint256) {
        return jobIds.length;
    }

    function getJobIds(
        uint256 offset,
        uint256 limit
    ) external view returns (uint256[] memory ids) {
        uint256 total = jobIds.length;
        if (offset >= total) return new uint256[](0);
        uint256 end = offset + limit > total ? total : offset + limit;
        ids = new uint256[](end - offset);
        for (uint256 i = offset; i < end; i++) {
            ids[i - offset] = jobIds[i];
        }
    }
}
