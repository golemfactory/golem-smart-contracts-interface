from typing import Optional
import abc


class SmartContractInterface(object, metaclass=abc.ABCMeta):
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
