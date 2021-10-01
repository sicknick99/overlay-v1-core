import brownie
from brownie.test import given, strategy
from hypothesis import settings, strategies
from brownie import chain
from pytest import approx
from decimal import *
import random

OI_CAP = 800000e18
MIN_COLLATERAL=1e14
FEE_RESOLUTION=1e18

def print_logs(tx):
    for i in range(len(tx.events['log'])):
        print(tx.events['log'][i]['k'] + ": " + str(tx.events['log'][i]['v']))

def get_collateral(collateral, leverage, fee):
    FL = fee*leverage
    fee_offset = MIN_COLLATERAL*(FL/(FEE_RESOLUTION - FL))
    if collateral - fee_offset <= MIN_COLLATERAL:
        return int(MIN_COLLATERAL + fee_offset)
    else:
        return int(collateral)


def test_unwind(ovl_collateral, token, bob):
    pass


def test_unwind_revert_insufficient_shares(ovl_collateral, bob):
    
    EXPECTED_ERROR_MESSAGE = "OVLV1:!shares"
    with brownie.reverts(EXPECTED_ERROR_MESSAGE):
        ovl_collateral.unwind(
            1,
            1e18,
            {"from": bob}
        );


@given(
    is_long=strategy('bool'),
    oi=strategy('uint256', min_value=1, max_value=OI_CAP/1e16),
    leverage=strategy('uint256', min_value=1, max_value=100))
def test_unwind_oi_removed(
        ovl_collateral,
        mothership,
        market,
        token,
        bob,
        alice,
        oi,
        leverage,
        is_long
        ):
    
    # Build parameters
    oi *= 1e16
    collateral = get_collateral(oi / leverage, leverage, mothership.fee())

    # Build
    token.approve(ovl_collateral, collateral, {"from": bob})
    tx_build = ovl_collateral.build(
        market,
        collateral,
        leverage,
        is_long,
        {"from": bob}
    )

    # Position info
    pid = tx_build.events['Build']['positionId']
    poi_build = tx_build.events['Build']['oi']

    (_, _, _, price_point, oi_shares_build,
        debt_build, cost_build, p_compounding) = ovl_collateral.positions(pid)

    chain.mine(timedelta=market.updatePeriod()+1)

    assert oi_shares_build > 0
    assert poi_build > 0
    
    # Unwind
    tx_unwind = ovl_collateral.unwind(
        pid,
        oi_shares_build,
        {"from": bob}
    )

    (_, _, _, _, oi_shares_unwind, debt_unwind, cost_unwind, _) =\
        ovl_collateral.positions(pid)

    poi_unwind = tx_unwind.events['Unwind']['oi']

    assert oi_shares_unwind == 0
    assert int(poi_unwind) == approx(int(poi_build))


# WIP
@given(
    is_long=strategy('bool'),
    oi=strategy('uint256', min_value=1, max_value=OI_CAP/1e16),
    leverage=strategy('uint256', min_value=1, max_value=100),
    time_delta=strategies.floats(min_value=0.1, max_value=1),
)
@settings(max_examples=10)
def test_unwind_expected_fee(
    ovl_collateral,
    mothership,
    market,
    token,
    bob,
    oi,
    leverage,
    is_long,
    feed_infos,
    time_delta
):

    mine_ix = int(( len(feed_infos.price_times) - 1 ) * time_delta)

    mine_time = feed_infos.price_times[mine_ix]['time']

    oi *= 1e16

    collateral = get_collateral(oi / leverage, leverage, mothership.fee())

    token.approve(ovl_collateral, collateral, {"from": bob})

    tx_build = ovl_collateral.build(
        market,
        collateral,
        leverage,
        is_long,
        {"from": bob}
    )

    price_cap = market.priceFrameCap() / 1e18

    fees_prior = ovl_collateral.fees() / 1e18

    # Position info
    pid = tx_build.events['Build']['positionId']
    pos_shares = tx_build.events['Build']['oi']
    (_, _, _, price_point, oi_shares_pos, debt_pos, _, p_compounding) = ovl_collateral.positions(pid)

    bob_balance = ovl_collateral.balanceOf(bob, pid)

    chain.mine(timestamp=mine_time+1)

    ( oi, oi_shares, price_frame ) = market.positionInfo(is_long, price_point, p_compounding)

    tx_unwind = ovl_collateral.unwind(
        pid,
        bob_balance,
        {"from": bob}
    )

    price_entry = market.pricePoints(market.pricePointCurrentIndex()-2)
    entry_bid = price_entry[0]
    entry_ask = price_entry[1]

    price_exit = market.pricePoints(market.pricePointCurrentIndex()-1)
    exit_bid = price_exit[0]
    exit_ask = price_exit[1]

    price_frame = min(exit_bid / entry_ask, price_cap) if is_long else exit_ask / entry_bid

    oi /= 1e18
    debt_pos /= 1e18
    oi_shares /= 1e18
    oi_shares_pos /= 1e18

    # Fee calculation
    pos_oi = ( oi_shares_pos * oi ) / oi_shares 

    if is_long:
        val = pos_oi * price_frame 
        val = val - min(val, debt_pos)
    else:
        val = pos_oi *2
        val = val - min(val, debt_pos + pos_oi * price_frame )

    notional = val + debt_pos 

    fee = notional * ( mothership.fee() / 1e18 )

    # Unwind

    (_, _, _, _, oi_shares_unwind, debt_unwind, cost_unwind, _) =\
        ovl_collateral.positions(pid)

    fees_now = ovl_collateral.fees() / 1e18

    assert fee + fees_prior == approx(fees_now), "fees not expected amount"


