from typing import Callable, Optional, List
import abc

from .events import (
    BatchTransferEvent,
    GntTransferEvent,
    ForcedPaymentEvent,
    ForcedSubtaskPaymentEvent,
    CoverAdditionalVerificationEvent,
)
from .structs import (
    Block,
    DirectEthTransfer,
    Payment,
    TransactionReceipt,
)


class SmartContractsInterface(object, metaclass=abc.ABCMeta):
    """
    All addresses are in the form of 0x[0-9a-zA-Z]
    ETH and GNT values are in wei, i.e. 10^18 wei = 1 ETH/GNT
    All transaction methods return transaction hash
    """

    @abc.abstractmethod
    def stop(self) -> None:
        pass

    @abc.abstractmethod
    def get_eth_address(self) -> str:
        """
        Return associated with this instance Ethereum address
        """
        pass

    @abc.abstractmethod
    def get_eth_balance(self, address: str) -> int:
        """
        Returns eth balance in wei.
        """
        pass

    @abc.abstractmethod
    def get_gnt_balance(self, address: str) -> int:
        """
        Returns GNT balance in wei.
        """
        pass

    @abc.abstractmethod
    def get_gntb_balance(self, address: str) -> int:
        """
        Returns GNTB balance in wei.
        """
        pass

    @abc.abstractmethod
    def get_transaction_receipt(
            self,
            tx_hash: str) -> Optional[TransactionReceipt]:
        """
        Returns transaction receipt or None if it hasn't been confirmed yet.
        """
        pass

    @abc.abstractmethod
    def get_transaction_gas_price(
            self,
            tx_hash: str) -> Optional[int]:
        pass

    @abc.abstractmethod
    def get_current_gas_price(self) -> int:
        """
        Returns current gas price that would be used for sending
        a transaction at this moment.
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
    def subscribe_to_batch_transfers(
            self,
            payer_address: Optional[str],
            payee_address: Optional[str],
            from_block: int,
            cb: Callable[[BatchTransferEvent], None]) -> None:
        """
        For all incoming batch transfers provide just the payee address,
        for outgoing just the payer address. Can also provide both to subscribe
        to batch transfers between particular pair of addresses.
        """
        pass

    @abc.abstractmethod
    def on_transaction_confirmed(
            self,
            tx_hash: str,
            cb: Callable[[TransactionReceipt], None]) -> None:
        """
        Will invoke callback after the transaction has been confirmed
        required number of times.
        """
        pass

    @abc.abstractmethod
    def get_latest_confirmed_block_number(self) -> int:
        pass

    @abc.abstractmethod
    def get_latest_confirmed_block(self) -> Block:
        pass

    @abc.abstractmethod
    def get_block_by_number(self, number: int) -> Block:
        pass

    # Transaction
    @abc.abstractmethod
    def transfer_eth(
            self,
            to_address: str,
            amount: int,
            gas_price: Optional[int] = None) -> str:
        pass

    @abc.abstractmethod
    def subscribe_to_direct_incoming_eth_transfers(
            self,
            address: str,
            from_block: int,
            cb: Callable[[DirectEthTransfer], None]) -> None:
        """
        Ether transfer detection is not an easy topic. This is a best effort
        method to subscribe to incoming transfers that originate from a wallet
        account (so not a contract, hence direct).
        """
        pass

    @abc.abstractmethod
    def estimate_transfer_eth_gas(self, to_address: str, amount: int) -> int:
        pass

    # Transaction
    @abc.abstractmethod
    def transfer_gnt(self, to_address: str, amount: int) -> str:
        pass

    @abc.abstractmethod
    def subscribe_to_gnt_transfers(
            self,
            from_address: Optional[str],
            to_address: Optional[str],
            from_block: int,
            cb: Callable[[GntTransferEvent], None]) -> None:
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
    def batch_transfer(self, payments: List[Payment], closure_time: int) -> str:
        pass

    ########################
    # GNT-GNTB conversions #
    ########################

    # Transaction
    @abc.abstractmethod
    def open_gate(self) -> str:
        """
        Creates the gate required for GNT-GNTB conversion.
        """
        pass

    @abc.abstractmethod
    def get_gate_address(self) -> Optional[str]:
        """
        Returns Ethereum address of the gate or None if it doesn't exist yet.
        """
        pass

    # Transaction
    @abc.abstractmethod
    def transfer_from_gate(self) -> str:
        """
        Final step which convert the value of the gate to GNTB.
        """
        pass

    # Transaction
    @abc.abstractmethod
    def convert_gntb_to_gnt(
            self,
            to_address: str,
            amount: int,
            gas_price: Optional[int] = None) -> str:
        pass

    ############################
    # Concent specific methods #
    ############################

    @abc.abstractmethod
    def get_deposit_value(
            self,
            account_address: str) -> int:
        """
        Returns Concent deposit value of a given address.
        """
        pass

    @abc.abstractmethod
    def get_deposit_locked_until(
            self,
            account_address: str) -> int:
        """
        Returns deposit locked_until value which is a Unix epoch timestamp in
        seconds.
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
    def lock_deposit(self) -> str:
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
            subtask_id: bytes,
            v: int,
            r: bytes,
            s: bytes,
            reimburse_amount: int) -> str:
        pass

    @abc.abstractmethod
    def get_forced_subtask_payments(
            self,
            requestor_address: str,
            provider_address: str,
            from_block: int,
            to_block: int) -> List[ForcedSubtaskPaymentEvent]:
        pass

    @abc.abstractmethod
    def subscribe_to_forced_subtask_payments(
            self,
            requestor_address: Optional[str],
            provider_address: Optional[str],
            from_block: int,
            cb: Callable[[ForcedSubtaskPaymentEvent], None]) -> None:
        pass

    # Transaction
    @abc.abstractmethod
    def force_payment(
            self,
            requestor_address: str,
            provider_address: str,
            value: List[int],
            subtask_id: List[bytes],
            v: List[int],
            r: List[bytes],
            s: List[bytes],
            reimburse_amount: int,
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

    @abc.abstractmethod
    def subscribe_to_forced_payments(
            self,
            requestor_address: Optional[str],
            provider_address: Optional[str],
            from_block: int,
            cb: Callable[[ForcedPaymentEvent], None]) -> None:
        pass

    # Transaction
    @abc.abstractmethod
    def cover_additional_verification_cost(
            self,
            address: str,
            value: int,
            subtask_id: bytes,
            v: int,
            r: bytes,
            s: bytes,
            reimburse_amount: int) -> str:
        pass

    @abc.abstractmethod
    def get_covered_additional_verification_costs(
            self,
            address: str,
            from_block: int,
            to_block: int) -> List[CoverAdditionalVerificationEvent]:
        pass
