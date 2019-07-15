import atexit
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from unittest import mock, TestCase

from eth_utils import encode_hex, denoms, to_checksum_address
from ethereum.utils import privtoaddr
from web3 import Web3
from web3.middleware import geth_poa_middleware
from web3.providers import IPCProvider

from golem_sci import (
    contracts,
    new_sci,
    JsonTransactionsStorage,
)
from golem_sci.implementation import SCIImplementation

from . import contract_bin

ZERO_ADDR = '0x' + 40 * '0'
TEST_RECIPIENT_ADDR = '0x' + 40 * '9'


def privtochecksumaddr(priv):
    return to_checksum_address(encode_hex(privtoaddr(priv)))


class IntegrationBase(TestCase):
    def _wait_for_pending(self) -> None:
        while int(self.web3.txpool.status['pending'], 16) > 0:
            time.sleep(0.01)
        if self.user_sci:
            self.user_sci._monitor_blockchain_single()
        if self.concent_sci:
            self.concent_sci._monitor_blockchain_single()

    def _mine_blocks(self, num: int = 1) -> None:
        for i in range(num):
            self._fund_account(ZERO_ADDR, 0)
            self._wait_for_pending()

    def _mine_required_blocks(self) -> None:
        self._mine_blocks(SCIImplementation.REQUIRED_CONFS)

    def _spawn_geth_process(self):
        ipcpath = tempfile.mkstemp(suffix='.ipc')[1]
        proc = subprocess.Popen(
            ['geth', '--dev', '-ipcpath={}'.format(ipcpath)],
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        atexit.register(lambda: proc.kill())
        self.proc = proc
        self.web3 = Web3(IPCProvider(ipcpath, timeout=60))
        self.web3.middleware_stack.inject(geth_poa_middleware, layer=0)
        while not self.web3.isConnected():
            time.sleep(0.1)

    def _deploy_gnt(self, golem_address: str):
        addr = self.web3.personal.listAccounts[0]

        block_number = self.web3.eth.blockNumber
        gnt = self.web3.eth.contract(
            bytecode=contract_bin.GNT,
            abi=json.loads(contracts.get_abi(contracts.GNT)),
        )
        gnt_tx = gnt.constructor(
            golem_address,
            golem_address,
            block_number + 2,
            block_number + 3,
        ).transact(transaction={'from': addr})
        self._wait_for_pending()
        gnt_address = \
            self.web3.eth.getTransactionReceipt(gnt_tx)['contractAddress']
        self.contract_addresses[contracts.GNT] = gnt_address
        gnt.functions.create().transact({
            'from': addr,
            'value': 2 * 10 ** 16,
            'to': gnt_address,
        })
        gnt.functions.create().transact({
            'from': addr,
            'value': 2 * 10 ** 16,
            'to': gnt_address,
        })
        total_gnt = gnt.functions.totalSupply().call({
            'from': addr,
            'to': gnt_address,
        })
        gnt.functions.finalize().transact({
            'from': addr,
            'to': gnt_address,
        })

        faucet_contract = self.web3.eth.contract(
            bytecode=contract_bin.Faucet,
            abi=json.loads(contracts.get_abi(contracts.Faucet)),
        )
        faucet_tx = faucet_contract.constructor(gnt_address).transact(
            transaction={'from': addr},
        )
        self._wait_for_pending()
        faucet_address = \
            self.web3.eth.getTransactionReceipt(faucet_tx)['contractAddress']
        self.contract_addresses[contracts.Faucet] = faucet_address

        gnt.functions.transfer(faucet_address, total_gnt).transact({
            'from': addr,
            'to': gnt_address,
        })

    def _deploy_gntb(self):
        addr = self.web3.personal.listAccounts[0]
        gntb = self.web3.eth.contract(
            bytecode=contract_bin.GNTB,
            abi=json.loads(contracts.get_abi(contracts.GNTB)),
        )
        gnt_address = self.contract_addresses[contracts.GNT]
        gntb_tx = gntb.constructor(gnt_address).transact(
            transaction={'from': addr},
        )
        self._wait_for_pending()
        gntb_address = \
            self.web3.eth.getTransactionReceipt(gntb_tx)['contractAddress']
        self.contract_addresses[contracts.GNTB] = gntb_address

    def _deploy_concent(self, concent_address: str, golem_privkey: bytes):
        self.gntdeposit_withdrawal_delay = 7 * 24 * 60 * 60
        gnt_deposit = self.web3.eth.contract(
            bytecode=contract_bin.GNTDeposit,
            abi=json.loads(contracts.get_abi(contracts.GNTDeposit)),
        )
        gntb_address = self.contract_addresses[contracts.GNTB]
        gnt_deposit_tx = gnt_deposit.constructor(
            gntb_address,
            concent_address,  # concent
            concent_address,  # coldwallet
            self.gntdeposit_withdrawal_delay,
        ).buildTransaction()
        gnt_deposit_tx['nonce'] = \
            self.web3.eth.getTransactionCount(privtochecksumaddr(golem_privkey))
        # Different nonce will generate different contract address
        assert gnt_deposit_tx['nonce'] == 0
        signed_tx = \
            self.web3.eth.account.signTransaction(gnt_deposit_tx, golem_privkey)
        tx_hash = self.web3.eth.sendRawTransaction(signed_tx.rawTransaction)
        self._wait_for_pending()
        gntdeposit_address = self.web3.eth.getTransactionReceipt(
            tx_hash)['contractAddress']
        self.contract_addresses[contracts.GNTDeposit] = gntdeposit_address

    def _fund_account(
            self,
            address: str,
            amount: int = 100 * denoms.ether) -> None:
        from_addr = self.web3.personal.listAccounts[0]
        self.web3.eth.sendTransaction({
            'from': from_addr,
            'to': address,
            'value': amount,
            'gas': 21000,
        })

    def tearDown(self):
        self.proc.kill()
        shutil.rmtree(self.tempdir)
        shutil.rmtree(self.tempdir2)

    def setUp(self):
        self.user_sci = None
        self.concent_sci = None

        self._spawn_geth_process()

        self.tempdir = Path(tempfile.mkdtemp())
        self.tempdir2 = Path(tempfile.mkdtemp())

        # random keys
        golem_privkey = b"2M\xf1\x8c}\xc3%B\xda\xa2\x85\x9c\x14\xba\xe5@\xefq\xeaM'q\xbc!\x97^\xc8\x1b\x1b\x89\x93\x7f"  # noqa
        concent_privkey = b't\xddGX\xd0\x84\x9c\xf4\xeeYV,\xd9\xab\xd9\xbd\xa3\xa4\xc8\xe4Hr\x9b\xdc4\n\xe7N}MF\x8b'  # noqa
        self.user_privkey = b'\xc5!\xc1\x91A\x15I]\xd2~\xf4\x1f\xf7a|\xd2\x9d\xcd\xea-\x1f\xde\xbaU\x9dh:Vv!H\xb9'  # noqa
        golem_address = privtochecksumaddr(golem_privkey)
        concent_address = privtochecksumaddr(concent_privkey)
        user_address = privtochecksumaddr(self.user_privkey)

        self.contract_addresses = {}

        self._deploy_gnt(golem_address)
        self._deploy_gntb()
        self._deploy_concent(concent_address, golem_privkey)

        self._fund_account(concent_address)
        self._fund_account(user_address)
        self._wait_for_pending()
        self._mine_required_blocks()

        with mock.patch('golem_sci.factory._ensure_genesis'), \
                mock.patch('golem_sci.implementation.threading'):
            def sign_tx_user(tx):
                tx.sign(self.user_privkey)
            self.user_sci = new_sci(
                self.web3,
                user_address,
                'test_chain',
                JsonTransactionsStorage(self.tempdir / 'user_tx.json'),
                self.contract_addresses,
                sign_tx_user,
            )

            def sign_tx_concent(tx):
                tx.sign(concent_privkey)
            self.concent_sci = new_sci(
                self.web3,
                concent_address,
                'test_chain',
                JsonTransactionsStorage(self.tempdir2 / 'concent_tx.json'),
                self.contract_addresses,
                sign_tx_concent,
            )

    def _create_gntb(self):
        amount = 1000 * denoms.ether
        self.user_sci.request_gnt_from_faucet()
        gate_addr = self.user_sci.get_gate_address()
        assert gate_addr is None
        self.user_sci.open_gate()
        self._mine_required_blocks()
        gate_addr = self.user_sci.get_gate_address()
        assert gate_addr is not None and gate_addr != ZERO_ADDR
        self.user_sci.transfer_gnt(gate_addr, amount)
        self._mine_required_blocks()
        assert self.user_sci.get_gnt_balance(gate_addr) == amount
        self.user_sci.transfer_from_gate()
        self._mine_required_blocks()
        assert self.user_sci.get_gntb_balance(self.user_sci.get_eth_address()) \
            == amount
