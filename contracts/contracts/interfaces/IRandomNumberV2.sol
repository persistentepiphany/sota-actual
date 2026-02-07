// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title IRandomNumberV2
 * @notice Interface for Flare's RandomNumberV2 protocol contract.
 *         Provides a secure random number updated every ~90 seconds.
 *         Coston2 address: 0x5CdF9eAF3EB8b44fB696984a1420B56A7575D250
 */
interface IRandomNumberV2 {
    /**
     * @notice Get the current random number.
     * @return _randomNumber    The random number
     * @return _isSecureRandom  Whether the random number is secure
     * @return _randomTimestamp The timestamp when the random number was generated
     */
    function getRandomNumber()
        external
        view
        returns (
            uint256 _randomNumber,
            bool _isSecureRandom,
            uint256 _randomTimestamp
        );
}
