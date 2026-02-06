// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title IFlareContractRegistry
 * @notice Minimal interface for Flare's on-chain contract registry.
 *         On Coston2/Flare mainnet, deployed at a well-known address.
 */
interface IFlareContractRegistry {
    function getContractAddressByName(string calldata name) external view returns (address);
}
