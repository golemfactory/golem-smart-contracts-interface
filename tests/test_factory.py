import unittest.mock as mock
import unittest

from golem_sci import new_sci, CHAIN_RINKEBY
from golem_sci.factory import GENESES, _ensure_genesis, _ensure_connection


class SCIImplementationTest(unittest.TestCase):
    @mock.patch('golem_sci.factory._ensure_connection')
    @mock.patch('golem_sci.factory._ensure_genesis')
    @mock.patch('golem_sci.implementation.SCIImplementation.__init__')
    def test_new_sci(self, sci_init, ensure_genesis, ensure_connection):
        def tx_sign(tx):
            pass
        sci_init.return_value = None
        eth_address = '0xdeafbeef'
        web3 = mock.Mock()

        new_sci(web3, eth_address, tx_sign, chain=CHAIN_RINKEBY)
        ensure_connection.assert_called_once_with(web3)
        ensure_genesis.assert_called_once_with(web3, CHAIN_RINKEBY)
        sci_init.assert_called_once_with(mock.ANY, eth_address, tx_sign)

    def test_ensure_genesis_valid(self):
        web3 = mock.Mock()
        web3.eth.getBlock.return_value = {
            'hash': GENESES[CHAIN_RINKEBY],
        }
        _ensure_genesis(web3, CHAIN_RINKEBY)
        web3.eth.getBlock.assert_called_once_with(0)

    def test_ensure_genesis_invalid(self):
        web3 = mock.Mock()
        web3.eth.getBlock.return_value = {
            'hash': '0xaaa',
        }
        try:
            _ensure_genesis(web3, CHAIN_RINKEBY)
        except Exception as e:
            pass
        else:
            assert False, 'Exception has not been thrown'
        web3.eth.getBlock.assert_called_once_with(0)

    def test_ensure_connection(self):
        web3 = mock.Mock()
        web3.isConnected.return_value = True
        _ensure_connection(web3)
        web3.isConnected.assert_called_once_with()

        web3.isConnected.reset_mock()
        web3.isConnected.return_value = False
        try:
            with mock.patch('time.sleep'):
                _ensure_connection(web3)
        except Exception as e:
            pass
        else:
            assert False, 'Exception has not been thrown'
        assert web3.isConnected.call_count > 1
