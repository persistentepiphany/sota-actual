// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";
import "./interfaces/IFastUpdater.sol";
import "./interfaces/IFlareContractRegistry.sol";

/**
 * @title FTSOPriceConsumer
 * @notice Wraps Flare's FTSO v2 Fast Updates to provide FLR/USD pricing.
 *         Used by FlareOrderBook and FlareEscrow to convert between USD and FLR.
 *
 *         On Coston2 the FlareContractRegistry lives at
 *         0xaD67FE66660Fb8dFE9d6b1b4240d8650e30F6019
 */
contract FTSOPriceConsumer is Ownable {
    /// @dev Well-known Flare Contract Registry address (same on Coston2 & mainnet)
    address public constant FLARE_CONTRACT_REGISTRY =
        0xaD67FE66660Fb8dFE9d6b1b4240d8650e30F6019;

    /// @dev Feed index for FLR/USD on Flare FTSO v2
    uint256 public constant FLR_USD_FEED_INDEX = 0;

    /// @dev Staleness threshold — reject prices older than this (seconds)
    uint256 public maxStaleness = 300; // 5 minutes

    /// @dev Cached FastUpdater address (resolved from registry)
    IFastUpdater public fastUpdater;

    event FastUpdaterSet(address indexed updater);
    event MaxStalenessUpdated(uint256 newStaleness);

    constructor(address initialOwner) Ownable(initialOwner) {
        // Try to resolve FastUpdater from the on-chain registry
        _resolveFastUpdater();
    }

    // ─── Configuration ──────────────────────────────────────

    /// @notice Re-resolve the FastUpdater address from Flare's contract registry
    function resolveFastUpdater() external onlyOwner {
        _resolveFastUpdater();
    }

    /// @notice Manually set FastUpdater (for local testing / non-Flare chains)
    function setFastUpdater(address updater) external onlyOwner {
        fastUpdater = IFastUpdater(updater);
        emit FastUpdaterSet(updater);
    }

    function setMaxStaleness(uint256 seconds_) external onlyOwner {
        maxStaleness = seconds_;
        emit MaxStalenessUpdated(seconds_);
    }

    // ─── Price Queries ──────────────────────────────────────

    /**
     * @notice Get the current FLR/USD price.
     * @return priceWei   The price of 1 FLR in USD, scaled to 18 decimals.
     * @return timestamp  When the price was last updated.
     */
    function getFlrUsdPrice()
        public
        view
        returns (uint256 priceWei, int64 timestamp)
    {
        require(address(fastUpdater) != address(0), "FTSO: updater not set");

        uint256[] memory indexes = new uint256[](1);
        indexes[0] = FLR_USD_FEED_INDEX;

        (
            uint256[] memory feeds,
            int8[] memory decimals,
            int64 ts
        ) = fastUpdater.fetchCurrentFeeds(indexes);

        require(feeds.length > 0, "FTSO: no feed data");
        require(
            block.timestamp - uint256(uint64(ts)) <= maxStaleness,
            "FTSO: price stale"
        );

        // Normalise to 18 decimals
        priceWei = _normalise(feeds[0], decimals[0]);
        timestamp = ts;
    }

    /**
     * @notice Convert a USD amount (18-decimal) to FLR (18-decimal wei).
     * @param usdAmount  USD value scaled to 18 decimals (e.g. 10 USD = 10e18)
     * @return flrAmount The equivalent amount of FLR in wei.
     */
    function usdToFlr(uint256 usdAmount)
        external
        view
        returns (uint256 flrAmount)
    {
        (uint256 priceWei, ) = getFlrUsdPrice();
        require(priceWei > 0, "FTSO: price is zero");
        // FLR = USD / (FLR per USD price)
        flrAmount = (usdAmount * 1e18) / priceWei;
    }

    /**
     * @notice Convert a FLR amount (wei) to USD (18-decimal).
     * @param flrAmount  FLR in wei
     * @return usdAmount USD value scaled to 18 decimals.
     */
    function flrToUsd(uint256 flrAmount)
        external
        view
        returns (uint256 usdAmount)
    {
        (uint256 priceWei, ) = getFlrUsdPrice();
        usdAmount = (flrAmount * priceWei) / 1e18;
    }

    // ─── Internals ──────────────────────────────────────────

    function _resolveFastUpdater() internal {
        // On non-Flare chains (local Hardhat), the registry won't exist
        if (FLARE_CONTRACT_REGISTRY.code.length == 0) return;

        address updater = IFlareContractRegistry(FLARE_CONTRACT_REGISTRY)
            .getContractAddressByName("FastUpdater");

        if (updater != address(0)) {
            fastUpdater = IFastUpdater(updater);
            emit FastUpdaterSet(updater);
        }
    }

    /**
     * @dev Normalise a feed value with its decimals to 18-decimal precision.
     */
    function _normalise(
        uint256 value,
        int8 feedDecimals
    ) internal pure returns (uint256) {
        if (feedDecimals >= 0) {
            uint8 d = uint8(int8(18) - feedDecimals);
            return value * (10 ** d);
        } else {
            uint8 d = uint8(int8(18) + feedDecimals); // feedDecimals is negative
            return value / (10 ** d);
        }
    }
}
