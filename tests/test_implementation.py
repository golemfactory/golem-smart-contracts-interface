import unittest.mock as mock
import unittest

from golem_sci.implementation import SCIImplementation


class SCIImplementationTest(unittest.TestCase):
    def setUp(self):
        self.geth_client = mock.Mock()
        self.token = mock.Mock()
        self.token.GNTW_ADDRESS = '0x' + '1' * 40
        self.token.TRANSFER_EVENT_ID = '0x' + '2' * 64
        self.sci = SCIImplementation(self.geth_client, self.token, False)

    def test_subscribe_to_incoming_batch_transfers(self):
        receiver_address = '0x' + 'f' * 40
        sender_address = '0x' + 'e' * 40
        tx_hash = '0x' + 'a' * 40
        required_confs = 2
        block_number = 100
        data = '0x00000000000000000000000000000000000000000000000002501e734690aaab000000000000000000000000000000000000000000000000000000005a6af820'  # noqa
        filter_id = 3
        events = []

        self.geth_client.new_filter.return_value = filter_id
        self.sci.subscribe_to_incoming_batch_transfers(
            receiver_address,
            lambda e: events.append(e),
            required_confs,
        )

        self.geth_client.new_filter.assert_called_once_with(
            address=self.token.GNTW_ADDRESS,
            topics=[self.token.TRANSFER_EVENT_ID, None, receiver_address],
        )

        self.geth_client.get_filter_changes.return_value = [{
            'removed': False,
            'transactionHash': tx_hash,
            'blockNumber': block_number,
            'topics': ['', '0x' + '0' * 24 + sender_address[2:]],
            'data': data,
        }]
        self.geth_client.get_block_number.return_value = block_number
        self.sci._pull_changes_from_blockchain()
        self.geth_client.get_filter_changes.assert_called_once_with(filter_id)
        assert 0 == len(events)

        self.geth_client.get_filter_changes.return_value = []
        self.geth_client.get_block_number.return_value = \
            block_number + required_confs
        self.sci._pull_changes_from_blockchain()
        assert 1 == len(events)
        assert tx_hash == events[0].tx_hash
        assert sender_address == events[0].sender
        assert 166666666666666667 == events[0].amount
        assert 1516959776 == events[0].closure_time
        events = []

        self.sci._pull_changes_from_blockchain()
        assert 0 == len(events)

    def test_get_incoming_batch_tranfers(self):
        receiver_address = '0x' + 'f' * 40
        sender_address = '0x' + 'e' * 40
        tx_hash = '0x' + 'a' * 40
        from_block = 10
        to_block = 20
        data = '0x00000000000000000000000000000000000000000000000002501e734690aaab000000000000000000000000000000000000000000000000000000005a6af820'  # noqa

        self.geth_client.get_logs.return_value = [{
            'transactionHash': tx_hash,
            'topics': ['', '0x' + '0' * 24 + sender_address[2:]],
            'data': data,
        }]

        events = self.sci.get_incoming_batch_tranfers(
            sender_address,
            receiver_address,
            from_block,
            to_block,
        )
        self.geth_client.get_logs.assert_called_once_with(
            address=self.token.GNTW_ADDRESS,
            topics=[self.token.TRANSFER_EVENT_ID, sender_address, receiver_address],  # noqa
            from_block=from_block,
            to_block=to_block,
        )
        assert 1 == len(events)
        assert tx_hash == events[0].tx_hash
        assert sender_address == events[0].sender
        assert 166666666666666667 == events[0].amount
        assert 1516959776 == events[0].closure_time

