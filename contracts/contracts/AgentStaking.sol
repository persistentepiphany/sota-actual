// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "./interfaces/IRandomNumberV2.sol";
import "./AgentRegistry.sol";

/**
 * @title AgentStaking
 * @notice Devs stake FLR to activate their AI agent. Job earnings accumulate
 *         in the contract. On cash-out, Flare's RandomNumberV2 runs a 50/50
 *         gamble: win = 2x earnings, lose = 0 (earnings go to shared pool).
 *         The stake itself is never lost.
 *
 *         Flare integration: RandomNumberV2 at
 *         0x5CdF9eAF3EB8b44fB696984a1420B56A7575D250 (Coston2).
 */
contract AgentStaking is Ownable, ReentrancyGuard {
    // ─── Types ──────────────────────────────────────────────

    struct StakeInfo {
        uint256 stakedAmount;
        uint256 accumulatedEarnings;
        uint256 wins;
        uint256 losses;
        bool isStaked;
    }

    // ─── State ──────────────────────────────────────────────

    uint256 public minimumStake;
    uint256 public lossPool;
    uint256 public maxRandomAge; // max age of random number in seconds
    uint256 public houseFeeBps; // house cut in basis points (500 = 5%)

    mapping(address => StakeInfo) public stakes;

    IRandomNumberV2 public randomNumberV2;
    AgentRegistry public agentRegistry;
    address public escrow;
    address public houseWallet;

    // ─── Events ─────────────────────────────────────────────

    event Staked(address indexed agent, uint256 amount);
    event Unstaked(address indexed agent, uint256 amount, uint256 forfeitedEarnings);
    event EarningsCredited(address indexed agent, uint256 amount);
    event CashoutWin(address indexed agent, uint256 payout);
    event CashoutLoss(address indexed agent, uint256 lostEarnings);
    event MinimumStakeUpdated(uint256 newMinimum);
    event EscrowUpdated(address indexed escrow);
    event HouseWalletUpdated(address indexed wallet);
    event HouseFeeUpdated(uint256 newFeeBps);
    event HouseFeePaid(address indexed agent, uint256 amount);
    event PoolSeeded(address indexed from, uint256 amount);
    event PoolWithdrawn(address indexed to, uint256 amount);

    // ─── Modifiers ──────────────────────────────────────────

    modifier onlyEscrow() {
        require(msg.sender == escrow, "AgentStaking: caller is not escrow");
        _;
    }

    modifier onlyHouse() {
        require(msg.sender == houseWallet, "AgentStaking: not house wallet");
        _;
    }

    // ─── Constructor ────────────────────────────────────────

    constructor(
        address initialOwner,
        address agentRegistry_,
        address randomNumberV2_,
        uint256 minimumStake_
    ) Ownable(initialOwner) {
        agentRegistry = AgentRegistry(agentRegistry_);
        randomNumberV2 = IRandomNumberV2(randomNumberV2_);
        minimumStake = minimumStake_;
        maxRandomAge = 120; // 120 seconds default
        houseWallet = 0x76F9398Ee268b9fdc06C0dff402B20532922fFAE;
        houseFeeBps = 500; // 5%
    }

    // ─── Config ─────────────────────────────────────────────

    function setEscrow(address escrow_) external onlyOwner {
        escrow = escrow_;
        emit EscrowUpdated(escrow_);
    }

    function setMinimumStake(uint256 minimumStake_) external onlyOwner {
        minimumStake = minimumStake_;
        emit MinimumStakeUpdated(minimumStake_);
    }

    function setMaxRandomAge(uint256 maxAge) external onlyOwner {
        maxRandomAge = maxAge;
    }

    function setHouseWallet(address wallet) external onlyOwner {
        require(wallet != address(0), "AgentStaking: zero address");
        houseWallet = wallet;
        emit HouseWalletUpdated(wallet);
    }

    function setHouseFeeBps(uint256 feeBps) external onlyOwner {
        require(feeBps <= 2000, "AgentStaking: fee too high"); // max 20%
        houseFeeBps = feeBps;
        emit HouseFeeUpdated(feeBps);
    }

    // ─── House Pool Management ───────────────────────────────

    function seedPool() external payable onlyHouse {
        require(msg.value > 0, "AgentStaking: zero seed");
        lossPool += msg.value;
        emit PoolSeeded(msg.sender, msg.value);
    }

    function withdrawPool(uint256 amount) external onlyHouse nonReentrant {
        require(amount <= lossPool, "AgentStaking: exceeds pool");
        lossPool -= amount;
        (bool ok, ) = houseWallet.call{value: amount}("");
        require(ok, "AgentStaking: withdraw failed");
        emit PoolWithdrawn(houseWallet, amount);
    }

    // ─── Core Functions ─────────────────────────────────────

    /**
     * @notice Stake FLR to activate an agent. Requires the agent to be
     *         Active in AgentRegistry. Only the developer wallet can stake.
     */
    function stake(address agent) external payable {
        require(
            agentRegistry.getDeveloper(agent) == msg.sender,
            "AgentStaking: not developer"
        );
        require(msg.value >= minimumStake, "AgentStaking: below minimum stake");
        require(!stakes[agent].isStaked, "AgentStaking: already staked");
        require(
            agentRegistry.isAgentActive(agent),
            "AgentStaking: agent not active in registry"
        );

        stakes[agent] = StakeInfo({
            stakedAmount: msg.value,
            accumulatedEarnings: 0,
            wins: 0,
            losses: 0,
            isStaked: true
        });

        emit Staked(agent, msg.value);
    }

    /**
     * @notice Credit earnings to a staked agent. Called by FlareEscrow
     *         when a job's NATIVE_FLR payout is released.
     */
    function creditEarnings(address agent, uint256 amount) external payable onlyEscrow {
        require(msg.value == amount, "AgentStaking: value mismatch");
        require(stakes[agent].isStaked, "AgentStaking: agent not staked");

        stakes[agent].accumulatedEarnings += amount;

        emit EarningsCredited(agent, amount);
    }

    /**
     * @notice Cash out accumulated earnings with a 50/50 gamble.
     *         Uses Flare RandomNumberV2 to determine outcome.
     *         Win: receive min(2x earnings, earnings + pool).
     *         Lose: earnings go to the shared loss pool.
     *         Only the developer wallet can cash out. Payout goes to developer.
     */
    function cashout(address agent) external nonReentrant {
        require(
            agentRegistry.getDeveloper(agent) == msg.sender,
            "AgentStaking: not developer"
        );

        StakeInfo storage info = stakes[agent];
        require(info.isStaked, "AgentStaking: not staked");
        require(info.accumulatedEarnings > 0, "AgentStaking: no earnings");

        // Read random number from Flare
        (uint256 randomNumber, bool isSecure, uint256 randomTimestamp) =
            randomNumberV2.getRandomNumber();

        require(isSecure, "AgentStaking: random number not secure");
        require(
            block.timestamp - randomTimestamp <= maxRandomAge,
            "AgentStaking: random number too stale"
        );

        uint256 earnings = info.accumulatedEarnings;
        info.accumulatedEarnings = 0;

        // House fee: 5% of earnings on every cashout
        uint256 houseFee = (earnings * houseFeeBps) / 10000;
        uint256 netEarnings = earnings - houseFee;

        // Pay house fee
        if (houseFee > 0) {
            (bool feeOk, ) = houseWallet.call{value: houseFee}("");
            require(feeOk, "AgentStaking: house fee failed");
            emit HouseFeePaid(agent, houseFee);
        }

        if (randomNumber & 1 == 0) {
            // WIN — pay min(2x netEarnings, netEarnings + pool)
            uint256 bonus = netEarnings; // the extra 1x
            if (bonus > lossPool) {
                bonus = lossPool;
            }
            lossPool -= bonus;
            uint256 payout = netEarnings + bonus;

            info.wins++;

            (bool ok, ) = msg.sender.call{value: payout}("");
            require(ok, "AgentStaking: payout failed");

            emit CashoutWin(agent, payout);
        } else {
            // LOSE — net earnings go to pool
            lossPool += netEarnings;
            info.losses++;

            emit CashoutLoss(agent, netEarnings);
        }
    }

    /**
     * @notice Unstake and reclaim the staked FLR. Agent must NOT be Active
     *         in AgentRegistry. Uncashed earnings are forfeited to the pool.
     *         Only the developer wallet can unstake. Stake returned to developer.
     */
    function unstake(address agent) external nonReentrant {
        require(
            agentRegistry.getDeveloper(agent) == msg.sender,
            "AgentStaking: not developer"
        );

        StakeInfo storage info = stakes[agent];
        require(info.isStaked, "AgentStaking: not staked");
        require(
            !agentRegistry.isAgentActive(agent),
            "AgentStaking: agent still active"
        );

        uint256 stakeAmount = info.stakedAmount;
        uint256 forfeited = info.accumulatedEarnings;

        // Forfeit uncashed earnings to the pool
        lossPool += forfeited;

        // Clear stake
        info.stakedAmount = 0;
        info.accumulatedEarnings = 0;
        info.isStaked = false;

        (bool ok, ) = msg.sender.call{value: stakeAmount}("");
        require(ok, "AgentStaking: unstake transfer failed");

        emit Unstaked(agent, stakeAmount, forfeited);
    }

    // ─── Views ──────────────────────────────────────────────

    function getStakeInfo(address agent) external view returns (StakeInfo memory) {
        return stakes[agent];
    }

    function isStaked(address agent) external view returns (bool) {
        return stakes[agent].isStaked;
    }

    function getPoolSize() external view returns (uint256) {
        return lossPool;
    }

    /**
     * @notice Preview what a cashout would yield (without executing).
     *         Returns the max possible payout (if win) and current earnings.
     */
    function previewCashout(address agent) external view returns (
        uint256 earnings,
        uint256 houseFee,
        uint256 maxPayout
    ) {
        earnings = stakes[agent].accumulatedEarnings;
        houseFee = (earnings * houseFeeBps) / 10000;
        uint256 net = earnings - houseFee;
        uint256 bonus = net;
        if (bonus > lossPool) {
            bonus = lossPool;
        }
        maxPayout = net + bonus;
    }

    /// @dev Accept native FLR (for pool funding, etc.)
    receive() external payable {}
}
