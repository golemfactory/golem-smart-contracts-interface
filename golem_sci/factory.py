from typing import Callable

from ethereum.transactions import Transaction
from web3 import Web3, IPCProvider, HTTPProvider

from .client import Client
from .implementation import SCIImplementation
from .interface import SmartContractsInterface

CHAIN_MAINNET = 'mainnet'
CHAIN_RINKEBY = 'rinkeby'

GENESES = {
    CHAIN_MAINNET:
        '0xd4e56740f876aef8c010b86a40d5f56745a118d0906a34e69aec8c0db1cb8fa3',
    CHAIN_RINKEBY:
        '0x6341fd3daf94b748c72ced5a5b26028f2474f5f00d824504e4fa37a75767e177',
}


def new_sci_ipc(
        ipc: str,
        address: str,
        tx_sign: Callable[[Transaction], None]=None,
        chain: str=CHAIN_RINKEBY) -> SmartContractsInterface:
    return new_sci(Web3(IPCProvider(ipc)), address, tx_sign, chain)


def new_sci_rpc(
        rpc: str,
        address: str,
        tx_sign: Callable[[Transaction], None]=None,
        chain: str=CHAIN_RINKEBY) -> SmartContractsInterface:
    return new_sci(Web3(HTTPProvider(rpc)), address, tx_sign, chain)


def new_sci(
        web3: Web3,
        address: str,
        tx_sign: Callable[[Transaction], None]=None,
        chain: str=CHAIN_RINKEBY) -> SmartContractsInterface:
    if chain != CHAIN_RINKEBY:
        raise Exception('Unsupported chain {}'.format(chain))
    _ensure_genesis(web3, chain)
    return SCIImplementation(Client(web3), address, tx_sign)


def _ensure_genesis(web3: Web3, chain: str):
    genesis_hash = web3.eth.getBlock(0)['hash']
    if genesis_hash != GENESES[chain]:
        raise Exception(
            'Invalid genesis block for {}, expected {}, got {}'.format(
                chain,
                GENESES[chain],
                genesis_hash,
            )
        )
