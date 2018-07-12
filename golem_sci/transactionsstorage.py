import json
import logging
import os

from abc import abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, List

from eth_utils import decode_hex, encode_hex
from ethereum.transactions import Transaction
from hexbytes import HexBytes

logger = logging.getLogger(__name__)


class TransactionsStorage:
    def init(self, network_nonce: int) -> None:
        if not self._is_storage_initialized():
            self._init_with_nonce(network_nonce)
            return

        if self._get_nonce() < network_nonce:
            raise Exception(
                'TransactionStorage initialization failed. Has '
                'nonce={} while network_nonce is={}'.format(
                    self._get_nonce(), network_nonce))

    @abstractmethod
    def get_all_tx(self) -> List[Transaction]:
        """
        Returns the list of all transactions.
        """
        pass

    @abstractmethod
    def set_nonce_sign_and_save_tx(
            self,
            sign_tx: Callable[[Transaction], None],
            tx: Transaction) -> None:
        """
        Sets the next nonce for the transaction, invokes the callback for
        signing and saves it to the storage.
        """
        pass

    @abstractmethod
    def remove_tx(self, nonce: int) -> None:
        """
        Remove the transaction after it's been confirmed and doesn't have
        to be tracked anymore.
        """
        pass

    @abstractmethod
    def revert_last_tx(self) -> None:
        """
        Remove the last transaction that was added.
        This shouldn't be ever called if everything is being used correctly,
        i.e. we don't try to send invalid transactions.
        """
        pass

    @abstractmethod
    def _is_storage_initialized(self) -> bool:
        """
        Should return False if this is the first time we try to use this
        storage.
        """
        pass

    @abstractmethod
    def _init_with_nonce(self, nonce: int) -> None:
        """
        Should initialize the storage and set the starting nonce.
        """
        pass

    @abstractmethod
    def _get_nonce(self) -> int:
        """
        Return current nonce.
        """
        pass


class JsonTransactionsStorage(TransactionsStorage):
    def __init__(self, filepath: Path) -> None:
        self._filepath = filepath
        self._data: Dict[str, Any] = {}
        if self._filepath.exists():
            with open(self._filepath) as f:
                self._data = json.load(f)
            if 'tx' in self._data:
                self._data['tx'] = \
                    {int(nonce): tx for nonce, tx in self._data['tx'].items()}

    def _is_storage_initialized(self) -> bool:
        return 'nonce' in self._data

    def _init_with_nonce(self, nonce: int) -> None:
        logger.info(
            'Initiating JsonTransactionStorage with nonce=%d',
            nonce,
        )
        self._data['nonce'] = nonce
        self._data['tx'] = {}
        self._save(self._data)

    def _get_nonce(self) -> int:
        return self._data['nonce']

    def get_all_tx(self) -> List[Transaction]:
        def convert(tx):
            return Transaction(
                nonce=tx['nonce'],
                gasprice=tx['gasprice'],
                startgas=tx['startgas'],
                to=tx['to'],
                value=tx['value'],
                data=decode_hex(tx['data']),
                v=tx['v'],
                r=tx['r'],
                s=tx['s'],
            )
        return [convert(tx) for tx in self._data['tx'].values()]

    def set_nonce_sign_and_save_tx(
            self,
            sign_tx: Callable[[Transaction], None],
            tx: Transaction) -> None:
        tx.nonce = self._data['nonce']
        sign_tx(tx)
        logger.info(
            'Saving transaction %s, nonce=%d',
            encode_hex(tx.hash),
            tx.nonce,
        )
        # Use temporary copy because we don't want to modify the state if
        # writing to the file fails
        new_data = dict(self._data)
        new_data['nonce'] = tx.nonce + 1
        new_data['tx'][tx.nonce] = {
            'nonce': tx.nonce,
            'gasprice': tx.gasprice,
            'startgas': tx.startgas,
            'to': HexBytes(tx.to).hex(),
            'value': tx.value,
            'data': HexBytes(tx.data).hex(),
            'v': tx.v,
            'r': tx.r,
            's': tx.s,
        }
        self._save(new_data)
        self._data = new_data

    def remove_tx(self, nonce: int) -> None:
        logger.info('Removing transaction nonce=%d', nonce)
        new_data = dict(self._data)
        del new_data['tx'][nonce]
        self._save(new_data)
        self._data = new_data

    def revert_last_tx(self) -> None:
        new_data = dict(self._data)
        new_data['nonce'] -= 1
        del new_data['tx'][new_data['nonce']]
        self._save(new_data)
        self._data = new_data

    def _save(self, data: Dict) -> None:
        with open(self._filepath, 'w') as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
