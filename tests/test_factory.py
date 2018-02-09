import unittest.mock as mock
import unittest

from golem_sci import new_sci, CHAIN_RINKEBY
from golem_sci.factory import GENESES


class SCIImplementationTest(unittest.TestCase):
    @mock.patch('golem_sci.implementation.SCIImplementation.__init__')
    def test_ensure_genesis_valid(self, sci_init):
        sci_init.return_value = None
        web3 = mock.Mock()
        web3.eth.getBlock.return_value = {
            'hash': GENESES[CHAIN_RINKEBY],
        }
        eth_address = '0xdeafbeef'

        def tx_sign(tx):
            pass
        new_sci(web3, eth_address, tx_sign, chain=CHAIN_RINKEBY)
        web3.eth.getBlock.assert_called_once_with(0)
        sci_init.assert_called_once_with(mock.ANY, '0xdeafbeef', tx_sign)

    @mock.patch('golem_sci.implementation.SCIImplementation.__init__')
    def test_ensure_genesis_invalid(self, sci_init):
        sci_init.return_value = None
        web3 = mock.Mock()
        web3.eth.getBlock.return_value = {
            'hash': '0xaaa',
        }
        try:
            new_sci(web3, '0xdeafbeef', chain=CHAIN_RINKEBY)
        except Exception as e:
            pass
        else:
            assert False, 'Exception has not been thrown'
        web3.eth.getBlock.assert_called_once_with(0)
        sci_init.assert_not_called()