@given(
    is_long=strategy('bool'),
    bob_oi=strategy('uint256', min_value=1, max_value=OI_CAP/1e16),
    alice_oi=strategy('uint256', min_value=1, max_value=OI_CAP/1e16),
    leverage=strategy('uint256', min_value=1, max_value=100))
@settings(max_examples = 3)
def test_partial_unwind(
  ovl_collateral,
  mothership,
  market,
  token,
  bob,
  alice,
  bob_oi,
  alice_oi,
  leverage,
  is_long
):
    # Build parameters
    bob_oi *= 1e16
    alice_oi *= 1e16
    bob_collateral = get_collateral(bob_oi / leverage, leverage, mothership.fee())
    alice_collateral = get_collateral(alice_oi / leverage, leverage, mothership.fee())

    print('bob balance: ', bob.balance())
    print('alice balance: ', alice.balance())
    print('bob_collateral: ', bob_collateral)
    print('alice_collateral: ', alice_collateral)

    # Alice and Bob both builds a position
    token.approve(ovl_collateral, bob_collateral, {"from": bob})
    token.approve(ovl_collateral, alice_collateral, {"from": alice})

    bob_tx_build = ovl_collateral.build(
        market,
        bob_collateral,
        leverage,
        is_long,
        {"from": bob}
    )

    alice_tx_build = ovl_collateral.build(
        market,
        alice_collateral,
        leverage,
        is_long,
        {"from": alice}
    )

    # Position info
    bob_pid = bob_tx_build.events['Build']['positionId']
    bob_poi_build = bob_tx_build.events['Build']['oi']

    alice_pid = alice_tx_build.events['Build']['positionId']
    alice_poi_build = alice_tx_build.events['Build']['oi']

    (_, _, _, price_point, bob_oi_shares_build,
        bob_debt_build, bob_cost_build, bob_p_compounding) = ovl_collateral.positions(bob_pid)

    (_, _, _, price_point, alice_oi_shares_build,
        alice_debt_build, alice_cost_build, alice_p_compounding) = ovl_collateral.positions(alice_pid)

    chain.mine(timedelta=market.updatePeriod()+1)

    # Confirm that Bob and Alice both hold a position
    assert bob_oi_shares_build > 0
    assert bob_poi_build > 0

    assert alice_oi_shares_build > 0
    assert alice_poi_build > 0

    # Unwind half of OI
    unwind_collateral = bob_collateral / 2
    print('ovl_collateral.positions before unwind: ', ovl_collateral.positions(bob_pid))
    ovl_collateral.unwind(bob_pid, unwind_collateral, {"from": bob})
    print('ovl_collateral.positions after unwind: ', ovl_collateral.positions(bob_pid))

    # Confirm Bob still hold a position after partial unwind
    assert bob_oi_shares_build > 0
    assert bob_poi_build > 0

    assert alice_oi_shares_build > 0
    assert alice_poi_build > 0

    # Bob should contain proper amounts of OI remaining

    pass


@given(
    is_long=strategy('bool'),
    bob_oi=strategy('uint256', min_value=1, max_value=OI_CAP/1e16),
    alice_oi=strategy('uint256', min_value=2, max_value=OI_CAP/1e16),
    leverage=strategy('uint256', min_value=1, max_value=100))
