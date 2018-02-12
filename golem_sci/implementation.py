import logging
import threading
import time
from typing import Callable, List, Optional

from ethereum import abi
from ethereum.utils import zpad, int_to_big_endian
from ethereum.transactions import Transaction
from eth_utils import decode_hex

from golem_sci import contracts
from .interface import SmartContractsInterface, TransactionReceipt

from .events import (
    BatchTransferEvent,
    ForcedPaymentEvent,
    ForcedSubtaskPaymentEvent,
    CoverAdditionalVerificationEvent,
)

logger = logging.getLogger("golem_sci.implementation")


def encode_payments(payments):
    paymap = {}
    for p in payments:
        if p.payee in paymap:
            paymap[p.payee] += p.value
        else:
            paymap[p.payee] = p.value

    args = []
    value = 0
    for to, v in paymap.items():
        max_value = 2 ** 96
        if v >= max_value:
            raise ValueError("v should be less than {}".format(max_value))
        value += v
        v = zpad(int_to_big_endian(v), 12)
        pair = v + to
        if len(pair) != 32:
            raise ValueError(
                "Incorrect pair length: {}. Should be 32".format(len(pair)))
        args.append(pair)
    return args


class ContractWrapper:
    def __init__(self, actor_address, contract):
        self._actor_address = actor_address
        self._contract = contract
        self._translator = abi.ContractTranslator(contract.abi)
        self.address = contract.address

    def call(self):
        return self._contract.call({'from': self._actor_address})

    def create_transaction(
            self,
            function_name,
            args,
            nonce,
            gas_price,
            gas_limit) -> Transaction:
        data = self._translator.encode_function_call(function_name, args)
        return Transaction(
            nonce=nonce,
            gasprice=gas_price,
            startgas=gas_limit,
            to=decode_hex(self._contract.address),
            value=0,
            data=data,
        )

    def on(self, event_name: str, from_block, to_block, arg_filters):
        return self._contract.on(
            event_name,
            filter_params={
                'fromBlock': from_block,
                'toBlock': to_block,
                'filter': arg_filters,
            },
        ).filter_id


