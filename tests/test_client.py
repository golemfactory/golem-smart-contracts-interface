from unittest import TestCase, mock

from golem_sci.client import Client, get_timestamp_utc


class EthereumClientTest(TestCase):
    def setUp(self):
        super().setUp()
        self.web3 = mock.Mock()
        self.client = Client(self.web3)
        self.client.SYNC_CHECK_INTERVAL = 0

    def test_synchronized2(self):
        self.web3.net.peerCount = 0
        assert not self.client.is_synchronized()

        self.web3.net.peerCount = 1
        self.web3.eth.syncing = {
            "currentBlock": 1,
            "highestBlock": 2,
        }
        assert not self.client.is_synchronized()

        self.web3.eth.syncing = False
        self.web3.eth.getBlock.return_value = {'timestamp': get_timestamp_utc()}
        assert self.client.is_synchronized()

    def test_wait_until_synchronized(self):
        self.web3.net.peerCount = 1
        self.web3.eth.syncing = {
            "currentBlock": 1,
            "highestBlock": 1,
        }
        assert self.client.wait_until_synchronized()

    def test_synchronized(self):
        syncing_status = {'startingBlock': '0x384',
                          'currentBlock': '0x386',
                          'highestBlock': '0x454'}
        combinations = ((0, False),
                        (0, syncing_status),
                        (1, False),
                        (1, syncing_status),
                        (65, syncing_status),
                        (65, False))

        self.web3.eth.syncing = {
            'currentBlock': 123,
            'highestBlock': 1234,
        }
        self.web3.eth.getBlock.return_value = {"timestamp": get_timestamp_utc()}

        for c in combinations:
            print("Subtest {}".format(c))
            self.web3.net.peerCount = c[0]
            self.web3.eth.syncing = c[1]
            assert self.client.is_synchronized() == (c[0] and not c[1])
