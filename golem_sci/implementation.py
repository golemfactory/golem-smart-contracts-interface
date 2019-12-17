import logging
import threading
from typing import Any, Callable, ClassVar, Dict, List, Optional, Tuple

from eth_utils import decode_hex, encode_hex
from ethereum.utils import zpad, int_to_big_endian, denoms
from ethereum.transactions import Transaction

from . import contracts
from .client import Client
from .interface import SmartContractsInterface
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


class Subscription:
    def __init__(
            self,
            contract,
            event_name: str,
            args: Dict[str, Any],
            event_cls,
            cb,
            from_block: int) -> None:
        self.contract = contract
        self.event_name = event_name
        self.args = args
        self.event_cls = event_cls
        self.cb = cb
        self.last_pulled_block = from_block


class EthSubscription:
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
    GAS_REIMBURSE = 90000
    GAS_WITHDRAW_DEPOSIT = 75000

    REQUIRED_CONFS: ClassVar[int] = 6

    def __init__(
            self,
            geth_client: Client,
            address: str,
            storage: TransactionsStorage,
            contract_addresses: Dict[contracts.Contract, str],
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
        logger.debug("Starting SCI")
        self._geth_client = geth_client
        self._address = address

        self._tx_lock = threading.Lock()
        self._storage = storage
        self._storage.init(geth_client.get_transaction_count(address))
        self._tx_sign = tx_sign

        def _make_contract(contract: contracts.Contract):
            if contract not in contract_addresses:
                logger.info(
                    "Address not provided for %s, won't be able to use it",
                    contract,
                )
                return None
            return self._geth_client.contract(
                contract_addresses[contract],
                contracts.get_abi(contract),
            )

        self._gnt = _make_contract(contracts.GNT)
        self._gntb = _make_contract(contracts.GNTB)
        self._gntdeposit = _make_contract(contracts.GNTDeposit)
        self._faucet = _make_contract(contracts.Faucet)

        self._subs_lock = threading.Lock()
        self._subscriptions: List[Subscription] = []
        self._eth_subs_lock = threading.Lock()
        self._eth_subscriptions: List[EthSubscription] = []

        self._awaiting_transactions_lock = threading.Lock()
        self._awaiting_transactions: List[Tuple] = []

        self._confirmed_block = -self.REQUIRED_CONFS
        self._update_block_numbers()
        self._update_gas_price()

        self._eth_reserved_lock = threading.Lock()
        self._eth_reserved = 0
        for tx in self._storage.get_all_tx():
            self._eth_reserved += tx.startgas * tx.gasprice + tx.value

        self._monitor_thread = None
        self._monitor_cv = threading.Condition()
        self._monitor_started = False
        if monitor:
            self._monitor_thread = threading.Thread(
                target=self._monitor_blockchain,
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

    def subscribe_to_batch_transfers(
            self,
            payer_address: Optional[str],
            payee_address: Optional[str],
            from_block: int,
            cb: Callable[[BatchTransferEvent], None]) -> None:
        self._create_subscription(
            self._gntb,
            'BatchTransfer',
            {
                'from': payer_address,
                'to': payee_address,
            },
            BatchTransferEvent,
            from_block,
            cb,
        )

    def on_transaction_confirmed(
            self,
            tx_hash: str,
            cb: Callable[[TransactionReceipt], None]) -> None:
        with self._awaiting_transactions_lock:
            self._awaiting_transactions.append((tx_hash, cb))

    def get_latest_confirmed_block(self) -> Block:
        return self.get_block_by_number(
            self.get_latest_confirmed_block_number())

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
            gasprice=gas_price,
            startgas=self.estimate_transfer_eth_gas(to_address, amount),
            to=to_address,
            value=amount,
            data=b'',
            nonce=0,  # nonce will be overridden
        )
        return self._sign_and_send_transaction(tx)

    def subscribe_to_direct_incoming_eth_transfers(
            self,
            address: str,
            from_block: int,
            cb: Callable[[DirectEthTransfer], None]) -> None:
        with self._eth_subs_lock:
            self._eth_subscriptions.append(EthSubscription(
                address,
                cb,
                from_block - 1,
            ))

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

    def subscribe_to_gnt_transfers(
            self,
            from_address: Optional[str],
            to_address: Optional[str],
            from_block: int,
            cb: Callable[[GntTransferEvent], None]) -> None:
        self._create_subscription(
            self._gnt,
            'Transfer',
            {
                '_from': from_address,
                '_to': to_address,
            },
            GntTransferEvent,
            from_block,
            cb,
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

    def get_latest_confirmed_block_number(self) -> int:
        return self._confirmed_block

    def get_transaction_receipt(
            self,
            tx_hash: str) -> Optional[TransactionReceipt]:
        raw = self._geth_client.get_transaction_receipt(tx_hash)
        if not raw:
            return None
        receipt = TransactionReceipt(raw)
        if receipt.block_number > self._confirmed_block:
            return None
        return receipt

    def get_transaction_gas_price(
            self,
            tx_hash: str) -> Optional[int]:
        raw = self._geth_client.get_transaction(tx_hash)
        return raw['gasPrice'] if raw else None

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
        logger.debug("Stopping SCI")
        self._geth_client.stop()
        logger.debug("SCI monitor: stopping")
        self._monitor_started = False
        with self._monitor_cv:
            self._monitor_cv.notify()
        logger.debug("SCI monitor: stopped")

    def _call(self, method) -> Any:
        return method.call(
            {'from': self._address},
            block_identifier=self._confirmed_block,
        )

    def _sign_and_send_transaction(self, tx: Transaction) -> str:
        with self._tx_lock:
            total_eth = tx.startgas * tx.gasprice + tx.value
            balance = self.get_eth_balance(self._address)
            if total_eth > balance:
                raise Exception(
                    'Not enough ETH for transaction. Has {}, required {}'.format(  # noqa
                        balance / denoms.ether,
                        total_eth / denoms.ether,
                    ))
            self._storage.set_nonce_sign_and_save_tx(self._tx_sign, tx)
            with self._eth_reserved_lock:
                self._eth_reserved += total_eth
            try:
                return self._geth_client.send(tx)
            except Exception as e:
                tx_hash = encode_hex(tx.hash)
                if _is_jsonrpc_error(e):
                    # yay for grepping for the error message because error codes
                    # from Geth are not unique
                    error_msg = e.args[0]['message']
                    # This can happen when reconnecting to other Geth instance
                    # but initial request went through anyway and the
                    # transaction was propagated, so this is fine
                    if error_msg.startswith('known transaction'):
                        return tx_hash
                    # Similar to the above but there are two cases:
                    # 1. Transaction got mined in the meantime and this is fine
                    # 2. Otherwise an actual error
                    if error_msg.startswith('nonce too low'):
                        if self._geth_client.get_transaction_receipt(tx_hash):
                            return tx_hash
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
                return tx_hash

    def _create_and_send_transaction(
            self,
            contract,
            fn_name: str,
            args: List[Any],
            gas_limit: int,
            gas_price: Optional[int] = None) -> str:
        raw_tx = contract.functions[fn_name](*args).buildTransaction({
            'gas': gas_limit,
        })
        if gas_price is None:
            gas_price = self.get_current_gas_price()
        tx = Transaction(
            gasprice=gas_price,
            startgas=gas_limit,
            to=raw_tx['to'],
            value=0,
            data=decode_hex(raw_tx['data']),
            nonce=0,  # nonce will be overridden
        )
        return self._sign_and_send_transaction(tx)

    def _create_subscription(
            self,
            contract,
            event_name: str,
            args: Dict[str, Any],
            event_cls,
            from_block: int,
            cb: Callable[[Any], None]) -> None:
        with self._subs_lock:
            self._subscriptions.append(Subscription(
                contract,
                event_name,
                args,
                event_cls,
                cb,
                from_block - 1,
            ))

    def _monitor_blockchain(self):
        logger.debug("SCI monitor: started")
        self._monitor_started = True
        with self._monitor_cv:
            while self._monitor_started \
                    and not self._monitor_cv.wait(timeout=15):
                try:
                    self._monitor_blockchain_single()
                except Exception as e:
                    logger.exception('Blockchain monitor exception: %r', e)

    def _monitor_blockchain_single(self):
        if not self._update_block_numbers():
            return
        logger.debug("SCI monitor: block updated")
        steps = (
            self._update_gas_price,
            self._pull_subscription_events,
            self._pull_eth_subscription_events,
            self._process_awaiting_transactions,
            self._process_sent_transactions,
        )
        for step in steps:
            if self._monitor_started:
                logger.debug("SCI monitor: step %s", )
                step()

    def _update_gas_price(self) -> None:
        self._gas_price = max(
            self.GAS_PRICE_MIN,
            min(self.GAS_PRICE, self._geth_client.get_gas_price()),
        )

    def _update_block_numbers(self) -> bool:
        latest_block = self._geth_client.get_block_number()
        confirmed_block = latest_block - self.REQUIRED_CONFS + 1
        if confirmed_block <= self._confirmed_block:
            return False
        self._confirmed_block = confirmed_block
        return True

    def _on_event(self, event, cb) -> None:
        logger.info('Detected event %s', event)
        try:
            cb(event)
        except Exception as e:
            logger.exception('Event callback exception: %r', e)

    def _pull_subscription_events(self) -> None:
        with self._subs_lock:
            subs = self._subscriptions.copy()
        for sub in subs:
            if not self._monitor_started:
                break
            try:
                if sub.last_pulled_block >= self._confirmed_block:
                    continue
                logs = self._geth_client.get_logs(
                    sub.contract,
                    sub.event_name,
                    sub.args,
                    sub.last_pulled_block + 1,
                    self._confirmed_block,
                )
                for log in logs:
                    self._on_event(sub.event_cls(log), sub.cb)
                sub.last_pulled_block = self._confirmed_block
            except Exception as e:
                logger.exception(
                    'Exception while processing subscription: %r',
                    e,
                )

    def _find_incoming_eth_transfers(
            self,
            from_block: int,
            to_block: int,
            address: str,
            from_block_balance: Optional[int] = None,
            to_block_balance: Optional[int] = None) -> List[DirectEthTransfer]:
        """
        Finds and returns transactions that send Ether to an address within
        block range (from_block, to_block].
        Proper way is to iterate over all transactions from all the blocks but
        it's way too resource consuming, so this is an approximation that may
        not find transactions if an address sent out (or spent on gas) more
        ether than it received within this block range.
        """
        if from_block_balance is None:
            from_block_balance = self._geth_client.get_balance(
                address,
                block=from_block,
            )
        if to_block_balance is None:
            to_block_balance = self._geth_client.get_balance(
                address,
                block=to_block,
            )
        if to_block_balance <= from_block_balance:
            return []
        if to_block - from_block < 4:
            result = []
            for block_number in range(from_block + 1, to_block + 1):
                raw_block = self._geth_client.get_block(block_number, True)
                for tx in raw_block['transactions']:
                    if tx['to'] == address:
                        result.append(DirectEthTransfer(tx))
            return result
        mid = (from_block + to_block) // 2
        mid_block_balance = self._geth_client.get_balance(
            address,
            block=mid,
        )
        result = self._find_incoming_eth_transfers(
            from_block,
            mid,
            address,
            from_block_balance,
            mid_block_balance,
        )
        result.extend(self._find_incoming_eth_transfers(
            mid,
            to_block,
            address,
            mid_block_balance,
            to_block_balance,
        ))
        return result

    def _pull_eth_subscription_events(self) -> None:
        with self._eth_subs_lock:
            subs = self._eth_subscriptions.copy()
        for sub in subs:
            if not self._monitor_started:
                break
            try:
                if sub.last_pulled_block >= self._confirmed_block:
                    continue
                transfers = self._find_incoming_eth_transfers(
                    sub.last_pulled_block,
                    self._confirmed_block,
                    sub.address,
                )
                for t in transfers:
                    self._on_event(t, sub.cb)
                sub.last_pulled_block = self._confirmed_block
            except Exception as e:
                if (
                        _is_jsonrpc_error(e)
                        and 'missing trie node' in e.args[0]['message']
                ):
                    log = logger.warning
                    # we cannot do anything here
                    # so let's just bump the pointer
                    # so that we don't poll the geth node repeatedly
                    sub.last_pulled_block = self._confirmed_block
                else:
                    log = logger.exception
                log(
                    'Exception while processing eth subscription: %r',
                    e,
                )

    def _process_awaiting_transactions(self) -> None:
        with self._awaiting_transactions_lock:
            awaiting_transactions = self._awaiting_transactions
            self._awaiting_transactions = []

        def processed(awaiting_tx) -> bool:
            tx_hash, cb = awaiting_tx
            receipt = self.get_transaction_receipt(tx_hash)
            if not receipt:
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
        with self._tx_lock:
            transactions = self._storage.get_all_tx()

            for tx in transactions:
                try:
                    tx_hash = encode_hex(tx.hash)
                    receipt = self.get_transaction_receipt(tx_hash)
                    if receipt:
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
                    logger.warning(
                        "Exception while resending transaction %s: %r",
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

    def convert_gntb_to_gnt(
            self,
            to_address: str,
            amount: int,
            gas_price: Optional[int] = None) -> str:
        return self._create_and_send_transaction(
            self._gntb,
            'withdrawTo',
            [amount, to_address],
            self.GAS_WITHDRAW,
            gas_price,
        )

    ############################
    # Concent specific methods #
    ############################

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
        if len(subtask_id) != 32:
            raise ValueError('subtask_id has to be exactly 32 bytes long')
        return self._create_and_send_transaction(
            self._gntdeposit,
            'reimburseForSubtask',
            [
                requestor_address,
                provider_address,
                value,
                subtask_id,
                v,
                r,
                s,
                reimburse_amount,
            ],
            self.GAS_REIMBURSE,
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

    def subscribe_to_forced_subtask_payments(
            self,
            requestor_address: Optional[str],
            provider_address: Optional[str],
            from_block: int,
            cb: Callable[[ForcedSubtaskPaymentEvent], None]) -> None:
        self._create_subscription(
            self._gntdeposit,
            'ReimburseForSubtask',
            {
                '_requestor': requestor_address,
                '_provider': provider_address,
            },
            ForcedSubtaskPaymentEvent,
            from_block,
            cb,
        )

    def deposit_payment(self, value: int) -> str:
        return self.transfer_gntb_and_call(self._gntdeposit.address, value, b'')

    def unlock_deposit(self) -> str:
        return self._create_and_send_transaction(
            self._gntdeposit,
            'unlock',
            [],
            self.GAS_UNLOCK_DEPOSIT,
        )

    def lock_deposit(self) -> str:
        return self._create_and_send_transaction(
            self._gntdeposit,
            'lock',
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
            value: List[int],
            subtask_id: List[bytes],
            v: List[int],
            r: List[bytes],
            s: List[bytes],
            reimburse_amount: int,
            closure_time: int) -> str:
        return self._create_and_send_transaction(
            self._gntdeposit,
            'reimburseForNoPayment',
            [
                requestor_address,
                provider_address,
                value,
                subtask_id,
                v,
                r,
                s,
                reimburse_amount,
                closure_time,
            ],
            self.GAS_REIMBURSE + len(value) * 5000,
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

    def subscribe_to_forced_payments(
            self,
            requestor_address: Optional[str],
            provider_address: Optional[str],
            from_block: int,
            cb: Callable[[ForcedPaymentEvent], None]) -> None:
        self._create_subscription(
            self._gntdeposit,
            'ReimburseForNoPayment',
            {
                '_requestor': requestor_address,
                '_provider': provider_address,
            },
            ForcedPaymentEvent,
            from_block,
            cb,
        )

    def cover_additional_verification_cost(
            self,
            address: str,
            value: int,
            subtask_id: bytes,
            v: int,
            r: bytes,
            s: bytes,
            reimburse_amount: int) -> str:
        if len(subtask_id) != 32:
            raise ValueError('subtask_id has to be exactly 32 bytes long')
        return self._create_and_send_transaction(
            self._gntdeposit,
            'reimburseForVerificationCosts',
            [address, value, subtask_id, v, r, s, reimburse_amount],
            self.GAS_REIMBURSE,
        )

    def get_covered_additional_verification_costs(
            self,
            address: str,
            from_block: int,
            to_block: int) -> List[CoverAdditionalVerificationEvent]:
        filter_id = self._gntdeposit.events.ReimburseForVerificationCosts.\
            createFilter(
                fromBlock=from_block,
                toBlock=to_block,
                argument_filters={
                    '_from': address,
                },
            ).filter_id
        logs = self._geth_client.get_filter_logs(filter_id)

        return [CoverAdditionalVerificationEvent(raw_log) for raw_log in logs]

    def get_deposit_value(
            self,
            account_address: str) -> int:
        return self._call(self._gntdeposit.functions.balanceOf(account_address))

    def get_deposit_locked_until(
            self,
            account_address: str) -> int:
        return self._call(
            self._gntdeposit.functions.getTimelock(account_address))
