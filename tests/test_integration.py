import atexit
import json
import os
import subprocess
import tempfile
import time
from unittest import mock, TestCase

from golem_sci import contracts
from golem_sci.factory import new_sci

from web3 import Web3
from web3.middleware import geth_poa_middleware
from web3.providers import IPCProvider
from ethereum.utils import privtoaddr
from eth_utils import encode_hex, denoms, to_checksum_address


def mock_payment(payee: str, amount: int):
    payment = mock.Mock()
    payment.payee = payee
    payment.amount = amount
    return payment


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

    def _fund_account(self, address: str) -> None:
        from_addr = self.web3.personal.listAccounts[0]
        self.web3.eth.sendTransaction({
            'from': from_addr,
            'to': address,
            'value': 100 * denoms.ether,
            'gas': 21000,
        })

    def tearDown(self):
        self.proc.kill()

    def setUp(self):
        ipcpath = tempfile.mkstemp(suffix='ipc')[1]
        proc = subprocess.Popen(
            ['geth', '--dev', '-ipcpath={}'.format(ipcpath)],
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.proc = proc
        atexit.register(lambda: proc.kill())
        self.web3 = Web3(IPCProvider(ipcpath))
        self.web3.middleware_stack.inject(geth_poa_middleware, layer=0)
        while not self.web3.isConnected():
            time.sleep(0.1)

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

        with mock.patch('golem_sci.factory._ensure_genesis'), \
                mock.patch('golem_sci.factory.ContractDataProvider') as cdp:
            cdp.return_value = self.provider

            def sign_tx_user(tx):
                tx.sign(user_privkey)
            self.user_sci = new_sci(self.web3, user_address, sign_tx_user)

            def sign_tx_concent(tx):
                tx.sign(concent_privkey)
            self.concent_sci = new_sci(
                self.web3,
                concent_address,
                sign_tx_concent,
            )

    def _create_gntb(self):
        self.user_sci.request_gnt_from_faucet()
        self.user_sci.open_gate()
        self._wait_for_pending()
        pda = self.user_sci.get_gate_address()
        self.user_sci.transfer_gnt(pda, 1000 * denoms.ether)
        self._wait_for_pending()
        self.user_sci.transfer_from_gate()
        self._wait_for_pending()
        assert self.user_sci.get_gntb_balance(self.user_sci.get_eth_address()) \
            == 1000 * denoms.ether

    def test_transfer_eth(self):
        recipient = to_checksum_address('0x' + 40 * 'e')
        assert self.user_sci.get_eth_balance(recipient) == 0
        amount = 2137
        self.user_sci.transfer_eth(recipient, amount)
        assert self.user_sci.get_eth_balance(recipient) == amount

    def test_faucet(self):
        user_addr = self.user_sci.get_eth_address()
        assert self.user_sci.get_gnt_balance(user_addr) == 0
        self.user_sci.request_gnt_from_faucet()
        assert self.user_sci.get_gnt_balance(user_addr) == 1000 * denoms.ether

    def test_gntdeposit_lock(self):
        self._create_gntb()
        value = 1000 * denoms.ether
        user_addr = self.user_sci.get_eth_address()
        assert self.user_sci.get_deposit_value(user_addr) == 0
        assert self.user_sci.get_deposit_locked_until(user_addr) == 0

        self.user_sci.deposit_payment(value)
        self._wait_for_pending()
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
        provider = to_checksum_address('0x' + 40 * 'b')
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
        self._wait_for_pending()
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
        provider = to_checksum_address('0x' + 40 * 'b')
        value = 123
        subtask_id = 'subtask_id'
        self.user_sci.deposit_payment(value)
        self._wait_for_pending()

        # subtask_id too long
        with self.assertRaisesRegex(ValueError, 'subtask_id cannot be longer'):
            self.concent_sci.force_subtask_payment(
                requestor,
                provider,
                value,
                'a' * 33,
            )

        from_block = self.user_sci.get_block_number()
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
        self._wait_for_pending()
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

    def test_gntb_transfer(self):
        self._create_gntb()
        recipient = to_checksum_address('0x' + 40 * 'a')
        amount = 123
        self.user_sci.transfer_gntb(recipient, amount)
        self._wait_for_pending()
        assert self.user_sci.get_gntb_balance(recipient) == amount

    def test_withdraw_gntb(self):
        self._create_gntb()
        amount = 123
        user_addr = self.user_sci.get_eth_address()
        recipient = to_checksum_address('0x' + 40 * 'a')
        self.user_sci.convert_gntb_to_gnt(recipient, amount)
        self._wait_for_pending()
        assert self.user_sci.get_gntb_balance(user_addr) == \
            1000 * denoms.ether - amount
        assert self.user_sci.get_gnt_balance(recipient) == amount

    def test_batch_transfer(self):
        self._create_gntb()
        payee1 = to_checksum_address('0x' + 40 * 'a')
        payee2 = to_checksum_address('0x' + 40 * 'b')
        amount1 = 123
        amount2 = 234
        closure_time = 555

        payment1 = mock_payment(payee1, amount1)
        payment2 = mock_payment(payee2, amount2)

        from_block = self.user_sci.get_block_number()
        tx_hash = self.user_sci.batch_transfer(
            [payment1, payment2],
            closure_time,
        )
        self._wait_for_pending()
        to_block = self.user_sci.get_block_number()

        batch_transfers1 = self.user_sci.get_batch_transfers(
            self.user_sci.get_eth_address(),
            payee1,
            from_block,
            to_block,
        )
        assert self.user_sci.get_gntb_balance(payee1) == amount1
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
        assert self.user_sci.get_gntb_balance(payee2) == amount2
        assert len(batch_transfers2) == 1
        assert batch_transfers2[0].tx_hash == tx_hash
        assert batch_transfers2[0].amount == amount2
        assert batch_transfers2[0].sender == self.user_sci.get_eth_address()
        assert batch_transfers2[0].receiver == payee2
        assert batch_transfers2[0].closure_time == closure_time
