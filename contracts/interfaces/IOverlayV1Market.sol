// SPDX-License-Identifier: MIT
pragma solidity ^0.8.7;

import "@openzeppelin/contracts/token/ERC1155/IERC1155.sol";
import "../libraries/Position.sol";

interface IOverlayV1Market is IERC1155 {

    event NewPrice(uint price);
    event FundingPaid(uint oiLong, uint oiShort, int fundingPaid);
    event log(string k, uint v);

    function ovl() external view returns (address);
    function factory() external view returns (address);

    function feed() external view returns (address);
    function windowSize() external view returns (uint256);
    function updatePeriod() external view returns (uint256);
    function updated() external view returns (uint256);
    function update() external returns (bool);
    function toUpdate() external view returns (uint256);
    function compounded() external view returns (uint256);
    function leverageMax() external view returns (uint8);
    function fundingKNumerator() external view returns (uint256);
    function fundingKDenominator() external view returns (uint256);

    function queuedOiLong() external view returns (uint256);
    function queuedOiShort() external view returns (uint256);
    function oi() external view returns (uint256, uint256);
    function oiLong() external view returns (uint256);
    function oiShort() external view returns (uint256);
    function oiLongShares() external view returns (uint256);
    function oiShortShares() external view returns (uint256);
    function oiCap() external view returns (uint256);

    function lmbda() external view returns (uint256);

    function epochs(
        uint _time,
        uint _from,
        uint _between
    ) external view returns (
        uint updatesThen_,
        uint updatesNow_,
        uint tUpdate_,
        uint t1Update_,
        uint compoundings_,
        uint tCompounding_,
        uint t1Compounding_
    );

    function pricePointCurrentIndex() external view returns (uint256);
    function pricePoints(uint256 index) external view returns (uint256 price );

    function MAX_FUNDING_COMPOUND() external view returns (uint16);

    function addCollateral (
        address _collateral
    ) external;

    function adjustParams (
        uint256 _updatePeriod,
        uint256 _compoundingPeriod,
        uint144 _oiCap,
        uint112 _fundingKNumerator,
        uint112 _fundingKDenominator,
        uint8 _leverageMax
    ) external;

    function enterOI (
        bool _isLong,
        uint _collateral,
        uint _leverage
    ) external returns (
        uint oiAdjusted_,
        uint collateralAdjusted_,
        uint debtAdjusted_,
        uint fee_,
        uint impact_,
        uint pricePointCurrent_,
        uint t1Compounding_
    );

    function exitData (
        bool _isLong,
        uint256 _pricePoint
    ) external returns (
        uint oi_,
        uint oiShares_,
        uint priceFrame_,
        uint tCompounding_
    );

    function exitOI (
        bool _compounded,
        bool _isLong,
        uint _oi,
        uint _oiShares,
        uint _brrrr,
        uint _antibrrrr
    ) external;

    function priceFrame(
        bool _isLong,
        uint _entryIndex
    ) external view returns (
        uint priceFrame_
    );


}
