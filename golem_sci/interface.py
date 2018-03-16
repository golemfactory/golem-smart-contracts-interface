from typing import Any, Callable, Dict, Optional, List
import abc

from .events import (
    BatchTransferEvent,
    ForcedPaymentEvent,
    ForcedSubtaskPaymentEvent,
    CoverAdditionalVerificationEvent,
)


class TransactionReceipt:
    def __init__(self, raw_receipt: Dict[str, Any]):
        self.tx_hash = raw_receipt['transactionHash']
        self.status = raw_receipt['status'] == 1
        self.block_hash = raw_receipt['blockHash']
        self.block_number = raw_receipt['blockNumber']
        self.gas_used = raw_receipt['gasUsed']


class SmartContractsInterface(object, metaclass=abc.ABCMeta):
    """
    All addresses are in the form of 0x[0-9a-zA-Z]
    ETH and GNT values are in wei, i.e. 10^18 wei = 1 ETH/GNT
    All transaction methods return transaction hash
    """

    @abc.abstractmethod
    def get_eth_address(self) -> str:
        """
        Return associated with this instance Ethereum address
        """
        pass

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
    def get_gntb_balance(self, address: str) -> Optional[int]:
        """
        Returns GNTB balance in wei or None is case of issues.
        """
        pass

    @abc.abstractmethod
    def get_transaction_receipt(
            self,
            tx_hash: str) -> Optional[TransactionReceipt]:
        """
        Returns transaction receipt or None if it hasn't been mined yet.
        """
        pass

    @abc.abstractmethod
    def get_batch_transfers(
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

    @abc.abstractmethod
    def on_transaction_confirmed(
            self,
            tx_hash: str,
            required_confs: int,
            cb: Callable[[TransactionReceipt], None]) -> None:
        """
        Will invoke callback after the transaction has been confirmed
        required number of times.
        """
        pass

    # Transaction
    @abc.abstractmethod
    def transfer_eth(self, to_address: str, amount: int) -> str:
        pass

    # Transaction
    @abc.abstractmethod
    def transfer_gnt(self, to_address: str, amount: int) -> str:
        pass

    # Transaction
    @abc.abstractmethod
    def transfer_gntb(self, to_address: str, amount: int) -> str:
        pass

    # Transaction
    @abc.abstractmethod
    def transfer_gntb_and_call(
            self,
            to_address: str,
            amount: int,
            data: bytes) -> str:
        pass

    # Transaction
    @abc.abstractmethod
    def batch_transfer(self, payments, closure_time: int) -> str:
        pass

    ########################
    # GNT-GNTB conversions #
    ########################

    # Transaction
    @abc.abstractmethod
    def open_gate(self) -> str:
        pass

    @abc.abstractmethod
    def get_gate_address(self) -> str:
        """
        Returns Ethereum address
        """
        pass

    # Transaction
    @abc.abstractmethod
    def transfer_from_gate(self) -> str:
        """
        Final step which convert the value of the gate to GNTB
        """
        pass

    # Transaction
    @abc.abstractmethod
    def convert_gntb_to_gnt(self, amount: int) -> str:
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

    # Transaction
    @abc.abstractmethod
    def deposit_payment(self, value: int) -> str:
        pass

    # Transaction
    @abc.abstractmethod
    def unlock_deposit(self) -> str:
        pass

    # Transaction
    @abc.abstractmethod
    def withdraw_deposit(self) -> str:
        pass

    # Transaction
    @abc.abstractmethod
    def force_subtask_payment(
            self,
            requestor_address: str,
            provider_address: str,
            value: int,
            subtask_id: str) -> str:
        pass

    @abc.abstractmethod
    def get_forced_subtask_payments(
            self,
            requestor_address: str,
            provider_address: str,
            from_block: int,
            to_block: int) -> List[ForcedSubtaskPaymentEvent]:
        pass

    # Transaction
    @abc.abstractmethod
    def force_payment(
            self,
            requestor_address: str,
            provider_address: str,
            value: int,
            closure_time: int) -> str:
        pass

    @abc.abstractmethod
    def get_forced_payments(
            self,
            requestor_address: str,
            provider_address: str,
            from_block: int,
            to_block: int) -> List[ForcedPaymentEvent]:
        pass

    # Transaction
    @abc.abstractmethod
    def cover_additional_verification_cost(
            self,
            client_address: str,
            value: int,
            subtask_id: str) -> str:
        pass

    @abc.abstractmethod
    def get_covered_additional_verification_costs(
            self,
            address: str,
            from_block: int,
            to_block: int) -> List[CoverAdditionalVerificationEvent]:
        pass
