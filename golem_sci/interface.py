from typing import Optional
import abc

from .implementation import SCIImplementation


class SmartContractsInterface(object, metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def get_eth_balance(self, address: str) -> Optional[int]:
        """
        Returns eth balance in wei or None is case of issues.
        @param address in the form of 0x[0-9a-zA-Z]{40}
        """
        pass

    @abc.abstractmethod
    def get_gnt_balance(self, address: str) -> Optional[int]:
        """
        Returns GNT balance in wei or None is case of issues.
        @param address in the form of 0x[0-9a-zA-Z]{40}
        """
        pass

    @abc.abstractmethod
    def get_gntw_balance(self, address: str) -> Optional[int]:
        """
        Returns GNTW balance in wei or None is case of issues.
        @param address in the form of 0x[0-9a-zA-Z]{40}
        """
        pass


def new_testnet(web3) -> SmartContractsInterface:
    return SCIImplementation(web3)
