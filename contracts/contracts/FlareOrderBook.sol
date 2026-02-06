// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";
import "./FTSOPriceConsumer.sol";

/**
 * @title FlareOrderBook
 * @notice Simplified job lifecycle for the SOTA Flare marketplace.
 *
 *         Workflow:
 *           1. createJob()      — poster describes work + max USD budget
 *           2. assignProvider() — poster picks an agent
 *           3. markCompleted()  — agent declares work done
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
        CANCELLED
    }

    struct Job {
        uint256 id;
        address poster;
        address provider;           // assigned agent
        string  metadataURI;        // IPFS / off-chain job description
        uint256 maxPriceUsd;        // budget in USD (18 decimals)
        uint256 maxPriceFlr;        // FTSO-derived FLR equivalent at creation
        uint64  deadline;
        JobStatus status;
        bytes32 deliveryProof;
        uint256 createdAt;
    }

    // ─── State ──────────────────────────────────────────────

    uint256 private _nextJobId = 1;
    mapping(uint256 => Job) public jobs;
    uint256[] public jobIds;                    // for enumeration

    FTSOPriceConsumer public ftso;
    address public escrow;                      // FlareEscrow address

    // ─── Events ─────────────────────────────────────────────

    event JobCreated(
        uint256 indexed jobId,
        address indexed poster,
        uint256 maxPriceUsd,
        uint256 maxPriceFlr
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
     *
     * @param metadataURI  Off-chain metadata (IPFS CID, URL, etc.)
     * @param maxPriceUsd  Maximum budget in USD, 18-decimal (e.g. 50 USD = 50e18)
     * @param deadline     Unix timestamp by which the job must be completed
     * @return jobId       The new job's on-chain ID
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
            createdAt: block.timestamp
        });

        jobIds.push(jobId);
        emit JobCreated(jobId, msg.sender, maxPriceUsd, flrEquivalent);
    }

    /**
     * @notice Poster assigns an agent to the job.
     *         After assignment, the poster should call FlareEscrow.fundJob().
     */
    function assignProvider(
        uint256 jobId,
        address provider
    ) external {
        Job storage job = jobs[jobId];
        require(job.poster == msg.sender, "FlareOrderBook: not poster");
        require(
            job.status == JobStatus.OPEN,
            "FlareOrderBook: not open"
        );
        require(provider != address(0), "FlareOrderBook: zero provider");

        job.provider = provider;
        job.status = JobStatus.ASSIGNED;

        emit ProviderAssigned(jobId, provider);
    }

    /**
     * @notice Assigned agent marks the job as completed.
     *         After this, the FDC proof must be submitted to FDCVerifier,
     *         then FlareEscrow.releaseToProvider() can be called.
     */
    function markCompleted(
        uint256 jobId,
        bytes32 deliveryProof
    ) external {
        Job storage job = jobs[jobId];
        require(
            job.provider == msg.sender,
            "FlareOrderBook: not provider"
        );
        require(
            job.status == JobStatus.ASSIGNED,
            "FlareOrderBook: not assigned"
        );

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
        require(
            job.status == JobStatus.OPEN,
            "FlareOrderBook: not open"
        );
        job.status = JobStatus.CANCELLED;
        emit JobCancelled(jobId);
    }

    // ─── Views ──────────────────────────────────────────────

    /**
     * @notice Get a quote: how much FLR is needed for a given USD amount.
     *         Front-end calls this to show "≈ X FLR" before posting.
     */
    function quoteUsdToFlr(
        uint256 usdAmount
    ) external view returns (uint256 flrAmount) {
        flrAmount = ftso.usdToFlr(usdAmount);
    }

    function getJob(uint256 jobId) external view returns (Job memory) {
        return jobs[jobId];
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
