// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title MockRandomNumberV2
 * @notice Mock for Flare's RandomNumberV2 — lets the test owner control
 *         the returned random number, security flag, and timestamp.
 */
contract MockRandomNumberV2 is Ownable {
    uint256 private _randomNumber;
    bool private _isSecureRandom;
    uint256 private _randomTimestamp;

    constructor() Ownable(msg.sender) {
        _randomNumber = 42;
        _isSecureRandom = true;
        _randomTimestamp = block.timestamp;
    }

    function setRandomNumber(
        uint256 randomNumber_,
        bool isSecureRandom_,
        uint256 randomTimestamp_
    ) external onlyOwner {
        _randomNumber = randomNumber_;
        _isSecureRandom = isSecureRandom_;
        _randomTimestamp = randomTimestamp_;
    }

    function getRandomNumber()
        external
        view
        returns (
            uint256,
            bool,
            uint256
        )
    {
        return (_randomNumber, _isSecureRandom, _randomTimestamp);
    }
}