@settings(max_examples = 3)
def test_partial_unwind1(
  ovl_collateral,
  mothership,
  market,
  token,
  bob,
  alice,
  alice_oi,
  bob_oi,
  leverage,
  is_long
):
    # Build parameters
    bob_oi *= 1e16
    alice_oi *= 1e16

    bob_collateral = get_collateral(bob_oi / leverage, leverage, mothership.fee())
    alice_collateral = get_collateral(alice_oi / leverage, leverage, mothership.fee())

    # Alice and Bob both builds a position
    token.approve(ovl_collateral, bob_collateral, {"from": bob})
    token.approve(ovl_collateral, alice_collateral, {"from": alice})
    
    bob_tx_build = ovl_collateral.build(
        market,
        bob_collateral,
        leverage,
        is_long,
        {"from": bob}
    )

    alice_tx_build = ovl_collateral.build(
      market,
      alice_collateral,
      leverage,
      is_long,
      {"from": alice}
    )

    # Position info
    bob_pid = bob_tx_build.events['Build']['positionId']
    bob_poi_build = bob_tx_build.events['Build']['oi']

    (_, _, _, price_point, bob_oi_shares_build,
        bob_debt_build, bob_cost_build, bob_p_compounding) = ovl_collateral.positions(bob_pid)

    chain.mine(timedelta=market.updatePeriod()+1)

    # Confirm that Bob and Alice both hold a position
    assert bob_oi_shares_build > 0
    assert bob_poi_build > 0

    # Unwind half of OI
    unwind_collateral = bob_collateral / 2
    print('ovl_collateral.positions before unwind: ', ovl_collateral.positions(bob_pid))
    ovl_collateral.unwind(bob_pid, unwind_collateral, {"from": bob})
    print('ovl_collateral.positions after unwind: ', ovl_collateral.positions(bob_pid))

    # Confirm Bob still hold a position after partial unwind
    assert bob_oi_shares_build > 0
    assert bob_poi_build > 0


    # Bob should contain proper amounts of OI remaining

    pass

@given(
    is_long=strategy('bool'),
    oi=strategy('uint256', min_value=1, max_value=OI_CAP/1e16),
    leverage=strategy('uint256', min_value=1, max_value=100))
def test_unwind_after_transfer(
        ovl_collateral,
        mothership,
        market,
        token,
        bob,
        alice,
        oi,
        leverage,
        is_long
        ):
    
    # Build parameters
    oi *= 1e16
    collateral = get_collateral(oi / leverage, leverage, mothership.fee())

    # Bob builds a position
    token.approve(ovl_collateral, collateral, {"from": bob})
    tx_build = ovl_collateral.build(
        market,
        collateral,
        leverage,
        is_long,
        {"from": bob}
    )

    # Position info
    pid = tx_build.events['Build']['positionId']
    poi_build = tx_build.events['Build']['oi']
    
    (_, _, _, price_point, oi_shares_build,
        debt_build, cost_build, p_compounding) = ovl_collateral.positions(pid)

    chain.mine(timedelta=market.updatePeriod()+1)

    # Confirm that Bob holds a position
    assert oi_shares_build > 0
    assert poi_build > 0

    # Transfer Bob's position to Alice
    ovl_collateral.safeTransferFrom(bob, alice, pid, ovl_collateral.totalSupply(pid), 1, {"from": bob})
    
    # Bob's unwind attempt should fail
    EXPECTED_ERROR_MESSAGE = "OVLV1:!shares"
    with brownie.reverts(EXPECTED_ERROR_MESSAGE):
        ovl_collateral.unwind(
            pid,
            oi_shares_build,
            {"from": bob}
        )


# WIP
# warning, dependent on what the price/mocks do
@given(collateral=strategy('uint256'))
def test_unwind_revert_position_was_liquidated(
        ovl_collateral,
        mothership,
        market,
        collateral,
        token,
        bob,
        alice):

    collateral = 2e18
    leverage = 1
    is_long = True

    # token.approve(ovl_collateral, collateral, {"from": bob})
    # tx_build = ovl_collateral.build(
    #     market,
    #     collateral,
    #     leverage,
    #     is_long,
    #     {"from": bob}
    # )

    # with brownie.reverts("OVLV1:!shares"):
    #     ovl_collateral.unwind(
    #         1,
    #         1e18,
    #         { "from": bob }
    #     );

    # build a position
    # liquidate a position
    # try to unwind it and get a revert

    pass

