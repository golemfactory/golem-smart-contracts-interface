from unittest import mock

from golem_sci import (
    Payment,
    new_sci,
    GNTConverter,
    JsonTransactionsStorage,
)
from golem_sci.implementation import SCIImplementation

from .integrationbase import IntegrationBase, TEST_RECIPIENT_ADDR, ZERO_ADDR

from eth_utils import denoms, to_checksum_address


class TestIntegration(IntegrationBase):
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

    def test_subscribe_from_block(self):
        from_block = self.user_sci.get_block_number()
        self.user_sci.request_gnt_from_faucet()
        self._mine_required_blocks()
        events = []
        self.user_sci.subscribe_to_gnt_transfers(
            None,
            self.user_sci.get_eth_address(),
            from_block,
            lambda e: events.append(e),
        )
        self._mine_blocks()
        assert len(events) == 1

    def test_gnt_transfer_subscription(self):
        self.user_sci.request_gnt_from_faucet()
        self._mine_required_blocks()
        recipient = TEST_RECIPIENT_ADDR
        assert self.user_sci.get_gnt_balance(recipient) == 0
        amount = 123
        events = []
        from_block = self.user_sci.get_block_number()
        self.user_sci.subscribe_to_gnt_transfers(
            self.user_sci.get_eth_address(),
            None,
            from_block,
            lambda e: events.append(e),
        )
        self.user_sci.subscribe_to_gnt_transfers(
            None,
            recipient,
            from_block,
            lambda e: events.append(e),
        )
        tx_hash = self.user_sci.transfer_gnt(recipient, amount)
        self._wait_for_pending()
        assert self.user_sci.get_gnt_balance(recipient) == 0
        assert not events
        self._mine_required_blocks()
        assert self.user_sci.get_gnt_balance(recipient) == amount
        assert len(events) == 2
        for e in events:
            assert e.from_address == self.user_sci.get_eth_address()
            assert e.to_address == recipient
            assert e.amount == amount
            assert e.tx_hash == tx_hash

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
        amount1 = 123
        amount2 = 222
        amount = amount1 + amount2
        user_addr = self.user_sci.get_eth_address()
        recipient = TEST_RECIPIENT_ADDR
        self.user_sci.convert_gntb_to_gnt(recipient, amount1)
        self.user_sci.convert_gntb_to_gnt(recipient, amount2, 10 ** 9)
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
                mock.patch('golem_sci.implementation.threading'):
            self.user_sci = new_sci(
                self.web3,
                self.user_sci.get_eth_address(),
                'test_chain',
                JsonTransactionsStorage(self.tempdir / 'user_tx.json'),
                self.contract_addresses,
            )
            self.concent_sci = None
        self._fund_account(self.user_sci.get_eth_address())
        self._wait_for_pending()
        assert len(self.user_sci._storage.get_all_tx()) == 1
        self._mine_required_blocks()
        assert len(self.user_sci._storage.get_all_tx()) == 0

    def test_nonce_too_low(self):
        self.user_sci.transfer_eth(ZERO_ADDR, 1)

        self.user_sci._storage._data = {'nonce': 0, 'tx': {}}
        # shouldn't throw since it's the same transaction
        self.user_sci.transfer_eth(ZERO_ADDR, 1)

        self.user_sci._storage._data = {'nonce': 0, 'tx': {}}
        # different transaction so it should throw
        with self.assertRaisesRegex(Exception, 'nonce too low'):
            self.user_sci.transfer_eth(ZERO_ADDR, 2)

    def test_get_transaction_gas_price(self):
        tx_hash_nope = '0x' + 64 * '1'
        assert self.user_sci.get_transaction_gas_price(tx_hash_nope) is None

        gas_price = 123
        tx_hash = self.user_sci.transfer_eth(ZERO_ADDR, 1, gas_price=gas_price)
        assert self.user_sci.get_transaction_gas_price(tx_hash) == gas_price

    def test_mined_but_unconfirmed_receipt(self):
        tx_hash = self.user_sci.transfer_eth(ZERO_ADDR, 1)
        self._wait_for_pending()
        assert self.user_sci.get_transaction_receipt(tx_hash) is None
        self._mine_required_blocks()
        assert self.user_sci.get_transaction_receipt(tx_hash) is not None
