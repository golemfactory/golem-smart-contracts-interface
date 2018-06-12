import logging
import threading
import time
from typing import Any, Callable, ClassVar, Dict, List, Optional, Tuple

from ethereum.utils import zpad, int_to_big_endian, denoms
from ethereum.transactions import Transaction
from eth_utils import decode_hex, encode_hex

from golem_sci import contracts
from .client import Client, FilterNotFoundException
from .interface import SmartContractsInterface
from .events import (
    BatchTransferEvent,
    ForcedPaymentEvent,
    ForcedSubtaskPaymentEvent,
    CoverAdditionalVerificationEvent,
)
from .structs import (
    Block,
    Payment,
    TransactionReceipt,
)
from .transactionsstorage import TransactionsStorage

logger = logging.getLogger(__name__)


def encode_payment(p: Payment) -> bytes:
    max_value = 2 ** 96
    if p.amount >= max_value:
        raise ValueError("Payment should be less than {}".format(max_value))
    v = zpad(int_to_big_endian(p.amount), 12)
    pair = v + decode_hex(p.payee)
    if len(pair) != 32:
        raise ValueError(
            "Incorrect pair length: {}. Should be 32".format(len(pair)))
    return pair


# web3 just throws ValueError(response['error']) and this is the best we can
# do to check whether this is coming from there
def _is_jsonrpc_error(e: Exception) -> bool:
    if not isinstance(e, ValueError):
        return False
    if len(e.args) != 1:
        return False
    arg = e.args[0]
    if not isinstance(arg, dict):
        return False
    return len(arg) == 2 and 'message' in arg and 'code' in arg


class SubscriptionFilter:
    def __init__(
            self,
            address: str,
            cb,
            from_block: int) -> None:
        self.address = address
        self.cb = cb
        self.last_pulled_block = from_block


