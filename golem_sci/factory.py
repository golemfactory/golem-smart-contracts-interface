from typing import Callable

from ethereum.transactions import Transaction

from .client import Client
from .implementation import SCIImplementation
from .interface import SmartContractsInterface
from .token import GNTWToken


def new_testnet(
        web3,
        address: str,
        tx_sign: Callable[[Transaction], None]) -> SmartContractsInterface:
    geth_client = Client(web3)
    token = GNTWToken(geth_client)
    return SCIImplementation(geth_client, token, address, tx_sign)
