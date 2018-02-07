import json
import unittest.mock as mock
import unittest

from golem_sci.implementation import SCIImplementation
from golem_sci.contracts import GolemNetworkTokenWrapped


def get_eth_address():
    return '0xadd355' + '0' * 34


class SCIImplementationTest(unittest.TestCase):
    def setUp(self):
        self.geth_client = mock.Mock()
        self.contracts = {}

        def client_contract(addr, abi):
            ret = mock.Mock()
            ret.abi = json.loads(abi)
            ret.address = addr
            return ret
        self.geth_client.contract.side_effect = client_contract
        with mock.patch('golem_sci.implementation.ContractWrapper') as contract:
            def wrapper_factory(actor_address, c):
                res = mock.Mock()
                self.contracts[c.address] = res
                return res
            contract.side_effect = wrapper_factory
            self.sci = SCIImplementation(
                self.geth_client,
                get_eth_address(),
                monitor=False)
        self.gntw = self.contracts[GolemNetworkTokenWrapped.ADDRESS]

    def test_eth_address(self):
        assert get_eth_address() == self.sci.get_eth_address()

    def test_subscribe_to_incoming_batch_transfers(self):
        receiver_address = '0x' + 'f' * 40
        sender_address = '0x' + 'e' * 40
        tx_hashes = ['0x' + 39 * '0' + str(i) for i in range(1, 10)]
        required_confs = 2
        block_number = 100
        from_block = 10
        data = '0x00000000000000000000000000000000000000000000000002501e734690aaab000000000000000000000000000000000000000000000000000000005a6af820'  # noqa
        filter_id = 3
        events = []

        self.gntw.on.return_value = filter_id
        self.geth_client.get_filter_logs.return_value = []
        self.sci.subscribe_to_incoming_batch_transfers(
            receiver_address,
            from_block,
            lambda e: events.append(e),
            required_confs,
        )

        self.gntw.on.assert_called_once_with(
            'BatchTransfer',
            from_block,
            'latest',
            {'to': receiver_address},
        )
        self.geth_client.get_filter_logs.assert_called_once_with(filter_id)

        self.geth_client.get_filter_changes.return_value = [
            {
                'removed': False,
                'transactionHash': tx_hash,
                'blockNumber': block_number,
                'topics': [
                    '',
                    '0x' + '0' * 24 + sender_address[2:],
                    '0x' + '0' * 24 + receiver_address[2:],
                ],
                'data': data,
            } for tx_hash in tx_hashes
        ]
        self.geth_client.get_block_number.return_value = block_number
        self.sci._pull_changes_from_blockchain()
        self.geth_client.get_filter_changes.assert_called_once_with(filter_id)
        assert 0 == len(events)

        self.geth_client.get_filter_changes.return_value = []
        self.geth_client.get_block_number.return_value = \
            block_number + required_confs
        self.sci._pull_changes_from_blockchain()
        assert len(tx_hashes) == len(events)
        for i, tx_hash in enumerate(tx_hashes):
            assert tx_hash == events[i].tx_hash
            assert sender_address == events[i].sender
            assert receiver_address == events[i].receiver
            assert 166666666666666667 == events[i].amount
            assert 1516959776 == events[i].closure_time
        events = []

        self.sci._pull_changes_from_blockchain()
        assert 0 == len(events)

    def test_get_batch_tranfers(self):
        receiver_address = '0x' + 'f' * 40
        sender_address = '0x' + 'e' * 40
        tx_hash = '0x' + 'a' * 40
        from_block = 10
        to_block = 20
        data = '0x00000000000000000000000000000000000000000000000002501e734690aaab000000000000000000000000000000000000000000000000000000005a6af820'  # noqa
        filter_id = 123

        self.geth_client.get_filter_logs.return_value = [{
            'transactionHash': tx_hash,
            'topics': [
                '',
                '0x' + '0' * 24 + sender_address[2:],
                '0x' + '0' * 24 + receiver_address[2:],
            ],
            'data': data,
        }]
        self.gntw.on.return_value = filter_id

        events = self.sci.get_batch_tranfers(
            sender_address,
            receiver_address,
            from_block,
            to_block,
        )
        self.geth_client.get_filter_logs.assert_called_once_with(
            filter_id,
        )
        assert 1 == len(events)
        assert tx_hash == events[0].tx_hash
        assert sender_address == events[0].sender
        assert receiver_address == events[0].receiver
        assert 166666666666666667 == events[0].amount
        assert 1516959776 == events[0].closure_time

    def test_on_transaction_confirmed(self):
        tx_hash = '0x' + 'a' * 40
        required_confs = 12
        gas_used = 1234
        block_number = 100
        block_hash = '0xbbb'
        receipt = []

        def cb(tx_receipt):
            receipt.append(tx_receipt)

        self.sci.on_transaction_confirmed(tx_hash, required_confs, cb)

        self.geth_client.get_block_number.return_value = block_number - 1
        self.geth_client.get_transaction_receipt.return_value = None
        self.sci._pull_changes_from_blockchain()
        assert not receipt

        self.geth_client.get_block_number.return_value = block_number
        self.geth_client.get_transaction_receipt.return_value = {
            'status': '0x1',
            'gasUsed': gas_used,
            'blockNumber': block_number,
            'blockHash': block_hash,
        }
        self.sci._pull_changes_from_blockchain()
        assert not receipt

        self.geth_client.get_block_number.return_value = \
            block_number + required_confs - 1
        self.sci._pull_changes_from_blockchain()
        assert not receipt

        self.geth_client.get_block_number.return_value = \
            block_number + required_confs + 1
        self.sci._pull_changes_from_blockchain()
        assert receipt
        assert receipt[0].status
        assert gas_used == receipt[0].gas_used
        assert block_number == receipt[0].block_number
        assert block_hash == receipt[0].block_hash
