// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title IAgentStaking
 * @notice Minimal interface so FlareEscrow can interact with staking
 *         without circular imports.
 */
interface IAgentStaking {
    function isStaked(address agent) external view returns (bool);
    function creditEarnings(address agent, uint256 amount) external payable;
}
