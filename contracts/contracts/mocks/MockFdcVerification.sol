// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../interfaces/IFdcVerification.sol";

/**
 * @title MockFdcVerification
 * @notice Mock FDC verifier for local Hardhat testing.
 *         Always returns true for verifyJsonApi().
 */
contract MockFdcVerification is IFdcVerification {
    bool public shouldPass = true;

    function setShouldPass(bool pass) external {
        shouldPass = pass;
    }

    function verifyJsonApi(
        IJsonApi.Proof calldata /* proof */
    ) external view override returns (bool) {
        return shouldPass;
    }
}
