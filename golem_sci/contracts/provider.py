from golem_sci.contracts import data
from .data.rinkeby import (
    golemnetworktoken,
    golemnetworktokenbatching,
    faucet,
    gntdeposit,
    gntpaymentchannels,
)


class ContractDataProvider:
    def __init__(self, chain: str) -> None:
        self._chain = chain

    def get_address(self, contract: str) -> str:
        return self._get_module(contract).ADDRESS

    def get_abi(self, contract: str) -> str:
        return self._get_module(contract).ABI

    def _get_module(self, contract: str):
        return getattr(getattr(data, self._chain), contract.lower())
