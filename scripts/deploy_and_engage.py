from brownie import *
from brownie import interface
from brownie import \
    UniswapV3FactoryMock, \
    chain, \
    accounts
import os
import json

TOKEN_DECIMALS = 18
TOKEN_TOTAL_SUPPLY = 8000000e18
OI_CAP = 800000
AMOUNT_IN = 1
PRICE_POINTS_START = 50
PRICE_POINTS_END = 100

PRICE_WINDOW_MACRO = 3600
PRICE_WINDOW_MICRO = 600

UPDATE_PERIOD = 100
COMPOUND_PERIOD = 600

IMPACT_WINDOW = 600

LAMBDA = .6e18
STATIC_CAP = 370400e18
BRRRR_EXPECTED = 26320e18
BRRRR_WINDOW_MACRO = 2592000
BRRRR_WINDOW_MICRO = 86400


DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
AXS = "0xBB0E17EF65F82Ab018d8EDd776e8DD940327B28b"
USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"

FEED_OWNER = accounts[6]


def deploy_uni_factory():

    uniswapv3_factory = FEED_OWNER.deploy(UniswapV3FactoryMock)

    return uniswapv3_factory


def main():

    uni_factory = deploy_uni_factory()
