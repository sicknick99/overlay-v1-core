from re import I
import requests
from pytest import approx
import json
import os
from os import environ
from pathlib import Path  # Python 3.6+ only
from brownie.convert import to_address
from dotenv import load_dotenv

subgraph = "http://localhost:8000/subgraphs/name/overlay-market/overlay-v1"

alice = "0x256F5ff57469492BC3bF5Ea7A70Daa565737dc68"
bob = "0xdA44bf38D3969931Ad844cB8813423311E68A5c1"

global ALICE
global BOB
global MOTHERSHIP
global MARKET
global OVL_COLLATERAL

load_dotenv("./subgraph.test.env")

def query(gql):

    return json.loads(requests.post(subgraph, json={'query': gql}).text)['data']

def test_alice_and_bob_exist():

    gql = """
        query {
            accounts {
                id
            }
        }
    """

    result = query(gql)

    accounts = [ to_address(x['id']) for x in result['accounts'] ]

    assert alice in accounts, "Alice is not in returned accounts"
    assert bob in accounts, "Bob is not in returned accounts"


def test_alice_and_bob_have_zero_position_one_shares():

    global ALICE
    global BOB

    gql = """
        query {
            accounts {
                id
                balances {
                    id
                    account {
                        id
                        address
                    }
                    position
                    shares
                }
            }
        }
    """

    result = query(gql)

    accounts = result['accounts']

    position_one = { 
        to_address(balance['account']['address']):balance['shares'] 
        for sublist in [ x['balances'] for x in accounts if 0 < len(x['balances'])]
        for balance in sublist 
        if balance['position'] == '1' 
    }

    assert position_one[BOB] == environ.get('BOB_POSITION_ONE'), 'bobs position one shares are not zero'
    assert position_one[ALICE] == environ.get('ALICE_POSITION_ONE'), 'alices position one shares are not zero'

    position_two = { 
        to_address(balance['account']['address']):balance['shares'] 
        for sublist in [ x['balances'] for x in accounts if 0 < len(x['balances'])]
        for balance in sublist 
        if balance['position'] == '2' 
    }

    assert BOB not in position_two, 'bob has no position two shares'

    assert position_two[ALICE] == environ.get('ALICE_POSITION_TWO')
    

def set_env():

    env_path = Path('.') / '.subgraph.test.env'
    load_dotenv(dotenv_path=env_path)

    global MOTHERSHIP 
    global MARKET
    global OVL_COLLATERAL
    global ALICE
    global BOB
    global GOV
    global FEE_TO 

    MOTHERSHIP = to_address(environ.get("MOTHERSHIP"))
    MARKET = to_address(environ.get("MARKET"))
    OVL_COLLATERAL = to_address(environ.get("OVL_COLLATERAL"))
    ALICE = to_address(environ.get("ALICE"))
    BOB = to_address(environ.get("BOB"))
    GOV = to_address(environ.get("GOV"))
    FEE_TO = to_address(environ.get("FEE_TO"))


if __name__ == "__main__":

    set_env()

    test_alice_and_bob_exist()

    test_alice_and_bob_have_zero_position_one_shares()