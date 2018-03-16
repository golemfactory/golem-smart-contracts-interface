import json
from unittest import mock, TestCase
import os

from golem_sci import contracts
from golem_sci.factory import new_sci

from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider
from ethereum.keys import privtoaddr
from ethereum.tester import TransactionFailed
from eth_tester import EthereumTester
from eth_utils import decode_hex, encode_hex, denoms

# This can go away after updating to web3 4.0.0
import web3.providers.eth_tester.main
web3.providers.eth_tester.main.API_ENDPOINTS['eth']['sendRawTransaction'] = \
    web3.providers.eth_tester.main.call_eth_tester('send_raw_transaction')


def mock_payment(payee: str, amount: int):
    payment = mock.Mock()
    payment.payee = decode_hex(payee)
    payment.value = amount
    return payment


class MockProvider:
    def __init__(self) -> None:
        self.data = {}

    def get_address(self, contract: str) -> str:
        return self.data[contract]['address']

    def get_abi(self, contract: str) -> str:
        return self.data[contract]['abi']


class IntegrationTest(TestCase):
    def _deploy_gnt(self, web3, golem_address: str):
        addr = self.eth_tester.get_accounts()[0]

        block_number = web3.eth.blockNumber
        from golem_sci.contracts.data.rinkeby import golemnetworktoken
        gnt = web3.eth.contract(
            bytecode=golemnetworktoken.BIN,
            abi=json.loads(golemnetworktoken.ABI),
        )
        gnt_tx = gnt.deploy(
            transaction={'from': addr},
            args=[
                decode_hex(golem_address),
                decode_hex(golem_address),
                block_number + 2,
                block_number + 3,
            ],
        )
        gnt_address = \
            web3.eth.getTransactionReceipt(gnt_tx)['contractAddress']
        self.provider.data[contracts.GolemNetworkToken] = {
            'address': gnt_address,
            'abi': golemnetworktoken.ABI,
        }
        gnt_funder = self.eth_tester.get_accounts()[1]
        gnt.transact({
            'from': gnt_funder,
            'value': 5 * 10 ** 16,
            'to': gnt_address,
        }).create()
        total_gnt = gnt.call({
            'from': gnt_funder,
            'to': gnt_address,
        }).totalSupply()
        self.eth_tester.mine_blocks(2)
        gnt.transact({
            'from': gnt_funder,
            'to': gnt_address,
        }).finalize()

        from golem_sci.contracts.data.rinkeby import faucet
        faucet_contract = web3.eth.contract(
            bytecode=faucet.BIN,
            abi=json.loads(faucet.ABI),
        )
        faucet_tx = faucet_contract.deploy(
            transaction={'from': addr},
            args=[decode_hex(gnt_address)],
        )
        faucet_address = \
            web3.eth.getTransactionReceipt(faucet_tx)['contractAddress']
        self.provider.data[contracts.Faucet] = {
            'address': faucet_address,
            'abi': faucet.ABI,
        }

        gnt.transact({
            'from': gnt_funder,
            'to': gnt_address,
        }).transfer(faucet_address, total_gnt)

    def _deploy_gntb(self, web3):
        addr = self.eth_tester.get_accounts()[0]
        from golem_sci.contracts.data.rinkeby import golemnetworktokenbatching
        gntb = web3.eth.contract(
            bytecode=golemnetworktokenbatching.BIN,
            abi=json.loads(golemnetworktokenbatching.ABI),
        )
        gnt_address = self.provider.get_address(contracts.GolemNetworkToken)
        gntb_tx = gntb.deploy(
            transaction={'from': addr},
            args=[decode_hex(gnt_address)],
        )
        gntb_address = \
            web3.eth.getTransactionReceipt(gntb_tx)['contractAddress']
        self.provider.data[contracts.GolemNetworkTokenBatching] = {
            'address': gntb_address,
            'abi': golemnetworktokenbatching.ABI,
        }

    def _deploy_concents(self, web3, concent_address: str):
        self.gntdeposit_withdrawal_delay = 7 * 24 * 60 * 60
        addr = self.eth_tester.get_accounts()[0]
        from golem_sci.contracts.data.rinkeby import gntdeposit
        gnt_deposit = web3.eth.contract(
            bytecode=gntdeposit.BIN,
            abi=json.loads(gntdeposit.ABI),
        )
        gntb_address = \
            self.provider.get_address(contracts.GolemNetworkTokenBatching)
        gnt_deposit_tx = gnt_deposit.deploy(
            transaction={'from': addr},
            args=[
                decode_hex(gntb_address),
                decode_hex(concent_address),  # oracle
                decode_hex(concent_address),  # coldwallet
                self.gntdeposit_withdrawal_delay,
            ],
        )
        gntdeposit_address = \
            web3.eth.getTransactionReceipt(gnt_deposit_tx)['contractAddress']
        self.provider.data[contracts.GNTDeposit] = {
            'address': gntdeposit_address,
            'abi': gntdeposit.ABI,
        }

        # TODO Test GNTPaymentChannels
        self.provider.data[contracts.GNTPaymentChannels] = {
            'address': '0x' + 40 * '3',
            'abi': '[]',
        }

    def _create_eth_tester(self):
        self.eth_tester = EthereumTester()

        # some weird patching is needed for compatibility with web3
        # mostly because of eth_tester using snake_case while web3 is using
        # camelCase

        self.eth_tester.original_create_log_filter = \
            self.eth_tester.create_log_filter

        def create_log_filter_patch(**params):
            if 'fromBlock' in params:
                params['from_block'] = int(params['fromBlock'], 16)
                del params['fromBlock']
            if 'toBlock' in params:
                params['to_block'] = int(params['toBlock'], 16)
                del params['toBlock']
            return self.eth_tester.original_create_log_filter(**params)
        self.eth_tester.create_log_filter = create_log_filter_patch

        self.eth_tester.original_get_all_filter_logs = \
            self.eth_tester.get_all_filter_logs

        def get_all_filter_logs_patch(filter_id):
            res = self.eth_tester.original_get_all_filter_logs(filter_id)
            for i in res:
                if 'transaction_hash' in i:
                    i['transactionHash'] = i['transaction_hash']
                    del i['transaction_hash']
            return res
        self.eth_tester.get_all_filter_logs = get_all_filter_logs_patch

    def _fund_account(self, from_idx: int, address: str) -> None:
        from_addr = self.eth_tester.get_accounts()[from_idx]
        self.eth_tester.send_transaction({
            'from': from_addr,
            'to': address,
            'value': self.eth_tester.get_balance(from_addr) - 21000,
            'gas': 21000,
        })

    def setUp(self):
        golem_privkey = os.urandom(32)
        concent_privkey = os.urandom(32)
        user_privkey = os.urandom(32)
        golem_address = encode_hex(privtoaddr(golem_privkey))
        concent_address = encode_hex(privtoaddr(concent_privkey))
        user_address = encode_hex(privtoaddr(user_privkey))

        self.provider = MockProvider()

        self._create_eth_tester()
        web3 = Web3(EthereumTesterProvider(self.eth_tester))

        self._deploy_gnt(web3, golem_address)
        self._deploy_gntb(web3)
        self._deploy_concents(web3, concent_address)

        self._fund_account(1, concent_address)
        self._fund_account(2, user_address)

        with mock.patch('golem_sci.factory._ensure_geth_version'), \
                mock.patch('golem_sci.factory._ensure_genesis'), \
                mock.patch('golem_sci.factory.ContractDataProvider') as cdp:
            cdp.return_value = self.provider

            def sign_tx_user(tx):
                tx.sign(user_privkey)
            self.user_sci = new_sci(web3, user_address, sign_tx_user)

            def sign_tx_concent(tx):
                tx.sign(concent_privkey)
            self.concent_sci = new_sci(
                web3,
                concent_address,
                sign_tx_concent,
            )

        self.eth_tester.add_account(encode_hex(concent_privkey))
        self.eth_tester.add_account(encode_hex(user_privkey))

    def _create_gntb(self):
        self.user_sci.request_gnt_from_faucet()
        self.user_sci.open_gate()
        pda = self.user_sci.get_gate_address()
        self.user_sci.transfer_gnt(pda, 1000 * denoms.ether)
        self.user_sci.transfer_from_gate()
        assert self.user_sci.get_gntb_balance(self.user_sci.get_eth_address()) \
            == 1000 * denoms.ether

    def _time_travel(self, period: int):
        current_ts = self.eth_tester.get_block_by_number('pending')['timestamp']
        self.eth_tester.time_travel(current_ts + period)

    def test_transfer_eth(self):
        recipient = '0x' + 40 * 'e'
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
        assert self.user_sci.get_deposit_value(user_addr) == value
        assert self.user_sci.get_gntb_balance(user_addr) == 0

        # can't withdraw if unlocked
        with self.assertRaises(TransactionFailed):
            self.user_sci.withdraw_deposit()

        # can't withdraw if just unlocked
        self.user_sci.unlock_deposit()
        with self.assertRaises(TransactionFailed):
            self.user_sci.withdraw_deposit()

        # can't withdraw if still time locked
        self._time_travel(self.gntdeposit_withdrawal_delay - 100)
        with self.assertRaises(TransactionFailed):
            self.user_sci.withdraw_deposit()

        self._time_travel(100)
        self.user_sci.withdraw_deposit()
        assert self.user_sci.get_deposit_value(user_addr) == 0
        assert self.user_sci.get_gntb_balance(user_addr) == value

    def test_forced_payment(self):
        self._create_gntb()
        requestor = self.user_sci.get_eth_address()
        provider = '0x' + 40 * 'b'
        value = 123
        closure_time = 1337
        self.user_sci.deposit_payment(value)

        from_block = self.user_sci.get_block_number()
        # user can't force a payment
        with self.assertRaises(TransactionFailed):
            self.user_sci.force_payment(
                requestor,
                provider,
                value,
                closure_time,
            )
        # only concent can
        self.concent_sci.force_payment(requestor, provider, value, closure_time)
        assert self.user_sci.get_deposit_value(requestor) == 0
        assert self.user_sci.get_gntb_balance(provider) == value
        self.eth_tester.mine_block()
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

    def test_gntb_transfer(self):
        self._create_gntb()
        recipient = '0x' + 40 * 'a'
        amount = 123
        self.user_sci.transfer_gntb(recipient, amount)
        assert self.user_sci.get_gntb_balance(recipient) == amount

    def test_withdraw_gntb(self):
        self._create_gntb()
        amount = 123
        user_addr = self.user_sci.get_eth_address()
        self.user_sci.convert_gntb_to_gnt(amount)
        assert self.user_sci.get_gnt_balance(user_addr) == amount
        assert self.user_sci.get_gntb_balance(user_addr) == \
            1000 * denoms.ether - amount

    def test_batch_transfer(self):
        self._create_gntb()
        payee1 = '0x' + 40 * 'a'
        payee2 = '0x' + 40 * 'b'
        amount1 = 123
        amount21 = 234
        amount22 = 345
        closure_time = 555

        payment1 = mock_payment(payee1, amount1)
        payment21 = mock_payment(payee2, amount21)
        payment22 = mock_payment(payee2, amount22)

        from_block = self.user_sci.get_block_number()
        tx_hash = self.user_sci.batch_transfer(
            [payment1, payment21, payment22],
            closure_time,
        )
        self.eth_tester.mine_block()
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
        assert self.user_sci.get_gntb_balance(payee2) == amount21 + amount22
        assert len(batch_transfers2) == 1
        assert batch_transfers2[0].tx_hash == tx_hash
        assert batch_transfers2[0].amount == amount21 + amount22
        assert batch_transfers2[0].sender == self.user_sci.get_eth_address()
        assert batch_transfers2[0].receiver == payee2
        assert batch_transfers2[0].closure_time == closure_time
