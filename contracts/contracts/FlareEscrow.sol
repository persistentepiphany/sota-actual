// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "./FTSOPriceConsumer.sol";
import "./interfaces/IAgentStaking.sol";

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
 * @notice Holds native FLR or ERC-20 stablecoins (Plasma-bridged USDC) for jobs.
 *         Validates funding against FTSO prices.
 *         Release is gated on FDC-attested delivery confirmation.
 *
 *         Key integrations:
 *         - FTSO: fundJob() validates that value ≥ FTSO-derived amount
 *         - FDC:  releaseToProvider() requires FDCVerifier.isDeliveryConfirmed()
 *         - Plasma: supports ERC-20 stablecoin deposits for secure payments
 *
 *         This satisfies Flare MAIN (FTSO + FDC), Flare BONUS (FDC-driven
 *         escrow release), and Plasma bonus (stablecoin transactions).
 */
contract FlareEscrow is Ownable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    // ─── Types ──────────────────────────────────────────────

    enum PaymentType { NATIVE_FLR, ERC20_STABLECOIN }

    struct Deposit {
        address poster;
        address provider;
        uint256 amount;         // amount locked (FLR wei or token base units)
        uint256 usdValue;       // USD equivalent at fund time (18 dec)
        PaymentType paymentType;
        address token;          // address(0) for native FLR, ERC-20 address for stablecoin
        bool funded;
        bool released;
        bool refunded;
    }

    // ─── State ──────────────────────────────────────────────

    mapping(uint256 => Deposit) public deposits;
    mapping(address => bool) public allowedStablecoins;  // Plasma-bridged USDC, etc.

    FTSOPriceConsumer public ftso;
    IFDCVerifier public fdcVerifier;
    IFlareOrderBook public orderBook;

    IAgentStaking public agentStaking;

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
        uint256 amount,
        uint256 amountUsd,
        PaymentType paymentType,
        address token
    );
    event PaymentReleased(
        uint256 indexed jobId,
        address indexed provider,
        uint256 payout,
        uint256 fee,
        PaymentType paymentType
    );
    event PaymentRefunded(
        uint256 indexed jobId,
        address indexed poster,
        uint256 amount,
        PaymentType paymentType
    );
    event StablecoinUpdated(address indexed token, bool allowed);

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

    function setAgentStaking(address staking) external onlyOwner {
        agentStaking = IAgentStaking(staking);
    }

    /**
     * @notice Whitelist or delist a stablecoin (e.g. Plasma-bridged USDC).
     */
    function setAllowedStablecoin(address token, bool allowed) external onlyOwner {
        require(token != address(0), "FlareEscrow: zero address");
        allowedStablecoins[token] = allowed;
        emit StablecoinUpdated(token, allowed);
    }

    // ─── Core Functions ─────────────────────────────────────

    /**
     * @notice Fund a job's escrow with native FLR.
     *
     *         ── FTSO integration (Flare MAIN) ──
     *         The contract reads the live FLR/USD FTSO price and validates that
     *         the sent FLR value covers the job's USD budget (with slippage).
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
        dep.paymentType = PaymentType.NATIVE_FLR;
        dep.token = address(0);
        dep.funded = true;

        emit EscrowFunded(jobId, msg.sender, provider, msg.value, usdBudget, PaymentType.NATIVE_FLR, address(0));
    }

    /**
     * @notice Fund a job's escrow with an ERC-20 stablecoin (Plasma-bridged USDC).
     *
     *         ── Plasma Bonus Track ──
     *         Supports secure stablecoin transactions via Plasma infrastructure.
     *         The token must be whitelisted via setAllowedStablecoin().
     *         Caller must approve this contract first.
     *
     * @param jobId       The FlareOrderBook job ID
     * @param provider    The assigned agent's address
     * @param token       The stablecoin token address (e.g. Plasma-bridged USDC)
     * @param amount      The token amount in base units (e.g. 50e6 for 50 USDC)
     * @param usdBudget   The USD value (18 decimals) for accounting
     */
    function fundJobWithStablecoin(
        uint256 jobId,
        address provider,
        address token,
        uint256 amount,
        uint256 usdBudget
    ) external {
        Deposit storage dep = deposits[jobId];
        require(!dep.funded, "FlareEscrow: already funded");
        require(amount > 0, "FlareEscrow: zero amount");
        require(provider != address(0), "FlareEscrow: zero provider");
        require(allowedStablecoins[token], "FlareEscrow: token not allowed");

        IERC20(token).safeTransferFrom(msg.sender, address(this), amount);

        dep.poster = msg.sender;
        dep.provider = provider;
        dep.amount = amount;
        dep.usdValue = usdBudget;
        dep.paymentType = PaymentType.ERC20_STABLECOIN;
        dep.token = token;
        dep.funded = true;

        emit EscrowFunded(jobId, msg.sender, provider, amount, usdBudget, PaymentType.ERC20_STABLECOIN, token);
    }

    /**
     * @notice Release payment to the provider.
     *
     *         ── FDC integration (Flare MAIN + BONUS) ──
     *         This function REQUIRES that the FDCVerifier has confirmed delivery
     *         via an FDC-attested external data proof. The escrow release is
     *         driven entirely by FDC, not by a trusted backend.
     *
     *         Supports both native FLR and ERC-20 stablecoin payouts.
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

        if (dep.paymentType == PaymentType.NATIVE_FLR) {
            if (fee > 0 && feeCollector != address(0)) {
                (bool feeOk, ) = feeCollector.call{value: fee}("");
                require(feeOk, "FlareEscrow: fee transfer failed");
            }
            // Route payout through AgentStaking if provider is staked
            if (
                address(agentStaking) != address(0) &&
                agentStaking.isStaked(dep.provider)
            ) {
                agentStaking.creditEarnings{value: payout}(dep.provider, payout);
            } else {
                (bool ok, ) = dep.provider.call{value: payout}("");
                require(ok, "FlareEscrow: payout failed");
            }
        } else {
            IERC20 token = IERC20(dep.token);
            if (fee > 0 && feeCollector != address(0)) {
                token.safeTransfer(feeCollector, fee);
            }
            token.safeTransfer(dep.provider, payout);
        }

        // Update OrderBook status
        if (address(orderBook) != address(0)) {
            orderBook.markReleased(jobId);
        }

        emit PaymentReleased(jobId, dep.provider, payout, fee, dep.paymentType);
    }

    /**
     * @notice Refund the poster. Can only be called by the owner (dispute resolution).
     *         Supports both native FLR and ERC-20 stablecoin refunds.
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

        if (dep.paymentType == PaymentType.NATIVE_FLR) {
            (bool ok, ) = dep.poster.call{value: dep.amount}("");
            require(ok, "FlareEscrow: refund failed");
        } else {
            IERC20(dep.token).safeTransfer(dep.poster, dep.amount);
        }

        emit PaymentRefunded(jobId, dep.poster, dep.amount, dep.paymentType);
    }

    // ─── Views ──────────────────────────────────────────────

    function getDeposit(
        uint256 jobId
    ) external view returns (Deposit memory) {
        return deposits[jobId];
    }

    function isStablecoinAllowed(address token) external view returns (bool) {
        return allowedStablecoins[token];
    }

    /// @dev Accept native FLR
    receive() external payable {}
}
