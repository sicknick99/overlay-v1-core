
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.2;

import "../libraries/PositionV2.sol";

import "@openzeppelin/contracts/token/ERC1155/ERC1155.sol";

import "../interfaces/IOverlayV1Market.sol";
import "../interfaces/IOverlayV1Factory.sol";
import "../interfaces/IOverlayToken.sol";

contract OverlayV1OVLCollateral is ERC1155 {

    using PositionV2 for PositionV2.Info;

    // TODO: do we have a struct for markets?
    struct Market { uint _marginAdjustment; }

    // mapping from position (erc1155) id to total shares issued of position
    mapping(uint256 => uint256) public totalPositionShares;

    mapping (address => uint) marginAdjustments;
    mapping (address => bool) supportedMarket;
    mapping (address => mapping(uint => uint)) internal queuedPositionLongs;
    mapping (address => mapping(uint => uint)) internal queuedPositionShorts;
    PositionV2.Info[] public positions;

    uint16 public constant MIN_COLLAT = 10**4;
    uint constant RESOLUTION = 1e4;

    uint nextPositionId;

    IOverlayToken public ovl;
    IOverlayV1Factory public factory;

    uint256 public fees;
    uint256 public liquidations;

    event Build(uint256 positionId, uint256 oi, uint256 debt);
    event Unwind(uint256 positionId, uint256 oi, uint256 debt);
    event Liquidate(address rewarded, uint256 reward);
    event Update(
        address rewarded, 
        uint rewardAmount, 
        uint feesCollected, 
        uint feesBurned, 
        uint liquidationsCollected, 
        uint liquidationsBurned 
    );
    constructor (
        string memory _uri,
        address _ovl
    ) ERC1155(_uri) { 

        ovl = IOverlayToken(_ovl);

    }

    function addMarket (
        address _market,
        uint _marginAdjustment
    ) external {

        marginAdjustments[_market] = _marginAdjustment;

    }

    /// @notice Updates funding payments, cumulative fees, queued position builds, and price points
    function update(
        address _market,
        address _rewardsTo
    ) public {

        if (IOverlayV1Market(_market).update()) {

            (   uint256 _marginBurnRate,
                uint256 _feeBurnRate,
                uint256 _feeRewardsRate,
                address _feeTo ) = factory.getUpdateParams();

            uint _feeForward = fees;
            uint _feeBurn = ( _feeForward * _feeBurnRate ) / RESOLUTION;
            uint _feeReward = ( _feeForward * _feeRewardsRate ) / RESOLUTION;
            _feeForward = _feeForward - _feeBurn - _feeReward;

            uint _liqForward = liquidations;
            uint _liqBurn = ( _liqForward * _marginBurnRate ) / RESOLUTION;
            _liqForward -= _liqBurn;

            emit Update(
                _rewardsTo,
                _feeReward,
                _feeForward,
                _feeBurn,
                _liqForward,
                _liqBurn
            );

            ovl.burn(address(this), _feeBurn + _liqBurn);
            ovl.transfer(_feeTo, _feeForward + _liqForward);
            ovl.transfer(_rewardsTo, _feeReward);


        }

    }

    function getQueuedPositionId (
        address _market,
        bool _isLong,
        uint _leverage,
        uint _pricePointCurrent
    ) internal returns (uint positionId_) {

        mapping(uint=>uint) storage _queuedPositions = _isLong 
            ? queuedPositionLongs[_market]
            : queuedPositionShorts[_market];

        positionId_ = _queuedPositions[_leverage];

        PositionV2.Info storage position = positions[positionId_];

        if (position.pricePoint < _pricePointCurrent) {

            positions.push(PositionV2.Info({
                market: _market,
                isLong: _isLong,
                leverage: _leverage,
                pricePoint: _pricePointCurrent,
                oiShares: 0,
                debt: 0,
                cost: 0
            }));

            positionId_ = positions.length;

            _queuedPositions[_leverage] = positionId_;

        }

    }

    function build(
        address _market,
        uint256 _collateral,
        bool _isLong,
        uint256 _leverage,
        address _rewardsTo
    ) external {

        (   uint _freeOi,
            uint _maxLev,
            uint _pricePointCurrent ) = IOverlayV1Market(_market).entryData(_isLong);

        require(_leverage <= _maxLev, "OVLV1:max<lev");
        require(_collateral < MIN_COLLAT, "OVLV1:collat<min");

        uint _positionId = getQueuedPositionId(
            _market, 
            _isLong, 
            _leverage, 
            _pricePointCurrent
        );

        PositionV2.Info storage position = positions[_positionId];

        uint _oiAdjusted;

        {
        uint _oi = _collateral * _leverage;
        uint _fee = ( _oi * factory.fee() ) / RESOLUTION;
        _oiAdjusted = _oi - _fee;
        uint _collateralAdjusted = _oiAdjusted / _leverage;
        uint _debtAdjusted = _oiAdjusted - _collateralAdjusted;

        fees += _fee;

        position.oiShares += _oiAdjusted;
        position.debt += _debtAdjusted;
        position.cost += _collateralAdjusted;

        }

        IOverlayV1Market(_market).enterOI(_isLong, _oiAdjusted);
        ovl.transferFrom(msg.sender, address(this), _collateral);
        mint(msg.sender, _positionId, _oiAdjusted, ""); // WARNING: last b/c erc1155 callback

        }

    /// @notice Unwinds shares of an existing position
    function unwind(
        uint256 _positionId,
        uint256 _shares
    ) external {

        require( 0 < _shares && _shares <= balanceOf(msg.sender, _positionId), "OVLV1:!shares");

        {

        PositionV2.Info storage pos = positions[_positionId];

        bool _isLong = pos.isLong;

        (   uint _oi,
            uint _oiShares,
            uint _priceFrame ) = IOverlayV1Market(pos.market).exitData(_isLong, pos.pricePoint);
        
        uint _totalPosShares = totalPositionShares[_positionId];

        uint _userOiShares = _shares * pos.oiShares / _totalPosShares;
        uint _userNotional = _shares * pos.notional(_priceFrame, _oi, _oiShares) / _totalPosShares;
        uint _userDebt = _shares * pos.debt / _totalPosShares;
        uint _userCost = _shares * pos.cost / _totalPosShares;
        uint _userOi = _shares * pos.openInterest(_oi, _oiShares) / _totalPosShares;

        // TODO: think through edge case of underwater position ... and fee adjustments ...
        uint _feeAmount = ( _userNotional * factory.fee() ) / RESOLUTION;

        uint _userValueAdjusted = _userNotional - _feeAmount;
        if (_userValueAdjusted > _userDebt) _userValueAdjusted -= _userDebt;
        else _userValueAdjusted = 0;

        fees += _feeAmount; // adds to fee pot, which is transferred on update

        // TODO: compare gas expenditure
        pos.debt -= _userDebt;
        pos.cost -= _userCost;
        pos.oiShares -= _userOiShares;
        // TODO: compare gas expenditure
        // positions[_positionId].debt -= _userDebt;
        // positions[_positionId].cost -= _userCost;
        // positions[_positionId].oiShares -= _userOiShares;

        emit Unwind(_positionId, _userOi, _userDebt);

        // mint/burn excess PnL = valueAdjusted - cost, accounting for need to also burn debt
        if (_userCost < _userValueAdjusted) ovl.mint(address(this), _userValueAdjusted - _userCost);
        else ovl.burn(address(this), _userCost - _userValueAdjusted);
        ovl.transfer(msg.sender, _userValueAdjusted);
        IOverlayV1Market(pos.market).exitOI(_isLong, _userOi, _userOiShares);

        }

        burn(msg.sender, _positionId, _shares);
 
    }

    /// @notice Liquidates an existing position
    function liquidate(
        uint256 _positionId,
        address _rewardsTo
    ) external {

        PositionV2.Info storage pos = positions[_positionId];

        bool _isLong = pos.isLong;

        (   uint _oi,
            uint _oiShares,
            uint _priceFrame ) = IOverlayV1Market(pos.market).exitData(_isLong, pos.pricePoint);

        (   uint _marginMaintenance,
            uint _marginRewardRate   ) = factory.getMarginParams();

        require(pos.isLiquidatable(
            _priceFrame,
            _oi,
            _oiShares,
            _marginMaintenance
        ), "OverlayV1: position not liquidatable");

        _oi -= pos.openInterest(_oi, _oiShares);
        _oiShares -= pos.oiShares;

        IOverlayV1Market(pos.market).exitOI(_isLong, _oi, _oiShares);

        // TODO: which is better on gas
        pos.oiShares = 0;
        // positions[positionId].oiShares = 0;

        uint _toForward = pos.cost;
        uint _toReward = ( _toForward * _marginRewardRate ) / RESOLUTION;

        liquidations += _toForward - _toReward;

        ovl.transfer(_rewardsTo, _toReward);

    }


    /// @notice Mint overrides erc1155 _mint to track total shares issued for given position id
    function mint(address account, uint256 id, uint256 shares, bytes memory data) internal {
        totalPositionShares[id] += shares;
        _mint(account, id, shares, data);
    }

    /// @notice Burn overrides erc1155 _burn to track total shares issued for given position id
    function burn(address account, uint256 id, uint256 shares) internal {
        uint256 totalShares = totalPositionShares[id];
        require(totalShares >= shares, "OVLV1: burn shares exceeds total");
        totalPositionShares[id] = totalShares - shares;
        _burn(account, id, shares);
    }


}