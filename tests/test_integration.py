import json
import unittest.mock as mock
import unittest
import os

from golem_sci.factory import new_sci
import golem_sci.contracts as contracts

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


class IntegrationTest(unittest.TestCase):
    def _deploy_gnt(self, web3):
        addr = self.eth_tester.get_accounts()[0]

        block_number = web3.eth.blockNumber
        gnt = web3.eth.contract(
            bytecode=contracts.GolemNetworkToken.BIN,
            abi=json.loads(contracts.GolemNetworkToken.ABI),
        )
        gnt_tx = gnt.deploy(
            transaction={'from': addr},
            args=[
                decode_hex(addr),
                decode_hex(addr),
                block_number + 2,
                block_number + 3,
            ],
        )
        contracts.GolemNetworkToken.ADDRESS = \
            web3.eth.getTransactionReceipt(gnt_tx)['contractAddress']
        gnt_funder = self.eth_tester.get_accounts()[1]
        gnt.transact({
            'from': gnt_funder,
            'value': 5 * 10 ** 16,
            'to': contracts.GolemNetworkToken.ADDRESS,
        }).create()
        total_gnt = gnt.call({
            'from': gnt_funder,
            'to': contracts.GolemNetworkToken.ADDRESS,
        }).totalSupply()
        self.eth_tester.mine_blocks(2)
        gnt.transact({
            'from': gnt_funder,
            'to': contracts.GolemNetworkToken.ADDRESS,
        }).finalize()

        faucet = web3.eth.contract(
            bytecode=contracts.Faucet.BIN,
            abi=json.loads(contracts.Faucet.ABI),
        )
        faucet_tx = faucet.deploy(
            transaction={'from': addr},
            args=[decode_hex(contracts.GolemNetworkToken.ADDRESS)],
        )
        contracts.Faucet.ADDRESS = \
            web3.eth.getTransactionReceipt(faucet_tx)['contractAddress']

        gnt.transact({
            'from': gnt_funder,
            'to': contracts.GolemNetworkToken.ADDRESS,
        }).transfer(contracts.Faucet.ADDRESS, total_gnt)

    def _deploy_gntw(self, web3):
        addr = self.eth_tester.get_accounts()[0]
        gntw = web3.eth.contract(
            bytecode=contracts.GolemNetworkTokenBatching.BIN,
            abi=json.loads(contracts.GolemNetworkTokenBatching.ABI),
        )
        gntw_tx = gntw.deploy(
            transaction={'from': addr},
            args=[decode_hex(contracts.GolemNetworkToken.ADDRESS)],
        )
        contracts.GolemNetworkTokenBatching.ADDRESS = \
            web3.eth.getTransactionReceipt(gntw_tx)['contractAddress']

    def _deploy_concents(self, web3):
        self.gntdeposit_withdrawal_delay = 7 * 24 * 60 * 60
        addr = self.eth_tester.get_accounts()[0]
        gnt_deposit = web3.eth.contract(
            bytecode=contracts.GNTDeposit.BIN,
            abi=json.loads(contracts.GNTDeposit.ABI),
        )
        gnt_deposit_tx = gnt_deposit.deploy(
            transaction={'from': addr},
            args=[
                decode_hex(contracts.GolemNetworkTokenBatching.ADDRESS),
                decode_hex(self.address),  # oracle
                decode_hex(self.address),  # coldwallet
                self.gntdeposit_withdrawal_delay,
            ],
        )
        contracts.GNTDeposit.ADDRESS = \
            web3.eth.getTransactionReceipt(gnt_deposit_tx)['contractAddress']

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

    def setUp(self):
        privkey = os.urandom(32)
        self.address = encode_hex(privtoaddr(privkey))
        self._create_eth_tester()
        web3 = Web3(EthereumTesterProvider(self.eth_tester))

        self._deploy_gnt(web3)
        self._deploy_gntw(web3)
        self._deploy_concents(web3)

        from_addr = self.eth_tester.get_accounts()[0]
        self.eth_tester.send_transaction({
            'from': from_addr,
            'to': self.address,
            'value': self.eth_tester.get_balance(from_addr) - 21000,
            'gas': 21000,
        })

        def sign_tx(tx):
            tx.sign(privkey)
        with mock.patch('golem_sci.factory._ensure_geth_version'):
            with mock.patch('golem_sci.factory._ensure_genesis'):
                self.sci = new_sci(web3, self.address, sign_tx)

        self.eth_tester.add_account(encode_hex(privkey))

    def _create_gntw(self):
        self.sci.request_gnt_from_faucet()
        self.sci.open_gate()
        pda = self.sci.get_gate_address()
        self.sci.transfer_gnt(pda, 1000 * denoms.ether)
        self.sci.transfer_from_gate()
        assert self.sci.get_gntw_balance(self.address) == 1000 * denoms.ether

    def _time_travel(self, period: int):
        current_ts = self.eth_tester.get_block_by_number('pending')['timestamp']
        self.eth_tester.time_travel(current_ts + period)

    def test_faucet(self):
        assert self.sci.get_gnt_balance(self.address) == 0
        self.sci.request_gnt_from_faucet()
        assert self.sci.get_gnt_balance(self.address) == 1000 * denoms.ether

    def test_gntdeposit_lock(self):
        self._create_gntw()
        value = 1000 * denoms.ether
        assert self.sci.get_deposit_value(self.address) == 0
        assert self.sci.get_deposit_locked_until(self.address) == 0

        self.sci.deposit_payment(value)
        assert self.sci.get_deposit_value(self.address) == value
        assert self.sci.get_gntw_balance(self.address) == 0

        # can't withdraw if unlocked
        with self.assertRaises(TransactionFailed):
            self.sci.withdraw_deposit()

        # can't withdraw if just unlocked
        self.sci.unlock_deposit()
        with self.assertRaises(TransactionFailed):
            self.sci.withdraw_deposit()

        # can't withdraw if still time locked
        self._time_travel(self.gntdeposit_withdrawal_delay - 100)
        with self.assertRaises(TransactionFailed):
            self.sci.withdraw_deposit()

        self._time_travel(100)
        self.sci.withdraw_deposit()
        assert self.sci.get_deposit_value(self.address) == 0
        assert self.sci.get_gntw_balance(self.address) == value

    def test_forced_payment(self):
        self._create_gntw()
        requestor = self.address
        provider = '0x' + 40 * 'b'
        value = 123
        closure_time = 1337
        self.sci.deposit_payment(value)

        from_block = self.sci.get_block_number()
        self.sci.force_payment(requestor, provider, value, closure_time)
        assert self.sci.get_deposit_value(requestor) == 0
        assert self.sci.get_gntw_balance(provider) == value
        self.eth_tester.mine_block()
        to_block = self.sci.get_block_number()
        forced_payments = self.sci.get_forced_payments(
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

    def test_gntw_transfer(self):
        self._create_gntw()
        recipient = '0x' + 40 * 'a'
        amount = 123
        self.sci.transfer_gntw(recipient, amount)
        assert self.sci.get_gntw_balance(recipient) == amount
