import enum

from . import abi


class Contract(enum.Enum):
    GNT = enum.auto()
    GNTB = enum.auto()
    GNTDeposit = enum.auto()
    Faucet = enum.auto()


GNT = Contract.GNT
GNTB = Contract.GNTB
GNTDeposit = Contract.GNTDeposit
Faucet = Contract.Faucet


_abi = {
    GNT: abi.GNT,
    GNTB: abi.GNTB,
    GNTDeposit: abi.GNTDeposit,
    Faucet: abi.Faucet,
}


def get_abi(contract: Contract):
    return _abi[contract]
