import json
import unittest.mock as mock
import unittest

from eth_utils import to_checksum_address
from hexbytes import HexBytes

from golem_sci import contracts
from golem_sci.implementation import SCIImplementation


def get_eth_address():
    return to_checksum_address('0xadd355' + '0' * 34)


class SCIImplementationTest(unittest.TestCase):
    def setUp(self):
        self.geth_client = mock.Mock()
        self.contracts = {}

        def client_contract(addr, abi):
            ret = mock.Mock()
            ret.abi = json.loads(abi)
            ret.address = addr
            self.contracts[addr] = ret
            return ret
        self.sign_tx = mock.Mock()
        self.geth_client.contract.side_effect = client_contract
        self.geth_client.get_gas_price.return_value = 10 ** 9
        self.geth_client.get_block_number.return_value = 1
        self.geth_client.get_balance.return_value = 10 ** 20
        self.geth_client.estimate_gas.return_value = 21000
        self.storage = mock.Mock()
        self.storage.get_all_tx.return_value = []
        self.storage.get_nonce.return_value = 0

        self.contract_addresses = {
            contracts.GNTB: '0x' + 40 * '1',
        }

        self.sci = SCIImplementation(
            self.geth_client,
            get_eth_address(),
            self.storage,
            self.contract_addresses,
            self.sign_tx,
            monitor=False)
        self.gntb = self.contracts[self.contract_addresses[contracts.GNTB]]

    def test_eth_address(self):
        assert get_eth_address() == self.sci.get_eth_address()

    def test_storage_init(self):
        self.storage.init.assert_called_once_with(
            self.geth_client.get_transaction_count(),
        )

    def test_gas_price(self):
        hard_cap = self.sci.GAS_PRICE

        gas_price = hard_cap // 2
        self.geth_client.get_gas_price.return_value = gas_price
        self.geth_client.get_transaction_count.return_value = 0
        self.geth_client.get_block_number.return_value = 2
        self.sci._monitor_blockchain_single()
        self.sci.transfer_eth(get_eth_address(), 123)
        self.geth_client.send.assert_called()
        assert self.geth_client.send.call_args[0][0].gasprice == gas_price
        self.geth_client.reset_mock()

        gas_price = 2 * hard_cap
        self.geth_client.get_gas_price.return_value = gas_price
        self.geth_client.get_block_number.return_value = 3
        self.sci._monitor_blockchain_single()
        self.sci.transfer_eth(get_eth_address(), 123)
        self.geth_client.send.assert_called()
        assert self.geth_client.send.call_args[0][0].gasprice == hard_cap
        self.geth_client.reset_mock()

    def test_subscribe_to_batch_transfers(self):
        receiver_address = to_checksum_address('0x' + 'f' * 40)
        sender_address = to_checksum_address('0x' + 'e' * 40)
        tx_hashes = ['0x' + 39 * '0' + str(i) for i in range(1, 10)]
        block_number = 100
        from_block = 10
        data = '0x00000000000000000000000000000000000000000000000002501e734690aaab000000000000000000000000000000000000000000000000000000005a6af820'  # noqa
        events = []
        self.geth_client.get_block_number.return_value = block_number
        self.sci._monitor_blockchain_single()

        self.geth_client.get_logs.return_value = []
        self.sci.subscribe_to_batch_transfers(
            None,
            receiver_address,
            from_block,
            lambda e: events.append(e),
        )

        self.geth_client.get_logs.assert_called_once_with(
            mock.ANY,
            'BatchTransfer',
            {'from': None, 'to': receiver_address},
            from_block,
            block_number - self.sci.REQUIRED_CONFS + 1,
        )

        self.geth_client.get_logs.return_value = [
            {
                'removed': False,
                'transactionHash': HexBytes(tx_hash),
                'blockNumber': block_number,
                'topics': [
                    '',
                    HexBytes('0x' + '0' * 24 + sender_address[2:]),
                    HexBytes('0x' + '0' * 24 + receiver_address[2:]),
                ],
                'data': data,
                'logIndex': 0,
            } for tx_hash in tx_hashes
        ]
        self.sci._monitor_blockchain_single()
        assert 0 == len(events)

        new_block_number = 200
        self.geth_client.get_filter_changes.return_value = []
        self.geth_client.get_block_number.return_value = new_block_number
        self.sci._monitor_blockchain_single()
        assert len(tx_hashes) == len(events)
        for i, tx_hash in enumerate(tx_hashes):
            assert tx_hash == events[i].tx_hash
            assert sender_address == events[i].sender
            assert receiver_address == events[i].receiver
            assert 166666666666666667 == events[i].amount
            assert 1516959776 == events[i].closure_time
        events = []

        self.sci._monitor_blockchain_single()
        assert 0 == len(events)

        # Testing network loss
        newest_block_number = 300
        self.geth_client.get_logs.reset_mock()
        self.geth_client.get_block_number.return_value = newest_block_number
        self.geth_client.get_logs.side_effect = Exception
        self.sci._monitor_blockchain_single()
        self.geth_client.get_logs.assert_called_once_with(
            mock.ANY,
            'BatchTransfer',
            {'from': None, 'to': receiver_address},
            new_block_number - self.sci.REQUIRED_CONFS + 1 + 1,
            newest_block_number - self.sci.REQUIRED_CONFS + 1,
        )
        assert 0 == len(events)

        newest_block_number += 1
        self.geth_client.get_logs.reset_mock()
        self.geth_client.get_block_number.return_value = newest_block_number
        self.geth_client.get_logs.side_effect = None
        self.sci._monitor_blockchain_single()
        self.geth_client.get_logs.assert_called_once_with(
            mock.ANY,
            'BatchTransfer',
            {'from': None, 'to': receiver_address},
            new_block_number - self.sci.REQUIRED_CONFS + 1 + 1,
            newest_block_number - self.sci.REQUIRED_CONFS + 1,
        )

    def test_on_transaction_confirmed(self):
        tx_hash = '0x' + 'a' * 40
        gas_used = 1234
        block_number = 100
        block_hash = '0xbbbb'
        receipt = []

        def cb(tx_receipt):
            receipt.append(tx_receipt)

        self.sci.on_transaction_confirmed(tx_hash, cb)

        self.geth_client.get_block_number.return_value = block_number - 1
        self.geth_client.get_transaction_receipt.return_value = None
        self.sci._monitor_blockchain_single()
        assert not receipt

        self.geth_client.get_block_number.return_value = block_number
        self.geth_client.get_transaction_receipt.return_value = {
            'transactionHash': HexBytes(tx_hash),
            'status': 1,
            'gasUsed': gas_used,
            'blockNumber': block_number,
            'blockHash': HexBytes(block_hash),
        }
        self.sci._monitor_blockchain_single()
        assert not receipt

        self.geth_client.get_block_number.return_value = \
            block_number + self.sci.REQUIRED_CONFS - 2
        self.sci._monitor_blockchain_single()
        assert not receipt

        self.geth_client.get_block_number.return_value = \
            block_number + self.sci.REQUIRED_CONFS + 1
        self.sci._monitor_blockchain_single()
        assert 1 == len(receipt)
        assert receipt[0].status
        assert gas_used == receipt[0].gas_used
        assert block_number == receipt[0].block_number
        assert block_hash == receipt[0].block_hash

        del receipt[:]
        self.sci._monitor_blockchain_single()
        assert not receipt

    def test_missing_contracts(self):
        contract_addresses = {}

        # Constructor shouldn't throw when there are missing contracts' data
        sci = SCIImplementation(
            self.geth_client,
            get_eth_address(),
            self.storage,
            contract_addresses,
            monitor=False,
        )
        # But we can't use them then
        with self.assertRaises(Exception):
            sci.transfer_gnt('0xdead', 123)
