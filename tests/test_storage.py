import os
import tempfile
import unittest
from pathlib import Path

from ethereum.transactions import Transaction

from golem_sci.transactionsstorage import JsonTransactionsStorage


def _make_signed_tx(nonce: int):
    tx = Transaction(
        startgas=21000,
        gasprice=10**9,
        value=10,
        to='0x' + 40 * '0',
        data=b'',
        nonce=nonce,
    )
    tx.sign(os.urandom(32))
    return tx


class TransactionsStorageTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = Path(tempfile.mkdtemp())
        self.storage = JsonTransactionsStorage(self.tempdir, 0)

    def test_wrong_tx_nonce(self):
        assert self.storage.get_nonce() == 0
        with self.assertRaisesRegex(Exception, 'nonce does not match'):
            self.storage.put_tx_and_inc_nonce(_make_signed_tx(1))

    def test_put_get_remove(self):
        tx = _make_signed_tx(0)
        self.storage.put_tx_and_inc_nonce(tx)
        assert self.storage.get_nonce() == 1
        transactions = self.storage.get_all_tx()
        assert len(transactions) == 1
        assert transactions[0] == tx

        self.storage.remove_tx(0)
        assert self.storage.get_nonce() == 1
        transactions = self.storage.get_all_tx()
        assert len(transactions) == 0

    def test_reload(self):
        tx = _make_signed_tx(0)
        self.storage.put_tx_and_inc_nonce(tx)
        self.storage = JsonTransactionsStorage(self.tempdir, 1)
        assert self.storage.get_nonce() == 1
        transactions = self.storage.get_all_tx()
        assert len(transactions) == 1
        assert transactions[0] == tx

        self.storage.remove_tx(0)
        self.storage = JsonTransactionsStorage(self.tempdir, 1)
        assert self.storage.get_nonce() == 1
        transactions = self.storage.get_all_tx()
        assert len(transactions) == 0

    def test_wrong_inital_nonce(self):
        with self.assertRaisesRegex(Exception, 'initialization failed'):
            self.storage = JsonTransactionsStorage(self.tempdir, 1)
