import importlib


class ContractDataProvider:
    def __init__(self, chain: str) -> None:
        self._chain = chain

    def get_address(self, contract: str) -> str:
        return self._get_module(contract).ADDRESS

    def get_abi(self, contract: str) -> str:
        return self._get_module(contract).ABI

    def _get_module(self, contract: str):
        return importlib.import_module('golem_sci.contracts.data.{}.{}'.format(
            self._chain,
            contract.lower(),
        ))
