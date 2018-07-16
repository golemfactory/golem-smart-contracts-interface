import os
import shutil
import tempfile
import unittest
from pathlib import Path

from ethereum.transactions import Transaction

from golem_sci.transactionsstorage import JsonTransactionsStorage


def _make_tx() -> Transaction:
    return Transaction(
        startgas=21000,
        gasprice=10**9,
        value=10,
        to='0x' + 40 * '0',
        data=b'',
        nonce=0,
    )


def _sign(tx: Transaction) -> None:
    tx.sign(os.urandom(32))


class JsonTransactionsStorageTest(unittest.TestCase):
    def setUp(self):
        self.tempfile = Path(tempfile.mkdtemp()) / 'tx.json'
        self.storage = JsonTransactionsStorage(self.tempfile)
        self.storage.init(0)

    def tearDown(self):
        shutil.rmtree(self.tempfile.parent)

    def test_put_get_remove(self):
        tx = _make_tx()
        self.storage.set_nonce_sign_and_save_tx(_sign, tx)
        transactions = self.storage.get_all_tx()
        assert len(transactions) == 1
        assert transactions[0] == tx
        assert tx.nonce == 0

        self.storage.remove_tx(0)
        transactions = self.storage.get_all_tx()
        assert len(transactions) == 0

    def test_nonce_increment(self):
        tx1 = _make_tx()
        tx2 = _make_tx()
        self.storage.set_nonce_sign_and_save_tx(_sign, tx1)
        self.storage.set_nonce_sign_and_save_tx(_sign, tx2)
        assert tx1.nonce == 0
        assert tx2.nonce == 1

    def test_reload(self):
        tx = _make_tx()
        self.storage.set_nonce_sign_and_save_tx(_sign, tx)
        self.storage = JsonTransactionsStorage(self.tempfile)
        self.storage.init(1)
        transactions = self.storage.get_all_tx()
        assert len(transactions) == 1
        assert transactions[0] == tx
        assert tx.nonce == 0

        self.storage.remove_tx(0)
        self.storage = JsonTransactionsStorage(self.tempfile)
        self.storage.init(1)
        transactions = self.storage.get_all_tx()
        assert len(transactions) == 0

    def test_wrong_inital_nonce(self):
        self.storage = JsonTransactionsStorage(self.tempfile)
        with self.assertRaisesRegex(Exception, 'initialization failed'):
            self.storage.init(1)

    def test_sign_throws(self):
        def sign_throws(tx: Transaction) -> None:
            raise Exception('sign exception')
        tx = _make_tx()
        with self.assertRaisesRegex(Exception, 'sign exception'):
            self.storage.set_nonce_sign_and_save_tx(sign_throws, tx)
        transactions = self.storage.get_all_tx()
        assert len(transactions) == 0
