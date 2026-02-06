// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title IFdcHub
 * @notice Minimal interface for the Flare Data Connector hub.
 *         Used to request attestations for off-chain/cross-chain data.
 */
interface IFdcHub {
    function requestAttestation(bytes calldata data) external payable returns (bytes32);
}
