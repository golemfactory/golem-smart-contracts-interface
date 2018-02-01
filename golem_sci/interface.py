from typing import Callable, Optional, List
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
        return '<BatchTransferEvent tx: {} sender: {} amount: {} '\
            'closure_time: {}>'.format(
                self.tx_hash,
                self.sender,
                self.amount / denoms.ether,
                self.closure_time,
            )


class SmartContractsInterface(object, metaclass=abc.ABCMeta):
    """
    All addresses are in the form of 0x[0-9a-zA-Z]
    ETH and GNT values are in wei, i.e. 10^18 wei = 1 ETH/GNT
    All transaction methods return transaction hash
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
    def get_incoming_batch_tranfers(
            self,
            payer_address: str,
            payee_address: str,
            from_block: int,
            to_block: int) -> List[BatchTransferEvent]:
        pass

    @abc.abstractmethod
    def subscribe_to_incoming_batch_transfers(
            self,
            address: str,
            from_block: int,
            cb: Callable[[BatchTransferEvent], None],
            required_confs: int) -> None:
        """
        Every time a BatchTransfer event happens callback will be called
        if the recipient equals to the input address and the block has been
        confirmed required number of times.
        """
        pass

    ################
    # Transactions #
    ################

    @abc.abstractmethod
    def batch_transfer(self, payments, closure_time: int) -> str:
        pass

    ############################
    # Concent specific methods #
    ############################

    @abc.abstractmethod
    def get_deposit_value(
            self,
            account_address: str) -> Optional[int]:
        """
        Returns deposit value or None.
        """
        pass

    @abc.abstractmethod
    def get_deposit_locked_until(
            self,
            account_address: str) -> Optional[int]:
        """
        Returns deposit locked_until value which is a Unix epoch timestamp in
        seconds. or None in case of issues.
        """
        pass

    ########################
    # Concent transactions #
    ########################

    @abc.abstractmethod
    def force_subtask_payment(
            self,
            requestor_address: str,
            provider_address: str,
            value: int,
            subtask_id: str) -> str:
        pass

    @abc.abstractmethod
    def force_batch_payment(
            self,
            requestor_address: str,
            provider_address: str,
            value: int,
            closure_time: int) -> str:
        pass

    @abc.abstractmethod
    def cover_additional_verification_cost(
            self,
            client_address: str,
            value: int,
            subtask_id: str) -> str:
        pass