class SCIImplementation(SmartContractsInterface):
    # Gas price: 20 gwei, Homestead suggested gas price.
    GAS_PRICE = 20 * 10 ** 9

    GAS_TRANSFER = 90000
    GAS_CREATE_PERSONAL_DEPOSIT = 320000
    GAS_PROCESS_DEPOSIT = 110000
    # Total gas for a batchTransfer is BASE + len(payments) * PER_PAYMENT
    GAS_PER_PAYMENT = 30000
    # tx: 21000, balance substract: 5000, arithmetics < 800
    GAS_BATCH_PAYMENT_BASE = 21000 + 800 + 5000
    GAS_FAUCET = 90000

    def __init__(self, geth_client, address, tx_sign=None, monitor=True):
        """
        Performs all blockchain operations using the address as the caller.
        Uses tx_sign to sign outgoing transaction, tx_sign can be None in which
        case one may only perform read only operations.
        """
        self._geth_client = geth_client
        self._address = address
        self._tx_sign = tx_sign

        self._gntw = ContractWrapper(
            address,
            self._geth_client.contract(
                contracts.GolemNetworkTokenWrapped.ADDRESS,
                contracts.GolemNetworkTokenWrapped.ABI,
            ),
        )
        self._gnt = ContractWrapper(
            address,
            self._geth_client.contract(
                contracts.GolemNetworkToken.ADDRESS,
                contracts.GolemNetworkToken.ABI,
            ),
        )
        self._faucet = ContractWrapper(
            address,
            self._geth_client.contract(
                contracts.Faucet.ADDRESS,
                contracts.Faucet.ABI,
            ),
        )

        self._subs_lock = threading.Lock()
        self._subscriptions = []

        self._awaiting_callbacks = {}
        self._cb_id = 0

        self._awaiting_transactions_lock = threading.Lock()
        self._awaiting_transactions = []

        self._monitor_thread = None
        self._monitor_stop = threading.Event()

        if monitor:
            self._monitor_thread = threading.Thread(
                target=self._monitor_blockchain,
                daemon=True
            )
            self._monitor_thread.start()

    def get_eth_address(self) -> str:
        return self._address

    def get_eth_balance(self, address: str) -> Optional[int]:
        """
        Returns None is case of issues coming from the geth client
        """
        return self._geth_client.get_balance(address)

    def get_gnt_balance(self, address: str) -> Optional[int]:
        return self._gnt.call().balanceOf(decode_hex(address))

    def get_gntw_balance(self, address: str) -> Optional[int]:
        return self._gntw.call().balanceOf(decode_hex(address))

    def batch_transfer(self, payments, closure_time: int) -> str:
        p = encode_payments(payments)
        gas = self.GAS_BATCH_PAYMENT_BASE + len(p) * self.GAS_PER_PAYMENT
        return self._send_transaction(
            self._gntw,
            'batchTransfer',
            [p, closure_time],
            gas,
        )

    def get_batch_tranfers(
            self,
            payer_address: str,
            payee_address: str,
            from_block: int,
            to_block: int) -> List[BatchTransferEvent]:
        filter_id = self._gntw.on(
            'BatchTransfer',
            from_block,
            to_block,
            {'from': payer_address, 'to': payee_address},
        )
        logs = self._geth_client.get_filter_logs(filter_id)

        return [BatchTransferEvent(raw_log) for raw_log in logs]

    def subscribe_to_incoming_batch_transfers(
            self,
            address: str,
            from_block: int,
            cb: Callable[[BatchTransferEvent], None],
            required_confs: int) -> None:
        with self._subs_lock:
            filter_id = self._gntw.on(
                'BatchTransfer',
                from_block,
                'latest',
                {'to': address},
            )
            logs = self._geth_client.get_filter_logs(filter_id)
            for log in logs:
                self._on_filter_log(log, cb, required_confs)
            self._subscriptions.append((filter_id, cb, required_confs))

    def on_transaction_confirmed(
            self,
            tx_hash: str,
            required_confs: int,
            cb: Callable[[TransactionReceipt], None]) -> None:
        with self._awaiting_transactions_lock:
            self._awaiting_transactions.append((tx_hash, required_confs, cb))

    def transfer_gnt(self, to_address: str, amount: int) -> str:
        return self._send_transaction(
            self._gnt,
            'transfer',
            [decode_hex(to_address), amount],
            self.GAS_TRANSFER,
        )

    def transfer_gntw(self, to_address: str, amount: int) -> str:
        return self._send_transaction(
            self._gntw,
            'transfer',
            [decode_hex(to_address), amount],
            self.GAS_TRANSFER,
        )

    def send_transaction(self, tx: Transaction):
        return self._geth_client.send(tx)

    def get_block_number(self) -> int:
        return self._geth_client.get_block_number()

    def get_transaction_receipt(
            self,
            tx_hash: str) -> Optional[TransactionReceipt]:
        raw = self._geth_client.get_transaction_receipt(tx_hash)
        return TransactionReceipt(raw) if raw else None

    def request_gnt_from_faucet(self) -> str:
        return self._send_transaction(
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
        self._monitor_stop.set()

    def _send_transaction(
            self,
            contract,
            function_name,
            args,
            gas_limit):
        tx = contract.create_transaction(
            function_name,
            args,
            self._geth_client.get_transaction_count(self.get_eth_address()),
            self.GAS_PRICE,
            gas_limit,
        )
        self._tx_sign(tx)
        return self._geth_client.send(tx)

    def _monitor_blockchain(self):
        while not self._monitor_stop.is_set():
            try:
                self.wait_until_synchronized()
                self._pull_changes_from_blockchain()
            except Exception as e:
                logger.error(e)
            time.sleep(15)

    def _on_filter_log(self, log, cb, required_confs: int) -> None:
        tx_hash = log['transactionHash']
        if log['removed']:
            del self._awaiting_callbacks[tx_hash]
        else:
            cb_copy = cb
            event = BatchTransferEvent(log)
            logger.info('Detected incoming batch transfer {}, '
                        'waiting for confirmations'.format(event))

            self._awaiting_callbacks[tx_hash] = (
                lambda: cb_copy(event),
                self._cb_id,
                log['blockNumber'] + required_confs,
            )
            self._cb_id += 1

    def _pull_changes_from_blockchain(self) -> None:
        with self._subs_lock:
            subs = self._subscriptions.copy()
        for filter_id, cb, required_confs in subs:
            logs = self._geth_client.get_filter_changes(filter_id)
            for log in logs:
                self._on_filter_log(log, cb, required_confs)

        block_number = self._geth_client.get_block_number()

        if self._awaiting_callbacks:
            to_remove = []
            chronological_callbacks = sorted(
                self._awaiting_callbacks.items(),
                key=lambda v: v[1][1],
            )
            for key, (cb, _, required_block) in chronological_callbacks:
                if block_number >= required_block:
                    try:
                        logger.info('Incoming batch transfer confirmed {}'
                                    .format(key))
                        cb()
                    except Exception as e:
                        logger.error(e)
                    to_remove.append(key)

            for key in to_remove:
                del self._awaiting_callbacks[key]

        self._process_awaiting_transactions(block_number)

    def _process_awaiting_transactions(self, block_number: int) -> None:
        with self._awaiting_transactions_lock:
            awaiting_transactions = self._awaiting_transactions
            self._awaiting_transactions = []

        def processed(awaiting_tx) -> bool:
            tx_hash, required_confs, cb = awaiting_tx
            receipt = self.get_transaction_receipt(tx_hash)
            if not receipt:
                return False
            if receipt.block_number + required_confs < block_number:
                try:
                    cb(receipt)
                except Exception as e:
                    logger.error(e)
                return True
            return False

        remaining_awaiting_transactions = \
            [tx for tx in awaiting_transactions if not processed(tx)]

        with self._awaiting_transactions_lock:
            self._awaiting_transactions.extend(remaining_awaiting_transactions)

    ########################
    # GNT-GNTW conversions #
    ########################

    def create_personal_deposit_slot(self) -> str:
        return self._send_transaction(
            self._gntw,
            'createPersonalDepositAddress',
            [],
            self.GAS_CREATE_PERSONAL_DEPOSIT,
        )

    def get_personal_deposit_slot(self) -> str:
        return self._gntw.call()\
            .getPersonalDepositAddress(decode_hex(self._address))

    def process_personal_deposit_slot(self) -> str:
        return self._send_transaction(
            self._gntw,
            'processDeposit',
            [],
            self.GAS_PROCESS_DEPOSIT,
        )

    def convert_gntw_to_gnt(self, amount: int) -> str:
        raise Exception("Not implemented yet")

    ############################
    # Concent specific methods #
    ############################

    def force_subtask_payment(
            self,
            requestor_address: str,
            provider_address: str,
            value: int,
            subtask_id: str) -> str:
        raise Exception("Not implemented yet")

    def get_forced_subtask_payments(
            self,
            requestor_address: str,
            provider_address: str,
            from_block: int,
            to_block: int) -> List[ForcedSubtaskPaymentEvent]:
        raise Exception("Not implemented yet")

    def force_payment(
            self,
            requestor_address: str,
            provider_address: str,
            value: int,
            closure_time: int) -> str:
        raise Exception("Not implemented yet")

    def get_forced_payments(
            self,
            requestor_address: str,
            provider_address: str,
            from_block: int,
            to_block: int) -> List[ForcedPaymentEvent]:
        raise Exception("Not implemented yet")

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
        raise Exception("Not implemented yet")

    def get_deposit_locked_until(
            self,
            account_address: str) -> Optional[int]:
        raise Exception("Not implemented yet")
