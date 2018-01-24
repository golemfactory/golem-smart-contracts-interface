from .implementation import SCIImplementation
from .interface import SmartContractsInterface


def new_testnet(web3) -> SmartContractsInterface:
    return SCIImplementation(web3)
