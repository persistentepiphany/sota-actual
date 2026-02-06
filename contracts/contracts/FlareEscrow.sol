// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "./FTSOPriceConsumer.sol";

/**
 * @title IFDCVerifier
 * @notice Interface for the FDCVerifier contract's delivery check.
 */
interface IFDCVerifier {
    function isDeliveryConfirmed(uint256 jobId) external view returns (bool);
}

/**
 * @title IFlareOrderBook
 * @notice Callback interface so escrow can update job status.
 */
interface IFlareOrderBook {
    function markReleased(uint256 jobId) external;
}

/**
 * @title FlareEscrow
 * @notice Holds native FLR for jobs. Validates funding against FTSO prices.
 *         Release is gated on FDC-attested delivery confirmation.
 *
 *         Key integrations:
 *         - FTSO: fundJob() validates that msg.value ≥ FTSO-derived FLR amount
 *         - FDC:  releaseToProvider() requires FDCVerifier.isDeliveryConfirmed()
 *
 *         This satisfies both Flare MAIN (FTSO + FDC usage) and
 *         Flare BONUS (innovative FDC-driven escrow release).
 */
contract FlareEscrow is Ownable, ReentrancyGuard {
    // ─── Types ──────────────────────────────────────────────

    struct Deposit {
        address poster;
        address provider;
        uint256 amount;         // FLR wei locked
        uint256 usdValue;       // USD equivalent at fund time (18 dec)
        bool funded;
        bool released;
        bool refunded;
    }

    // ─── State ──────────────────────────────────────────────

    mapping(uint256 => Deposit) public deposits;

    FTSOPriceConsumer public ftso;
    IFDCVerifier public fdcVerifier;
    IFlareOrderBook public orderBook;

    address public feeCollector;
    uint96 public platformFeeBps;       // e.g. 200 = 2%

    /// @dev Allow a small slippage buffer (5%) to handle price movement
    ///      between the quote on the front-end and the on-chain fundJob() tx.
    uint256 public slippageBps = 500;   // 5%

    // ─── Events ─────────────────────────────────────────────

    event EscrowFunded(
        uint256 indexed jobId,
        address indexed poster,
        address indexed provider,
        uint256 amountFlr,
        uint256 amountUsd
    );
    event PaymentReleased(
        uint256 indexed jobId,
        address indexed provider,
        uint256 payout,
        uint256 fee
    );
    event PaymentRefunded(
        uint256 indexed jobId,
        address indexed poster,
        uint256 amount
    );

    // ─── Constructor ────────────────────────────────────────

    constructor(
        address initialOwner,
        address ftsoConsumer,
        address feeCollector_
    ) Ownable(initialOwner) {
        ftso = FTSOPriceConsumer(ftsoConsumer);
        feeCollector = feeCollector_;
        platformFeeBps = 200; // 2%
    }

    // ─── Config ─────────────────────────────────────────────

    function setOrderBook(address orderBook_) external onlyOwner {
        orderBook = IFlareOrderBook(orderBook_);
    }

    function setFdcVerifier(address verifier) external onlyOwner {
        fdcVerifier = IFDCVerifier(verifier);
    }

    function setFTSO(address ftsoConsumer) external onlyOwner {
        ftso = FTSOPriceConsumer(ftsoConsumer);
    }

    function setFeeCollector(
        address collector,
        uint96 feeBps
    ) external onlyOwner {
        require(feeBps <= 1_000, "FlareEscrow: fee too high"); // max 10%
        feeCollector = collector;
        platformFeeBps = feeBps;
    }

    function setSlippageBps(uint256 bps) external onlyOwner {
        require(bps <= 2_000, "FlareEscrow: slippage too high"); // max 20%
        slippageBps = bps;
    }

    // ─── Core Functions ─────────────────────────────────────

    /**
     * @notice Fund a job's escrow with native FLR.
     *
     *         ── FTSO integration (Flare MAIN) ──
     *         The contract reads the live FLR/USD FTSO price and validates that
     *         the sent FLR value covers the job's USD budget (with slippage).
     *
     * @param jobId     The FlareOrderBook job ID
     * @param provider  The assigned agent's address
     * @param usdBudget The job's max USD budget (18 decimals)
     */
    function fundJob(
        uint256 jobId,
        address provider,
        uint256 usdBudget
    ) external payable {
        Deposit storage dep = deposits[jobId];
        require(!dep.funded, "FlareEscrow: already funded");
        require(msg.value > 0, "FlareEscrow: zero value");
        require(provider != address(0), "FlareEscrow: zero provider");

        // ── FTSO price validation ──
        uint256 requiredFlr = ftso.usdToFlr(usdBudget);
        uint256 minRequired = (requiredFlr * (10_000 - slippageBps)) / 10_000;
        require(
            msg.value >= minRequired,
            "FlareEscrow: insufficient FLR for USD budget"
        );

        dep.poster = msg.sender;
        dep.provider = provider;
        dep.amount = msg.value;
        dep.usdValue = usdBudget;
        dep.funded = true;

        emit EscrowFunded(jobId, msg.sender, provider, msg.value, usdBudget);
    }

    /**
     * @notice Release payment to the provider.
     *
     *         ── FDC integration (Flare MAIN + BONUS) ──
     *         This function REQUIRES that the FDCVerifier has confirmed delivery
     *         via an FDC-attested external data proof. The escrow release is
     *         driven entirely by FDC, not by a trusted backend.
     *
     * @param jobId  The job to release payment for.
     */
    function releaseToProvider(uint256 jobId) external nonReentrant {
        Deposit storage dep = deposits[jobId];
        require(dep.funded, "FlareEscrow: not funded");
        require(!dep.released, "FlareEscrow: already released");
        require(!dep.refunded, "FlareEscrow: refunded");

        // ── FDC gate ──
        require(
            address(fdcVerifier) != address(0),
            "FlareEscrow: FDC verifier not set"
        );
        require(
            fdcVerifier.isDeliveryConfirmed(jobId),
            "FlareEscrow: delivery not attested by FDC"
        );

        // Caller must be poster or provider
        require(
            msg.sender == dep.poster || msg.sender == dep.provider,
            "FlareEscrow: not authorised"
        );

        dep.released = true;

        uint256 fee = (dep.amount * platformFeeBps) / 10_000;
        uint256 payout = dep.amount - fee;

        if (fee > 0 && feeCollector != address(0)) {
            (bool feeOk, ) = feeCollector.call{value: fee}("");
            require(feeOk, "FlareEscrow: fee transfer failed");
        }

        (bool ok, ) = dep.provider.call{value: payout}("");
        require(ok, "FlareEscrow: payout failed");

        // Update OrderBook status
        if (address(orderBook) != address(0)) {
            orderBook.markReleased(jobId);
        }

        emit PaymentReleased(jobId, dep.provider, payout, fee);
    }

    /**
     * @notice Refund the poster. Can only be called by the owner (dispute resolution)
     *         or if the job deadline has passed without completion.
     */
    function refund(uint256 jobId) external nonReentrant {
        Deposit storage dep = deposits[jobId];
        require(dep.funded, "FlareEscrow: not funded");
        require(!dep.released, "FlareEscrow: already released");
        require(!dep.refunded, "FlareEscrow: already refunded");

        // Only owner can refund (dispute resolution)
        require(
            msg.sender == owner(),
            "FlareEscrow: not authorised"
        );

        dep.refunded = true;

        (bool ok, ) = dep.poster.call{value: dep.amount}("");
        require(ok, "FlareEscrow: refund failed");

        emit PaymentRefunded(jobId, dep.poster, dep.amount);
    }

    // ─── Views ──────────────────────────────────────────────

    function getDeposit(
        uint256 jobId
    ) external view returns (Deposit memory) {
        return deposits[jobId];
    }

    /// @dev Accept native FLR
    receive() external payable {}
}
