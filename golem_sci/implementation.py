import logging
import threading
import time
from typing import Any, Dict, List, Optional

from ethereum.transactions import Transaction

from .interface import SmartContractsInterface, BatchTransferEvent

logger = logging.getLogger("golem_sci.implementation")


class SCIImplementation(SmartContractsInterface):
    def __init__(self, geth_client, token, monitor=True):
        self._geth_client = geth_client
        self._token = token

        self.GAS_PRICE = self._token.GAS_PRICE
        self.GAS_PER_PAYMENT = self._token.GAS_PER_PAYMENT
        self.GAS_BATCH_PAYMENT_BASE = self._token.GAS_BATCH_PAYMENT_BASE

        self._subs_lock = threading.Lock()
        self._subscriptions = []

        self._awaiting_callbacks = {}

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
            cb: callable(BatchTransferEvent),
            required_confs: int) -> None:
        with self._subs_lock:
            filter_id = self._geth_client.new_filter(
                address=self._token.GNTW_ADDRESS,
                topics=[self._token.TRANSFER_EVENT_ID, None, address],
            )
            self._subscriptions.append((filter_id, cb, required_confs))

    def send_transaction(self, tx: Transaction):
        return self._geth_client.send(tx)

    def get_block_number(self) -> int:
        return self._geth_client.get_block_number()

    def get_transaction_receipt(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        return self._geth_client.get_transaction_receipt(tx_hash)

    def get_incomes_from_block(self, block: int, address: str) -> List[Any]:
        return self._token.get_incomes_from_block(block, address)

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

    def _pull_changes_from_blockchain(self) -> None:
        with self._subs_lock:
            subs = self._subscriptions
        for filter_id, cb, required_confs in subs:
            changes = self._geth_client.get_filter_changes(filter_id)
            for change in changes:
                tx_hash = change['transactionHash']
                if change['removed']:
                    del self._awaiting_callbacks[tx_hash]
                else:
                    cb_copy = cb
                    event = self._raw_log_to_batch_event(change)
                    logger.info('Detected incoming batch transfer {}, '
                                'waiting for confirmations'.format(event))

                    def callback():
                        cb_copy(event)
                    self._awaiting_callbacks[tx_hash] = \
                        (callback, change['blockNumber'] + required_confs)

        if self._awaiting_callbacks:
            block_number = self._geth_client.get_block_number()
            to_remove = []
            for key, (cb, required_block) in self._awaiting_callbacks.items():
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
