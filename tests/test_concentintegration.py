from eth_utils import denoms

from .integrationbase import IntegrationBase, TEST_RECIPIENT_ADDR


class TestConcentIntegration(IntegrationBase):
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
        self._mine_required_blocks()
        receipt = self.user_sci.get_transaction_receipt(tx_hash)
        assert not receipt.status

        # can't withdraw if just unlocked
        self.user_sci.unlock_deposit()
        self._wait_for_pending()
        tx_hash = self.user_sci.withdraw_deposit()
        self._mine_required_blocks()
        receipt = self.user_sci.get_transaction_receipt(tx_hash)
        assert not receipt.status

        assert self.user_sci.get_deposit_locked_until(user_addr) > 0
        self.user_sci.lock_deposit()
        self._mine_required_blocks()
        assert self.user_sci.get_deposit_locked_until(user_addr) == 0

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
        events = []

        from_block = self.user_sci.get_block_number()
        # user can't force a payment
        tx_hash = self.user_sci.force_payment(
            requestor,
            provider,
            value,
            closure_time,
        )
        self._mine_required_blocks()
        receipt = self.user_sci.get_transaction_receipt(tx_hash)
        assert not receipt.status

        self.user_sci.subscribe_to_forced_payments(
            None,
            provider,
            from_block,
            lambda e: events.append(e),
        )

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

        assert len(events) == 1
        assert events[0].requestor == requestor
        assert events[0].provider == provider
        assert events[0].amount == value
        assert events[0].closure_time == closure_time

    def test_forced_subtask_payment(self):
        self._create_gntb()
        requestor = self.user_sci.get_eth_address()
        provider = TEST_RECIPIENT_ADDR
        value = 123
        subtask_id = b'subtask_id' + b'0' * 22
        events = []
        self.user_sci.deposit_payment(value)
        self._wait_for_pending()

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
        self._mine_required_blocks()
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

    def test_cover_additional_verification_costs(self):
        self._create_gntb()
        address = self.user_sci.get_eth_address()
        value = 123
        subtask_id = b'subtask_id' + b'0' * 22
        self.user_sci.deposit_payment(value)
        self._wait_for_pending()

        with self.assertRaisesRegex(ValueError, 'subtask_id has to be exactly'):
            self.concent_sci.cover_additional_verification_cost(
                address,
                value,
                b'a' * 31,
            )

        from_block = self.user_sci.get_block_number()

        # user can't force a payment
        tx_hash = self.user_sci.cover_additional_verification_cost(
            address,
            value,
            subtask_id,
        )
        self._mine_required_blocks()
        receipt = self.user_sci.get_transaction_receipt(tx_hash)
        assert not receipt.status

        # only concent can
        self.concent_sci.cover_additional_verification_cost(
            address,
            value,
            subtask_id,
        )
        self._mine_required_blocks()
        assert self.user_sci.get_deposit_value(address) == 0
        to_block = self.user_sci.get_block_number()
        additional_costs = \
            self.user_sci.get_covered_additional_verification_costs(
                address,
                from_block,
                to_block,
            )

        assert len(additional_costs) == 1
        assert additional_costs[0].address == address
        assert additional_costs[0].amount == value
        assert additional_costs[0].subtask_id == subtask_id