@given(
    is_long=strategy('bool'),
    oi=strategy('uint256', min_value=1, max_value=OI_CAP/1e16),
    leverage=strategy('uint256', min_value=1, max_value=100))
def test_unwind_from_queued_oi (
    ovl_collateral, 
    bob,
    token,
    mothership,
    oi,
    leverage,
    market,
    is_long
):
    ''' 
    When compounding period is larger than update period we unwind before 
    compounding period is done and expect the oi to be removed from the 
    queued oi instead of the non queued oi.
    '''

    oi *= 1e16

    collateral = get_collateral(oi / leverage, leverage, mothership.fee())

    is_long = True

    update_period = market.updatePeriod()

    tx = ovl_collateral.build(market, collateral, leverage, is_long, { 'from': bob })

    pos_id = tx.events['Build']['positionId']
    pos_oi = tx.events['Build']['oi']

    pos_shares = ovl_collateral.balanceOf(bob, pos_id)

    chain.mine(timedelta=update_period+1)

    q_oi_after_update_period = market.queuedOiLong() if is_long else market.queuedOiShort()

    tx = ovl_collateral.unwind(pos_id, pos_oi, { 'from': bob })

    q_oi_after_unwind = market.queuedOiLong() if is_long else market.queuedOiShort()

    assert q_oi_after_update_period == pos_shares
    assert approx(q_oi_after_unwind/1e18) == 0


@given(
    oi=strategy('uint256', min_value=1, max_value=OI_CAP/1e16),
    leverage=strategy('uint256', min_value=1, max_value=100),
    is_long=strategy('bool'))
def test_unwind_from_active_oi(
        ovl_collateral,
        market,
        token,
        mothership,
        bob,
        oi,
        leverage,
        is_long
):
    '''
    We want to unwind from the queued oi so we only mine the chain to the next
    update period, not further into the compounding period. Then we unwind and 
    verify that the queued oi at zero.
    '''

    oi *= 1e16

    collateral = get_collateral(oi/leverage, leverage, mothership.fee())

    # Build
    token.approve(ovl_collateral, collateral, {"from": bob})
    tx_build = ovl_collateral.build(
        market,
        collateral,
        leverage,
        is_long,
        {"from": bob}
    )

    # Position info
    pid = tx_build.events['Build']['positionId']
    build_oi = tx_build.events['Build']['oi']
    pshares = ovl_collateral.balanceOf(bob, pid)

    queued_oi_before = market.queuedOiLong() if is_long else market.queuedOiShort()

    chain.mine(timedelta=market.compoundingPeriod()+1)

    market.update({'from': bob})

    queued_oi_after = market.queuedOiLong() if is_long else market.queuedOiShort()

    assert queued_oi_before == build_oi
    assert queued_oi_after == 0

    oi_before_unwind = market.oiLong() if is_long else market.oiShort()

    tx = ovl_collateral.unwind(pid, pshares, { 'from': bob })

    oi_after_unwind = market.oiLong() if is_long else market.oiShort()

    assert oi_before_unwind == build_oi
    assert oi_after_unwind == 0 or 1

@given(thing=strategy('uint'))
@settings(max_examples=1)
def test_comptroller_recorded_mint_or_burn (
    ovl_collateral, 
    token, 
    market, 
    bob,
    thing
):
    '''
    When we unwind we want to see that the comptroller included however much 
    was minted or burnt from the payout from unwinding the position into its
    brrrrd storage variable.
    '''

    update_period = market.updatePeriod()

    token.approve(ovl_collateral, 1e50, { 'from': bob })

    # when we unwind, seeing if there was a mint/burn, 
    # and see if the brrrrd variable has recorded it
    tx = ovl_collateral.build(
        market,
        1e18,
        1,
        True,
        { 'from': bob }
    )

    pos_id = tx.events['Build']['positionId']
    bobs_shares = tx.events['Build']['oi']

    chain.mine(timedelta=update_period*2)

    tx = ovl_collateral.unwind(
        pos_id,
        bobs_shares, 
        { "from": bob }
    )

    burnt = 0
    minted = 0
    for _, v in enumerate(tx.events['Transfer']):
        if v['to'] == '0x0000000000000000000000000000000000000000':
            burnt = v['value']
        elif v['from'] == '0x0000000000000000000000000000000000000000':
            minted = v['value']

    brrrrd = market.brrrrd()

    if burnt > 0:
        assert brrrrd == -burnt
    else:
        assert minted == brrrrd