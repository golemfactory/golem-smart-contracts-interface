from .client import Client
from .implementation import SCIImplementation
from .interface import SmartContractsInterface
from .token import GNTWToken


def new_testnet(web3) -> SmartContractsInterface:
    geth_client = Client(web3)
    token = GNTWToken(geth_client)
    return SCIImplementation(geth_client, token)
