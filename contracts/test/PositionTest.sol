// SPDX-License-Identifier: MIT
pragma solidity ^0.8.2;

import "../libraries/FixedPoint.sol";
import "../libraries/Position.sol";

contract PositionTest {
    using FixedPoint for FixedPoint.uq112x112;
    using FixedPoint for FixedPoint.uq144x112;
    using Position for Position.Info;

    Position.Info[] public positions;

    function push(
        bool _isLong,
        uint256 _leverage,
        uint256 _oiShares,
        uint256 _debt,
        uint256 _cost
    ) public {
        positions.push(Position.Info({
            isLong: _isLong,
            leverage: _leverage,
            oiShares: _oiShares,
            debt: _debt,
            cost: _cost
        }));
    }

    function len() public view returns (uint256) {
        return positions.length;
    }

    function value(
        uint256 positionId,
        uint256 totalOi,
        uint256 totalOiShares,
        uint256 priceEntry,
        uint256 priceExit
    ) external view returns (uint256) {
        Position.Info storage position = positions[positionId];
        return position.value(totalOi, totalOiShares, priceEntry, priceExit);
    }

    function isUnderwater(
        uint256 positionId,
        uint256 totalOi,
        uint256 totalOiShares,
        uint256 priceEntry,
        uint256 priceExit
    ) external view returns (bool) {
        Position.Info storage position = positions[positionId];
        return position.isUnderwater(totalOi, totalOiShares, priceEntry, priceExit);
    }

    function notional(
        uint256 positionId,
        uint256 totalOi,
        uint256 totalOiShares,
        uint256 priceEntry,
        uint256 priceExit
    ) external view returns (uint256) {
        Position.Info storage position = positions[positionId];
        return position.notional(totalOi, totalOiShares, priceEntry, priceExit);
    }

    function openLeverage(
        uint256 positionId,
        uint256 totalOi,
        uint256 totalOiShares,
        uint256 priceEntry,
        uint256 priceExit
    ) external view returns (FixedPoint.uq144x112 memory) {
        Position.Info storage position = positions[positionId];
        return position.openLeverage(totalOi, totalOiShares, priceEntry, priceExit);
    }

    function openMargin(
        uint256 positionId,
        uint256 totalOi,
        uint256 totalOiShares,
        uint256 priceEntry,
        uint256 priceExit
    ) external view returns (FixedPoint.uq144x112 memory) {
        Position.Info storage position = positions[positionId];
        return position.openMargin(totalOi, totalOiShares, priceEntry, priceExit);
    }

    function isLiquidatable(
        uint256 positionId,
        uint256 totalOi,
        uint256 totalOiShares,
        uint256 priceEntry,
        uint256 priceExit,
        uint16 maintenanceFactor,
        uint16 marginResolution
    ) external view returns (bool) {
        Position.Info storage position = positions[positionId];
        return position.isLiquidatable(
            totalOi,
            totalOiShares,
            priceEntry,
            priceExit,
            maintenanceFactor,
            marginResolution
        );
    }
}