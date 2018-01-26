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

    def subscribe_to_incoming_batch_transfers(
            self,
            address: str,
            cb: callable(BatchTransferEvent),
            required_confs: int) -> None:
        with self._subs_lock:
            filter_id = \
                self._token.get_incoming_batch_transfers_filter(address)
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
                    event = BatchTransferEvent(
                        tx_hash=tx_hash,
                        sender='0x' + change['topics'][1][26:],
                        amount=int(change['data'][2:66], 16),
                        closure_time=int(change['data'][66:130], 16),
                    )
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