class SCIImplementation(SmartContractsInterface):
    # Gas price: 20 gwei, Homestead suggested gas price.
    GAS_PRICE = 20 * 10 ** 9
    GAS_PRICE_MIN = 10 ** 8

    GAS_GNT_TRANSFER = 55000
    GAS_WITHDRAW = 75000
    GAS_OPEN_GATE = 230000
    GAS_TRANSFER_FROM_GATE = 100000
    GAS_TRANSFER_AND_CALL = 90000
    # Total gas for a batchTransfer is BASE + len(payments) * PER_PAYMENT
    GAS_PER_PAYMENT = 28000
    GAS_BATCH_PAYMENT_BASE = 27000
    GAS_FAUCET = 90000
    # Concent methods
    GAS_UNLOCK_DEPOSIT = 55000
    GAS_FORCE_PAYMENT = 80000
    GAS_WITHDRAW_DEPOSIT = 75000

    REQUIRED_CONFS: ClassVar[int] = 6

    def __init__(
            self,
            geth_client: Client,
            address: str,
            storage: TransactionsStorage,
            contract_data_provider,
            tx_sign=None,
            monitor=True) -> None:
        """
        Performs all blockchain operations using the address as the caller.
        Uses tx_sign to sign outgoing transaction, tx_sign can be None in which
        case one may only perform read only operations.
        Straightforward implementation of tx_sign having the private key:
        def sign_tx(tx) -> None:
            tx.sign(private_key)
        """
        self._geth_client = geth_client
        self._address = address
        self._storage = storage
        self._tx_sign = tx_sign

        def _make_contract(contract: str):
            try:
                return self._geth_client.contract(
                    contract_data_provider.get_address(contract),
                    contract_data_provider.get_abi(contract),
                )
            except Exception as e:
                logger.warning("Unable to use `%s` contract: %r", contract, e)
                return None

        self._gnt = _make_contract(contracts.GolemNetworkToken)
        self._gntb = _make_contract(contracts.GolemNetworkTokenBatching)
        self._gntdeposit = _make_contract(contracts.GNTDeposit)
        self._faucet = _make_contract(contracts.Faucet)

        self._subs_lock = threading.Lock()
        self._subscriptions: Dict[str, SubscriptionFilter] = {}

        self._awaiting_callbacks: Dict[str, Tuple] = {}
        self._cb_id = 0

        self._awaiting_transactions_lock = threading.Lock()
        self._awaiting_transactions: List[Tuple] = []

        self._update_gas_price()
        self._update_block_numbers()

        self._eth_reserved_lock = threading.Lock()
        self._eth_reserved = 0
        for tx in self._storage.get_all_tx():
            self._eth_reserved += tx.startgas * tx.gasprice + tx.value

        self._monitor_thread = None
        self._monitor_stop = threading.Event()
        if monitor:
            self._monitor_thread = threading.Thread(
                target=self._monitor_blockchain,
                daemon=True,
            )
            self._monitor_thread.start()

    def get_eth_address(self) -> str:
        return self._address

    def get_eth_balance(self, address: str) -> int:
        balance = self._geth_client.get_balance(
            address,
            block=self._confirmed_block,
        )
        if address == self._address:
            with self._eth_reserved_lock:
                balance -= self._eth_reserved
        return balance

    def get_gnt_balance(self, address: str) -> int:
        return self._call(self._gnt.functions.balanceOf(address))

    def get_gntb_balance(self, address: str) -> int:
        return self._call(self._gntb.functions.balanceOf(address))

    def batch_transfer(self, payments: List[Payment], closure_time: int) -> str:
        encoded_payments = []
        for p in payments:
            encoded_payments.append(encode_payment(p))
        gas = self.GAS_BATCH_PAYMENT_BASE + len(payments) * self.GAS_PER_PAYMENT
        return self._create_and_send_transaction(
            self._gntb,
            'batchTransfer',
            [encoded_payments, closure_time],
            gas,
        )

    def get_batch_transfers(
            self,
            payer_address: str,
            payee_address: str,
            from_block: int,
            to_block: int) -> List[BatchTransferEvent]:
        filter_id = self._gntb.events.BatchTransfer.createFilter(
            fromBlock=from_block,
            toBlock=to_block,
            argument_filters={
                'from': payer_address,
                'to': payee_address,
            },
        ).filter_id
        logs = self._geth_client.get_filter_logs(filter_id)

        return [BatchTransferEvent(raw_log) for raw_log in logs]

    def subscribe_to_incoming_batch_transfers(
            self,
            address: str,
            from_block: int,
            cb: Callable[[BatchTransferEvent], None]) -> None:
        with self._subs_lock:
            filter_id = self._gntb.events.BatchTransfer.createFilter(
                fromBlock=from_block,
                toBlock='latest',
                argument_filters={'to': address},
            ).filter_id
            logs = self._geth_client.get_filter_logs(filter_id)
            for log in logs:
                self._on_filter_log(log, cb)
            self._subscriptions[filter_id] = SubscriptionFilter(
                address,
                cb,
                from_block,
            )

    def on_transaction_confirmed(
            self,
            tx_hash: str,
            cb: Callable[[TransactionReceipt], None]) -> None:
        with self._awaiting_transactions_lock:
            self._awaiting_transactions.append((tx_hash, cb))

    def get_latest_block(self) -> Block:
        return self.get_block_by_number(self.get_block_number())

    def get_block_by_number(self, number: int) -> Block:
        return Block(self._geth_client.get_block(number))

    def transfer_eth(
            self,
            to_address: str,
            amount: int,
            gas_price: Optional[int] = None) -> str:
        if gas_price is None:
            gas_price = self.get_current_gas_price()

        tx = Transaction(
            nonce=self._get_current_nonce(),
            gasprice=gas_price,
            startgas=self.estimate_transfer_eth_gas(to_address, amount),
            to=to_address,
            value=amount,
            data=b'',
        )
        return self._sign_and_send_transaction(tx)

    def estimate_transfer_eth_gas(self, to_address: str, amount: int) -> int:
        return self._geth_client.estimate_gas({
            'to': to_address,
            'from': self._address,
            'value': amount,
        })

    def transfer_gnt(self, to_address: str, amount: int) -> str:
        return self._create_and_send_transaction(
            self._gnt,
            'transfer',
            [to_address, amount],
            self.GAS_GNT_TRANSFER,
        )

    def transfer_gntb(self, to_address: str, amount: int) -> str:
        return self._create_and_send_transaction(
            self._gntb,
            'transfer',
            [to_address, amount],
            self.GAS_GNT_TRANSFER,
        )

    def transfer_gntb_and_call(
            self,
            to_address: str,
            amount: int,
            data: bytes) -> str:
        return self._create_and_send_transaction(
            self._gntb,
            'transferAndCall',
            [to_address, amount, data],
            self.GAS_TRANSFER_AND_CALL,
        )

    def get_block_number(self) -> int:
        return self._current_block

    def get_transaction_receipt(
            self,
            tx_hash: str) -> Optional[TransactionReceipt]:
        raw = self._geth_client.get_transaction_receipt(tx_hash)
        return TransactionReceipt(raw) if raw else None

    def get_current_gas_price(self) -> int:
        return self._gas_price

    def request_gnt_from_faucet(self) -> str:
        return self._create_and_send_transaction(
            self._faucet,
            'create',
            [],
            self.GAS_FAUCET,
        )

    def wait_until_synchronized(self) -> bool:
        return self._geth_client.wait_until_synchronized()

    def is_synchronized(self) -> bool:
        return self._geth_client.is_synchronized()

    def stop(self) -> None:
        self._geth_client.stop()
        self._monitor_stop.set()

    def _call(self, method) -> Any:
        return method.call(
            {'from': self._address},
            block_identifier=self._confirmed_block,
        )

    def _get_current_nonce(self) -> int:
        return self._storage.get_nonce()

    def _sign_and_send_transaction(self, tx: Transaction) -> str:
        self._tx_sign(tx)
        total_eth = tx.startgas * tx.gasprice + tx.value
        balance = self.get_eth_balance(self._address)
        if total_eth > balance:
            raise Exception(
                'Not enough ETH for transaction. Got {}, required {}'.format(
                    balance / denoms.ether,
                    total_eth / denoms.ether,
                ))
        self._storage.put_tx_and_inc_nonce(tx)
        try:
            with self._eth_reserved_lock:
                self._eth_reserved += total_eth
            return self._geth_client.send(tx)
        except Exception as e:
            if _is_jsonrpc_error(e):
                # This can be stuff like not enough gas for the transaction.
                # It shouldn't ever happen and if it does then it's a bug
                # that should be fixed by the caller.
                logger.critical('web3 JSON rpc critical error %r', e)
                with self._eth_reserved_lock:
                    self._eth_reserved -= total_eth
                self._storage.revert_last_tx()
                raise
            # We don't need to do anything explicitly, it will be retried
            logger.exception(
                'Exception while sending transaction, will be retried: %r',
                e,
            )
            return encode_hex(tx.hash)

    def _create_and_send_transaction(
            self,
            contract,
            fn_name: str,
            args: List[Any],
            gas_limit: int) -> str:
        raw_tx = contract.functions[fn_name](*args).buildTransaction({
            'gas': gas_limit,
        })
        tx = Transaction(
            nonce=self._get_current_nonce(),
            gasprice=self.get_current_gas_price(),
            startgas=gas_limit,
            to=raw_tx['to'],
            value=0,
            data=decode_hex(raw_tx['data']),
        )
        return self._sign_and_send_transaction(tx)

    def _monitor_blockchain(self):
        while not self._monitor_stop.is_set():
            try:
                self._monitor_blockchain_single()
            except Exception as e:
                logger.exception('Blockchain monitor exception: %r', e)
            time.sleep(15)

    def _monitor_blockchain_single(self):
        self._update_block_numbers()
        self._update_gas_price()
        self._pull_filter_changes()
        self._process_awaiting_transactions()
        self._process_sent_transactions()

    def _update_gas_price(self) -> None:
        self._gas_price = max(
            self.GAS_PRICE_MIN,
            min(self.GAS_PRICE, self._geth_client.get_gas_price()),
        )

    def _update_block_numbers(self) -> None:
        self._current_block = self._geth_client.get_block_number()
        self._confirmed_block = self._current_block - self.REQUIRED_CONFS + 1

    def _on_filter_log(self, log, cb) -> None:
        tx_hash = log['transactionHash'].hex()
        if log['removed']:
            del self._awaiting_callbacks[tx_hash]
        else:
            cb_copy = cb
            event = BatchTransferEvent(log)
            logger.info(
                'Detected incoming batch transfer %s, waiting for confirmation',
                event,
            )

            self._awaiting_callbacks[tx_hash] = (
                lambda: cb_copy(event),
                self._cb_id,
                log['blockNumber'],
            )
            self._cb_id += 1

    def _pull_filter_changes(self) -> None:
        with self._subs_lock:
            subs = self._subscriptions.copy()
        for filter_id, sub in subs.items():
            try:
                logs = self._geth_client.get_filter_changes(filter_id)
                for log in logs:
                    self._on_filter_log(log, sub.cb)
                sub.last_pulled_block = self._current_block
            except FilterNotFoundException as e:
                logger.warning('Filter not found error, probably caused by'
                               ' network loss. Recreating.')
                with self._subs_lock:
                    del self._subscriptions[filter_id]
                self.subscribe_to_incoming_batch_transfers(
                    sub.address,
                    sub.last_pulled_block,
                    sub.cb,
                )

        if self._awaiting_callbacks:
            to_remove = []
            chronological_callbacks = sorted(
                self._awaiting_callbacks.items(),
                key=lambda v: v[1][1],
            )
            for key, (cb, _, block_number) in chronological_callbacks:
                if block_number <= self._confirmed_block:
                    try:
                        logger.info(
                            'Incoming batch transfer confirmed %s',
                            key,
                        )
                        cb()
                    except Exception as e:
                        logger.exception('Tx callback exception: %r', e)
                    to_remove.append(key)

            for key in to_remove:
                del self._awaiting_callbacks[key]

    def _process_awaiting_transactions(self) -> None:
        with self._awaiting_transactions_lock:
            awaiting_transactions = self._awaiting_transactions
            self._awaiting_transactions = []

        def processed(awaiting_tx) -> bool:
            tx_hash, cb = awaiting_tx
            receipt = self.get_transaction_receipt(tx_hash)
            if not receipt:
                return False
            if receipt.block_number > self._confirmed_block:
                return False
            try:
                cb(receipt)
            except Exception as e:
                logger.exception(
                    'Confirmed transaction %r callback error: %r',
                    tx_hash,
                    e,
                )
            return True

        remaining_awaiting_transactions = \
            [tx for tx in awaiting_transactions if not processed(tx)]

        with self._awaiting_transactions_lock:
            self._awaiting_transactions.extend(remaining_awaiting_transactions)

    def _process_sent_transactions(self) -> None:
        transactions = self._storage.get_all_tx()

        for tx in transactions:
            try:
                tx_hash = encode_hex(tx.hash)
                receipt = self.get_transaction_receipt(tx_hash)
                if receipt:
                    if receipt.block_number <= self._confirmed_block:
                        self._storage.remove_tx(tx.nonce)
                        with self._eth_reserved_lock:
                            self._eth_reserved -= \
                                tx.value + tx.gasprice * tx.startgas
                else:
                    tx_res = self._geth_client.get_transaction(tx_hash)
                    if tx_res is None:
                        logger.info('Resending transaction %r', tx_hash)
                        self._geth_client.send(tx)
            except Exception as e:
                logger.exception(
                    "Exception while processing transaction %s: %r",
                    tx_hash,
                    e,
                )

    ########################
    # GNT-GNTB conversions #
    ########################

    def open_gate(self) -> str:
        return self._create_and_send_transaction(
            self._gntb,
            'openGate',
            [],
            self.GAS_OPEN_GATE,
        )

    def get_gate_address(self) -> Optional[str]:
        addr = self._call(self._gntb.functions.getGateAddress(self._address))
        if addr and int(addr, 16) == 0:
            return None
        return addr

    def transfer_from_gate(self) -> str:
        return self._create_and_send_transaction(
            self._gntb,
            'transferFromGate',
            [],
            self.GAS_TRANSFER_FROM_GATE,
        )

    def convert_gntb_to_gnt(self, to_address: str, amount: int) -> str:
        return self._create_and_send_transaction(
            self._gntb,
            'withdrawTo',
            [amount, to_address],
            self.GAS_WITHDRAW,
        )

    ############################
    # Concent specific methods #
    ############################

    def force_subtask_payment(
            self,
            requestor_address: str,
            provider_address: str,
            value: int,
            subtask_id: str) -> str:
        if len(subtask_id) > 32:
            raise ValueError('subtask_id cannot be longer than 32 characters')
        return self._create_and_send_transaction(
            self._gntdeposit,
            'reimburseForSubtask',
            [
                requestor_address,
                provider_address,
                value,
                subtask_id.encode('UTF-8'),
            ],
            self.GAS_FORCE_PAYMENT,
        )

    def get_forced_subtask_payments(
            self,
            requestor_address: str,
            provider_address: str,
            from_block: int,
            to_block: int) -> List[ForcedSubtaskPaymentEvent]:
        filter_id = \
            self._gntdeposit.events.ReimburseForSubtask.createFilter(
                fromBlock=from_block,
                toBlock=to_block,
                argument_filters={
                    '_requestor': requestor_address,
                    '_provider': provider_address,
                },
            ).filter_id
        logs = self._geth_client.get_filter_logs(filter_id)

        return [ForcedSubtaskPaymentEvent(raw_log) for raw_log in logs]

    def deposit_payment(self, value: int) -> str:
        return self.transfer_gntb_and_call(self._gntdeposit.address, value, b'')

    def unlock_deposit(self) -> str:
        return self._create_and_send_transaction(
            self._gntdeposit,
            'unlock',
            [],
            self.GAS_UNLOCK_DEPOSIT,
        )

    def withdraw_deposit(self) -> str:
        return self._create_and_send_transaction(
            self._gntdeposit,
            'withdraw',
            [self._address],
            self.GAS_WITHDRAW_DEPOSIT,
        )

    def force_payment(
            self,
            requestor_address: str,
            provider_address: str,
            value: int,
            closure_time: int) -> str:
        return self._create_and_send_transaction(
            self._gntdeposit,
            'reimburseForNoPayment',
            [requestor_address, provider_address, value, closure_time],
            self.GAS_FORCE_PAYMENT,
        )

    def get_forced_payments(
            self,
            requestor_address: str,
            provider_address: str,
            from_block: int,
            to_block: int) -> List[ForcedPaymentEvent]:
        filter_id = self._gntdeposit.events.ReimburseForNoPayment.\
            createFilter(
                fromBlock=from_block,
                toBlock=to_block,
                argument_filters={
                    '_requestor': requestor_address,
                    '_provider': provider_address,
                },
            ).filter_id
        logs = self._geth_client.get_filter_logs(filter_id)

        return [ForcedPaymentEvent(raw_log) for raw_log in logs]

    def cover_additional_verification_cost(
            self,
            client_address: str,
            value: int,
            subtask_id: str) -> str:
        raise Exception("Not implemented yet")

    def get_covered_additional_verification_costs(
            self,
            address: str,
            from_block: int,
            to_block: int) -> List[CoverAdditionalVerificationEvent]:
        raise Exception("Not implemented yet")

    def get_deposit_value(
            self,
            account_address: str) -> Optional[int]:
        return self._call(self._gntdeposit.functions.balanceOf(account_address))

    def get_deposit_locked_until(
            self,
            account_address: str) -> Optional[int]:
        return self._call(
            self._gntdeposit.functions.getTimelock(account_address))
