import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from ethereum.transactions import Transaction

from .interface import SmartContractsInterface, BatchTransferEvent

logger = logging.getLogger("golem_sci.implementation")


class SCIImplementation(SmartContractsInterface):
    def __init__(self, geth_client, token, address, tx_sign=None, monitor=True):
        """
        Performs all blockchain operations using the address as the caller.
        Uses tx_sign to sign outgoing transaction, tx_sign can be None in which
        case one may only perform read only operations.
        """
        self._geth_client = geth_client
        self._token = token
        self._address = address
        self._tx_sign = tx_sign

        self.GAS_PRICE = self._token.GAS_PRICE
        self.GAS_PER_PAYMENT = self._token.GAS_PER_PAYMENT
        self.GAS_BATCH_PAYMENT_BASE = self._token.GAS_BATCH_PAYMENT_BASE

        self._subs_lock = threading.Lock()
        self._subscriptions = []

        self._awaiting_callbacks = {}
        self._cb_id = 0

        if monitor:
            thread = threading.Thread(target=self._monitor_blockchain)
            thread.daemon = True
            thread.start()

    def get_eth_balance(self, address: str) -> Optional[int]:
        """
        Returns None is case of issues coming from the geth client
        """
        return self._geth_client.get_balance(address)

    def get_gnt_balance(self, address: str) -> Optional[int]:
        return self._token.get_gnt_balance(address)

    def get_gntw_balance(self, address: str) -> Optional[int]:
        return self._token.get_gntw_balance(address)

    def batch_transfer(self, payments, closure_time: int) -> str:
        raise Exception("Not implemented yet")

    def prepare_batch_transfer(self,
                               privkey: bytes,
                               payments,
                               closure_time: int) -> Transaction:
        return self._token.batch_transfer(privkey, payments, closure_time)

    def get_incoming_batch_tranfers(
            self,
            payer_address: str,
            payee_address: str,
            from_block: int,
            to_block: int) -> List[BatchTransferEvent]:
        logs = self._geth_client.get_logs(
            from_block=from_block,
            to_block=to_block,
            address=self._token.GNTW_ADDRESS,
            topics=[self._token.TRANSFER_EVENT_ID, payer_address, payee_address]
        )

        return [self._raw_log_to_batch_event(raw_log) for raw_log in logs]

    def subscribe_to_incoming_batch_transfers(
            self,
            address: str,
            from_block: int,
            cb: Callable[[BatchTransferEvent], None],
            required_confs: int) -> None:
        with self._subs_lock:
            filter_id = self._geth_client.new_filter(
                address=self._token.GNTW_ADDRESS,
                topics=[self._token.TRANSFER_EVENT_ID, None, address],
                from_block=from_block,
                to_block='latest',
            )
            logs = self._geth_client.get_filter_logs(filter_id)
            for log in logs:
                self._on_filter_log(log, cb, required_confs)
            self._subscriptions.append((filter_id, cb, required_confs))

    def send_transaction(self, tx: Transaction):
        return self._geth_client.send(tx)

    def get_block_number(self) -> int:
        return self._geth_client.get_block_number()

    def get_transaction_receipt(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        return self._geth_client.get_transaction_receipt(tx_hash)

    def request_gnt_from_faucet(self, privkey: bytes) -> None:
        self._token.request_from_faucet(privkey)

    def wait_until_synchronized(self) -> bool:
        return self._geth_client.wait_until_synchronized()

    def is_synchronized(self) -> bool:
        return self._geth_client.is_synchronized()

    def _monitor_blockchain(self):
        while True:
            try:
                self.wait_until_synchronized()
                self._pull_changes_from_blockchain()
            except Exception as e:
                logger.error(e)
            time.sleep(15)

    @classmethod
    def _raw_log_to_batch_event(cls, raw_log) -> BatchTransferEvent:
        return BatchTransferEvent(
            tx_hash=raw_log['transactionHash'],
            sender='0x' + raw_log['topics'][1][26:],
            amount=int(raw_log['data'][2:66], 16),
            closure_time=int(raw_log['data'][66:130], 16),
        )

    def _on_filter_log(self, log, cb, required_confs: int) -> None:
        tx_hash = log['transactionHash']
        if log['removed']:
            del self._awaiting_callbacks[tx_hash]
        else:
            cb_copy = cb
            event = self._raw_log_to_batch_event(log)
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

        if self._awaiting_callbacks:
            block_number = self._geth_client.get_block_number()
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

    def force_batch_payment(
            self,
            requestor_address: str,
            provider_address: str,
            value: int,
            closure_time: int) -> str:
        raise Exception("Not implemented yet")

    def cover_additional_verification_cost(
            self,
            client_address: str,
            value: int,
            subtask_id: str) -> str:
        raise Exception("Not implemented yet")

    def get_deposit_value(
            self,
            account_address: str) -> Optional[int]:
        raise Exception("Not implemented yet")

    def get_deposit_locked_until(
            self,
            account_address: str) -> Optional[int]:
        raise Exception("Not implemented yet")
