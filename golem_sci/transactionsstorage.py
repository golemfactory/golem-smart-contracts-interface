import json
import logging
import os

from abc import abstractmethod
from pathlib import Path
from typing import ClassVar, Dict, List

from eth_utils import decode_hex, encode_hex
from ethereum.transactions import Transaction
from hexbytes import HexBytes

logger = logging.getLogger(__name__)


class TransactionsStorage:
    @abstractmethod
    def get_nonce(self) -> int:
        """
        Returns the nonce for the next transaction.
        """
        pass

    @abstractmethod
    def get_all_tx(self) -> List[Transaction]:
        """
        Returns the list of all transactions.
        """
        pass

    @abstractmethod
    def put_tx_and_inc_nonce(self, tx: Transaction) -> None:
        """
        Save a valid transaction and increase the nonce.
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


class JsonTransactionsStorage(TransactionsStorage):
    FILENAME: ClassVar[str] = 'transactions.json'

    def __init__(self, datadir: Path, nonce: int) -> None:
        self._filepath = datadir / self.FILENAME
        self._data = {}
        if self._filepath.exists():
            with open(self._filepath) as f:
                self._data = json.load(f)
            if 'tx' in self._data:
                self._data['tx'] = \
                    {int(nonce): tx for nonce, tx in self._data['tx'].items()}
        if 'nonce' not in self._data:
            logger.info('Initiating TransactionStorage with nonce=%d', nonce)
            self._data['nonce'] = nonce
            self._data['tx'] = {}
            self._save(self._data)
        elif self._data['nonce'] < nonce:
            raise Exception(
                'TransactionStorage initialization failed. Found '
                'nonce={} while current nonce is={}'.format(
                    self._data['nonce'], nonce))

    def get_nonce(self) -> int:
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

    def put_tx_and_inc_nonce(self, tx: Transaction) -> None:
        if tx.nonce != self._data['nonce']:
            raise Exception(
                'Transaction nonce does not match. Current={}, tx={}'.format(
                    self._data['nonce'], tx.nonce))
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
