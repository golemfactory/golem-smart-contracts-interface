import atexit
import json
import os
import tempfile
import time
import shutil
import subprocess
from pathlib import Path
from unittest import mock, TestCase

from golem_sci import contracts, Payment, new_sci, GNTConverter
from golem_sci.implementation import SCIImplementation

from web3 import Web3
from web3.middleware import geth_poa_middleware
from web3.providers import IPCProvider
from ethereum.utils import privtoaddr
from eth_utils import encode_hex, denoms, to_checksum_address

ZERO_ADDR = '0x' + 40 * '0'
TEST_RECIPIENT_ADDR = '0x' + 40 * '9'


class MockProvider:
    def __init__(self) -> None:
        self.data = {}

    def get_address(self, contract: str) -> str:
        return self.data[contract]['address']

    def get_abi(self, contract: str) -> str:
        return self.data[contract]['abi']


def privtochecksumaddr(priv):
    return to_checksum_address(encode_hex(privtoaddr(priv)))


class IntegrationTest(TestCase):
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
        self.web3 = Web3(IPCProvider(ipcpath))
        self.web3.middleware_stack.inject(geth_poa_middleware, layer=0)
        while not self.web3.isConnected():
            time.sleep(0.1)

    def _deploy_gnt(self, golem_address: str):
        addr = self.web3.personal.listAccounts[0]

        block_number = self.web3.eth.blockNumber
        from golem_sci.contracts.data.rinkeby import golemnetworktoken
        gnt = self.web3.eth.contract(
            bytecode=golemnetworktoken.BIN,
            abi=json.loads(golemnetworktoken.ABI),
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
        self.provider.data[contracts.GolemNetworkToken] = {
            'address': gnt_address,
            'abi': golemnetworktoken.ABI,
        }
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

        from golem_sci.contracts.data.rinkeby import faucet
        faucet_contract = self.web3.eth.contract(
            bytecode=faucet.BIN,
            abi=json.loads(faucet.ABI),
        )
        faucet_tx = faucet_contract.constructor(gnt_address).transact(
            transaction={'from': addr},
        )
        self._wait_for_pending()
        faucet_address = \
            self.web3.eth.getTransactionReceipt(faucet_tx)['contractAddress']
        self.provider.data[contracts.Faucet] = {
            'address': faucet_address,
            'abi': faucet.ABI,
        }

        gnt.functions.transfer(faucet_address, total_gnt).transact({
            'from': addr,
            'to': gnt_address,
        })

    def _deploy_gntb(self):
        addr = self.web3.personal.listAccounts[0]
        from golem_sci.contracts.data.rinkeby import golemnetworktokenbatching
        gntb = self.web3.eth.contract(
            bytecode=golemnetworktokenbatching.BIN,
            abi=json.loads(golemnetworktokenbatching.ABI),
        )
        gnt_address = self.provider.get_address(contracts.GolemNetworkToken)
        gntb_tx = gntb.constructor(gnt_address).transact(
            transaction={'from': addr},
        )
        self._wait_for_pending()
        gntb_address = \
            self.web3.eth.getTransactionReceipt(gntb_tx)['contractAddress']
        self.provider.data[contracts.GolemNetworkTokenBatching] = {
            'address': gntb_address,
            'abi': golemnetworktokenbatching.ABI,
        }

    def _deploy_concents(self, concent_address: str):
        self.gntdeposit_withdrawal_delay = 7 * 24 * 60 * 60
        addr = self.web3.personal.listAccounts[0]
        from golem_sci.contracts.data.rinkeby import gntdeposit
        gnt_deposit = self.web3.eth.contract(
            bytecode=gntdeposit.BIN,
            abi=json.loads(gntdeposit.ABI),
        )
        gntb_address = \
            self.provider.get_address(contracts.GolemNetworkTokenBatching)
        gnt_deposit_tx = gnt_deposit.constructor(
            gntb_address,
            concent_address,  # oracle
            concent_address,  # coldwallet
            self.gntdeposit_withdrawal_delay,
        ).transact(transaction={'from': addr})
        self._wait_for_pending()
        gntdeposit_address = self.web3.eth.getTransactionReceipt(
            gnt_deposit_tx)['contractAddress']
        self.provider.data[contracts.GNTDeposit] = {
            'address': gntdeposit_address,
            'abi': gntdeposit.ABI,
        }

        # TODO Test GNTPaymentChannels
        self.provider.data[contracts.GNTPaymentChannels] = {
            'address': '0x' + 40 * '3',
            'abi': '[]',
        }

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

        golem_privkey = os.urandom(32)
        concent_privkey = os.urandom(32)
        user_privkey = os.urandom(32)
        golem_address = privtochecksumaddr(golem_privkey)
        concent_address = privtochecksumaddr(concent_privkey)
        user_address = privtochecksumaddr(user_privkey)

        self.provider = MockProvider()

        self._deploy_gnt(golem_address)
        self._deploy_gntb()
        self._deploy_concents(concent_address)

        self._fund_account(concent_address)
        self._fund_account(user_address)
        self._wait_for_pending()
        self._mine_required_blocks()

        with mock.patch('golem_sci.factory._ensure_genesis'), \
                mock.patch('golem_sci.factory.ContractDataProvider') as cdp:
            cdp.return_value = self.provider

            def sign_tx_user(tx):
                tx.sign(user_privkey)
            self.user_sci = new_sci(
                self.tempdir,
                self.web3,
                user_address,
                sign_tx_user,
            )

            def sign_tx_concent(tx):
                tx.sign(concent_privkey)
            self.concent_sci = new_sci(
                self.tempdir2,
                self.web3,
                concent_address,
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

    def test_transfer_eth(self):
        sender = self.user_sci.get_eth_address()
        amount = 2 * denoms.ether
        sender_balance = self.user_sci.get_eth_balance(sender)
        gas_price = 2 * 10 ** 9
        recipient = TEST_RECIPIENT_ADDR
        total_eth = amount + gas_price * 21000
        sender_new_balance = sender_balance - total_eth

        assert sender_balance >= amount
        assert self.user_sci.get_eth_balance(recipient) == 0
        self.user_sci.transfer_eth(recipient, amount, gas_price=gas_price)
        self._wait_for_pending()
        assert self.user_sci.get_eth_balance(sender) == sender_new_balance
        assert self.user_sci.get_eth_balance(recipient) == 0

        self._mine_required_blocks()

        assert self.user_sci.get_eth_balance(sender) == sender_new_balance
        assert self.user_sci.get_eth_balance(recipient) == amount

    def test_estimate_transfer_eth_gas(self):
        cost = self.user_sci.estimate_transfer_eth_gas(
            TEST_RECIPIENT_ADDR,
            denoms.ether,
        )
        assert cost == 21000

    def test_not_enough_eth(self):
        balance = self.user_sci.get_eth_balance(self.user_sci.get_eth_address())
        with self.assertRaisesRegex(Exception, 'Not enough ETH'):
            self.user_sci.transfer_eth(ZERO_ADDR, balance + 1)

    def test_faucet(self):
        user_addr = self.user_sci.get_eth_address()
        assert self.user_sci.get_gnt_balance(user_addr) == 0
        self.user_sci.request_gnt_from_faucet()
        self._wait_for_pending()
        assert self.user_sci.get_gnt_balance(user_addr) == 0
        self._mine_required_blocks()
        assert self.user_sci.get_gnt_balance(user_addr) == 1000 * denoms.ether

    def test_gntdeposit_lock(self):
        self._create_gntb()
        value = 1000 * denoms.ether
        user_addr = self.user_sci.get_eth_address()
        assert self.user_sci.get_deposit_value(user_addr) == 0
        assert self.user_sci.get_deposit_locked_until(user_addr) == 0

        assert self.user_sci.get_deposit_value(user_addr) == 0
        self.user_sci.deposit_payment(value)
        self._mine_required_blocks()
        assert self.user_sci.get_deposit_value(user_addr) == value
        assert self.user_sci.get_gntb_balance(user_addr) == 0

        # can't withdraw if unlocked
        tx_hash = self.user_sci.withdraw_deposit()
        self._wait_for_pending()
        receipt = self.user_sci.get_transaction_receipt(tx_hash)
        assert not receipt.status

        # can't withdraw if just unlocked
        self.user_sci.unlock_deposit()
        self._wait_for_pending()
        tx_hash = self.user_sci.withdraw_deposit()
        self._wait_for_pending()
        receipt = self.user_sci.get_transaction_receipt(tx_hash)
        assert not receipt.status

        """ This needs block timestamp manipulation """
        # can't withdraw if still time locked
        # self._time_travel(self.gntdeposit_withdrawal_delay - 100)
        # tx_hash = self.user_sci.withdraw_deposit()
        # self._wait_for_pending()
        # receipt = self.user_sci.get_transaction_receipt(tx_hash)
        # assert not receipt.status

        # self._time_travel(100)
        # self.user_sci.withdraw_deposit()
        # self._wait_for_pending()
        # assert self.user_sci.get_deposit_value(user_addr) == 0
        # assert self.user_sci.get_gntb_balance(user_addr) == value

    def test_forced_payment(self):
        self._create_gntb()
        requestor = self.user_sci.get_eth_address()
        provider = TEST_RECIPIENT_ADDR
        value = 123
        closure_time = 1337
        self.user_sci.deposit_payment(value)

        from_block = self.user_sci.get_block_number()
        # user can't force a payment
        tx_hash = self.user_sci.force_payment(
            requestor,
            provider,
            value,
            closure_time,
        )
        self._wait_for_pending()
        receipt = self.user_sci.get_transaction_receipt(tx_hash)
        assert not receipt.status

        # only concent can
        self.concent_sci.force_payment(requestor, provider, value, closure_time)
        self._mine_required_blocks()
        assert self.user_sci.get_deposit_value(requestor) == 0
        assert self.user_sci.get_gntb_balance(provider) == value
        to_block = self.user_sci.get_block_number()
        forced_payments = self.user_sci.get_forced_payments(
            requestor,
            provider,
            from_block,
            to_block,
        )

        assert len(forced_payments) == 1
        assert forced_payments[0].requestor == requestor
        assert forced_payments[0].provider == provider
        assert forced_payments[0].amount == value
        assert forced_payments[0].closure_time == closure_time

    def test_forced_subtask_payment(self):
        self._create_gntb()
        requestor = self.user_sci.get_eth_address()
        provider = TEST_RECIPIENT_ADDR
        value = 123
        subtask_id = b'subtask_id' + b'0' * 22
        events = []
        self.user_sci.deposit_payment(value)
        self._wait_for_pending()

        # subtask_id too long
        with self.assertRaisesRegex(ValueError, 'subtask_id has to be exactly'):
            self.concent_sci.force_subtask_payment(
                requestor,
                provider,
                value,
                b'a' * 31,
            )

        from_block = self.user_sci.get_block_number()
        self.user_sci.subscribe_to_forced_subtask_payments(
            None,
            provider,
            from_block,
            lambda e: events.append(e),
        )

        # user can't force a payment
        tx_hash = self.user_sci.force_subtask_payment(
            requestor,
            provider,
            value,
            subtask_id,
        )
        self._wait_for_pending()
        receipt = self.user_sci.get_transaction_receipt(tx_hash)
        assert not receipt.status

        # only concent can
        self.concent_sci.force_subtask_payment(
            requestor,
            provider,
            value,
            subtask_id,
        )
        self._mine_required_blocks()
        assert self.user_sci.get_deposit_value(requestor) == 0
        assert self.user_sci.get_gntb_balance(provider) == value
        to_block = self.user_sci.get_block_number()
        forced_payments = self.user_sci.get_forced_subtask_payments(
            requestor,
            provider,
            from_block,
            to_block,
        )

        assert len(forced_payments) == 1
        assert forced_payments[0].requestor == requestor
        assert forced_payments[0].provider == provider
        assert forced_payments[0].amount == value
        assert forced_payments[0].subtask_id == subtask_id

        assert len(events) == 1
        assert events[0].requestor == requestor
        assert events[0].provider == provider
        assert events[0].amount == value
        assert events[0].subtask_id == subtask_id

    def test_gntb_transfer(self):
        self._create_gntb()
        recipient = TEST_RECIPIENT_ADDR
        assert self.user_sci.get_gntb_balance(recipient) == 0
        amount = 123
        self.user_sci.transfer_gntb(recipient, amount)
        self._wait_for_pending()
        assert self.user_sci.get_gntb_balance(recipient) == 0
        self._mine_required_blocks()
        assert self.user_sci.get_gntb_balance(recipient) == amount

    def test_withdraw_gntb(self):
        self._create_gntb()
        amount = 123
        user_addr = self.user_sci.get_eth_address()
        recipient = TEST_RECIPIENT_ADDR
        self.user_sci.convert_gntb_to_gnt(recipient, amount)
        self._mine_required_blocks()
        assert self.user_sci.get_gntb_balance(user_addr) == \
            1000 * denoms.ether - amount
        assert self.user_sci.get_gnt_balance(recipient) == amount

    def test_on_transaction_confirmed(self):
        recipient = TEST_RECIPIENT_ADDR
        tx_hash = self.user_sci.transfer_eth(recipient, 10)
        receipt = []
        self.user_sci.on_transaction_confirmed(
            tx_hash,
            lambda r: receipt.append(r),
        )
        self._wait_for_pending()
        block_number = self.user_sci.get_block_number()
        self._mine_blocks(SCIImplementation.REQUIRED_CONFS - 2)
        assert len(receipt) == 0
        self._mine_blocks(1)
        assert len(receipt) == 1
        assert tx_hash == receipt[0].tx_hash
        assert receipt[0].status
        assert block_number == receipt[0].block_number

    def test_batch_transfer(self):
        self._create_gntb()
        payee1 = to_checksum_address('0x' + 40 * 'a')
        payee2 = to_checksum_address('0x' + 40 * 'b')
        amount1 = 123
        amount2 = 234
        closure_time = 555

        payment1 = Payment(payee1, amount1)
        payment2 = Payment(payee2, amount2)

        from_block = self.user_sci.get_block_number()
        events_incoming = []
        events_outgoing = []
        self.user_sci.subscribe_to_batch_transfers(
            None,
            payee1,
            from_block,
            lambda e: events_incoming.append(e),
        )
        self.user_sci.subscribe_to_batch_transfers(
            self.user_sci.get_eth_address(),
            None,
            from_block,
            lambda e: events_outgoing.append(e),
        )

        tx_hash = self.user_sci.batch_transfer(
            [payment1, payment2],
            closure_time,
        )
        self._wait_for_pending()
        assert len(events_incoming) == 0
        assert len(events_outgoing) == 0
        to_block = self.user_sci.get_block_number()

        batch_transfers1 = self.user_sci.get_batch_transfers(
            self.user_sci.get_eth_address(),
            payee1,
            from_block,
            to_block,
        )
        assert len(batch_transfers1) == 1
        assert batch_transfers1[0].tx_hash == tx_hash
        assert batch_transfers1[0].amount == amount1
        assert batch_transfers1[0].sender == self.user_sci.get_eth_address()
        assert batch_transfers1[0].receiver == payee1
        assert batch_transfers1[0].closure_time == closure_time

        batch_transfers2 = self.user_sci.get_batch_transfers(
            self.user_sci.get_eth_address(),
            payee2,
            from_block,
            to_block,
        )
        assert len(batch_transfers2) == 1
        assert batch_transfers2[0].tx_hash == tx_hash
        assert batch_transfers2[0].amount == amount2
        assert batch_transfers2[0].sender == self.user_sci.get_eth_address()
        assert batch_transfers2[0].receiver == payee2
        assert batch_transfers2[0].closure_time == closure_time

        self._mine_required_blocks()
        assert self.user_sci.get_gntb_balance(payee1) == amount1
        assert self.user_sci.get_gntb_balance(payee2) == amount2

        assert len(events_incoming) == 1
        assert tx_hash == events_incoming[0].tx_hash
        assert self.user_sci.get_eth_address() == events_incoming[0].sender
        assert payee1 == events_incoming[0].receiver
        assert amount1 == events_incoming[0].amount
        assert closure_time == events_incoming[0].closure_time

        assert len(events_outgoing) == 2
        assert tx_hash == events_outgoing[0].tx_hash
        assert self.user_sci.get_eth_address() == events_outgoing[0].sender
        assert payee1 == events_outgoing[0].receiver
        assert amount1 == events_outgoing[0].amount
        assert closure_time == events_outgoing[0].closure_time
        assert tx_hash == events_outgoing[1].tx_hash
        assert self.user_sci.get_eth_address() == events_outgoing[1].sender
        assert payee2 == events_outgoing[1].receiver
        assert amount2 == events_outgoing[1].amount
        assert closure_time == events_outgoing[1].closure_time

    def test_gnt_converter(self):
        addr = self.user_sci.get_eth_address()
        assert self.user_sci.get_gnt_balance(addr) == 0
        self.user_sci.request_gnt_from_faucet()
        self._wait_for_pending()
        assert self.user_sci.get_gnt_balance(addr) == 0
        gnt = 1000 * denoms.ether
        self._mine_required_blocks()
        assert self.user_sci.get_gnt_balance(addr) == gnt

        assert self.user_sci.get_gate_address() is None
        converter = GNTConverter(self.user_sci)
        amount = 600 * denoms.ether
        converter.convert(amount)

        self._mine_required_blocks()
        assert self.user_sci.get_gate_address() is not None
        assert converter.is_converting()
        assert converter.get_gate_balance() == 0

        self._mine_required_blocks()
        assert converter.is_converting()
        assert self.user_sci.get_gnt_balance(addr) == gnt - amount
        assert converter.get_gate_balance() == amount

        self._mine_required_blocks()
        assert not converter.is_converting()
        assert converter.get_gate_balance() == 0
        assert self.user_sci.get_gntb_balance(addr) == amount

    def test_remove_tx_from_storage(self):
        assert len(self.user_sci._storage.get_all_tx()) == 0
        self.user_sci.transfer_eth(ZERO_ADDR, 1)
        assert len(self.user_sci._storage.get_all_tx()) == 1
        self._mine_required_blocks()
        assert len(self.user_sci._storage.get_all_tx()) == 0

    def test_lost_connection_to_geth(self):
        assert len(self.user_sci._storage.get_all_tx()) == 0
        self.proc.kill()
        self.user_sci.get_eth_balance = mock.Mock(return_value=9 * denoms.ether)
        self.user_sci.estimate_transfer_eth_gas = mock.Mock(return_value=21000)
        self.user_sci.transfer_eth(ZERO_ADDR, 1)
        assert len(self.user_sci._storage.get_all_tx()) == 1
        self._spawn_geth_process()
        with mock.patch('golem_sci.factory._ensure_genesis'), \
                mock.patch('golem_sci.factory.ContractDataProvider') as cdp:
            cdp.return_value = self.provider

            self.web3.eth.getTransactionCount = mock.Mock(return_value=1)
            self.user_sci = new_sci(
                self.tempdir,
                self.web3,
                self.user_sci.get_eth_address(),
            )
            self.concent_sci = None
        self._fund_account(self.user_sci.get_eth_address())
        self._wait_for_pending()
        assert len(self.user_sci._storage.get_all_tx()) == 1
        self._mine_required_blocks()
        assert len(self.user_sci._storage.get_all_tx()) == 0
