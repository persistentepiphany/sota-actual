// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../interfaces/IFastUpdater.sol";

/**
 * @title MockFastUpdater
 * @notice Mock FTSO v2 FastUpdater for local Hardhat testing.
 *         Allows setting arbitrary FLR/USD prices.
 */
contract MockFastUpdater is IFastUpdater {
    /// @dev feedIndex => price value
    mapping(uint256 => uint256) private _prices;
    /// @dev feedIndex => decimals
    mapping(uint256 => int8) private _decimals;

    /**
     * @notice Set a mock price for a feed index.
     * @param feedIndex  The FTSO feed index (0 = FLR/USD)
     * @param price      The price value
     * @param decimals_  The number of decimals
     */
    function setPrice(
        uint256 feedIndex,
        uint256 price,
        int8 decimals_
    ) external {
        _prices[feedIndex] = price;
        _decimals[feedIndex] = decimals_;
    }

    function fetchCurrentFeeds(
        uint256[] calldata _feedIndexes
    )
        external
        view
        override
        returns (
            uint256[] memory feeds,
            int8[] memory decimals,
            int64 timestamp
        )
    {
        feeds = new uint256[](_feedIndexes.length);
        decimals = new int8[](_feedIndexes.length);

        for (uint256 i = 0; i < _feedIndexes.length; i++) {
            feeds[i] = _prices[_feedIndexes[i]];
            decimals[i] = _decimals[_feedIndexes[i]];
        }

        timestamp = int64(int256(block.timestamp));
    }
}
