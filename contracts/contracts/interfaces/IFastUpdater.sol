// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title IFastUpdater
 * @notice Minimal interface for Flare's Fast Updates (FTSO v2 Scaling) price feeds.
 *         Provides sub-second price updates on Flare.
 */
interface IFastUpdater {
    /**
     * @notice Fetch current feed values by feed index array.
     * @param _feedIndexes Array of feed indexes (e.g. 0 = FLR/USD, 2 = BTC/USD, …)
     * @return _feeds       The current feed values (scaled integers)
     * @return _decimals    The number of decimals for each feed
     * @return _timestamp   Block timestamp of the update
     */
    function fetchCurrentFeeds(
        uint256[] calldata _feedIndexes
    )
        external
        view
        returns (
            uint256[] memory _feeds,
            int8[] memory _decimals,
            int64 _timestamp
        );
}
