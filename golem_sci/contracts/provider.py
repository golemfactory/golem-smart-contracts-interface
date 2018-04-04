from golem_sci.contracts import data
# Without these imports the `getattr` below don't work
from .data.rinkeby import (
    golemnetworktoken,
    golemnetworktokenbatching,
    faucet,
    gntdeposit,
    gntpaymentchannels,
)
from .data.mainnet import (
    golemnetworktoken,
    golemnetworktokenbatching,
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
