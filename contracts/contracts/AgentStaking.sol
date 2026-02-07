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

    mapping(address => StakeInfo) public stakes;

    IRandomNumberV2 public randomNumberV2;
    AgentRegistry public agentRegistry;
    address public escrow;

    // ─── Events ─────────────────────────────────────────────

    event Staked(address indexed agent, uint256 amount);
    event Unstaked(address indexed agent, uint256 amount, uint256 forfeitedEarnings);
    event EarningsCredited(address indexed agent, uint256 amount);
    event CashoutWin(address indexed agent, uint256 payout);
    event CashoutLoss(address indexed agent, uint256 lostEarnings);
    event MinimumStakeUpdated(uint256 newMinimum);
    event EscrowUpdated(address indexed escrow);

    // ─── Modifiers ──────────────────────────────────────────

    modifier onlyEscrow() {
        require(msg.sender == escrow, "AgentStaking: caller is not escrow");
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

    // ─── Core Functions ─────────────────────────────────────

    /**
     * @notice Stake FLR to activate an agent. Requires the agent to be
     *         Active in AgentRegistry.
     */
    function stake() external payable {
        require(msg.value >= minimumStake, "AgentStaking: below minimum stake");
        require(!stakes[msg.sender].isStaked, "AgentStaking: already staked");
        require(
            agentRegistry.isAgentActive(msg.sender),
            "AgentStaking: agent not active in registry"
        );

        stakes[msg.sender] = StakeInfo({
            stakedAmount: msg.value,
            accumulatedEarnings: 0,
            wins: 0,
            losses: 0,
            isStaked: true
        });

        emit Staked(msg.sender, msg.value);
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
     */
    function cashout() external nonReentrant {
        StakeInfo storage info = stakes[msg.sender];
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

        if (randomNumber & 1 == 0) {
            // WIN — pay min(2x earnings, earnings + pool)
            uint256 bonus = earnings; // the extra 1x
            if (bonus > lossPool) {
                bonus = lossPool;
            }
            lossPool -= bonus;
            uint256 payout = earnings + bonus;

            info.wins++;

            (bool ok, ) = msg.sender.call{value: payout}("");
            require(ok, "AgentStaking: payout failed");

            emit CashoutWin(msg.sender, payout);
        } else {
            // LOSE — earnings go to pool
            lossPool += earnings;
            info.losses++;

            emit CashoutLoss(msg.sender, earnings);
        }
    }

    /**
     * @notice Unstake and reclaim the staked FLR. Agent must NOT be Active
     *         in AgentRegistry. Uncashed earnings are forfeited to the pool.
     */
    function unstake() external nonReentrant {
        StakeInfo storage info = stakes[msg.sender];
        require(info.isStaked, "AgentStaking: not staked");
        require(
            !agentRegistry.isAgentActive(msg.sender),
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

        emit Unstaked(msg.sender, stakeAmount, forfeited);
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
        uint256 maxPayout
    ) {
        earnings = stakes[agent].accumulatedEarnings;
        uint256 bonus = earnings;
        if (bonus > lossPool) {
            bonus = lossPool;
        }
        maxPayout = earnings + bonus;
    }

    /// @dev Accept native FLR (for pool funding, etc.)
    receive() external payable {}
}
