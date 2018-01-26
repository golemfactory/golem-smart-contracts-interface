from typing import Optional
import abc

from ethereum.utils import denoms


class BatchTransferEvent:
    def __init__(
            self,
            tx_hash: str,
            sender: str,
            amount: int,
            closure_time: int):
        self.tx_hash = tx_hash
        self.sender = sender
        self.amount = amount
        self.closure_time = closure_time

    def __str__(self) -> str:
        return 'tx: {} sender: {} amount: {} closure_time: {}'.format(
            self.tx_hash,
            self.sender,
            self.amount / denoms.ether,
            self.closure_time,
        )


class SmartContractsInterface(object, metaclass=abc.ABCMeta):
    """
    All addresses are in the form of 0x[0-9a-zA-Z]
    """

    @abc.abstractmethod
    def get_eth_balance(self, address: str) -> Optional[int]:
        """
        Returns eth balance in wei or None is case of issues.
        """
        pass

    @abc.abstractmethod
    def get_gnt_balance(self, address: str) -> Optional[int]:
        """
        Returns GNT balance in wei or None is case of issues.
        """
        pass

    @abc.abstractmethod
    def get_gntw_balance(self, address: str) -> Optional[int]:
        """
        Returns GNTW balance in wei or None is case of issues.
        """
        pass

    @abc.abstractmethod
    def subscribe_to_incoming_batch_transfers(
            self,
            address: str,
            cb: callable(BatchTransferEvent),
            required_confs: int) -> None:
        """
        Every time a BatchTransfer event happens callback will be called
        if the recipient equals to the input address and the block has been
        confirmed required number of times.
        """
        pass
