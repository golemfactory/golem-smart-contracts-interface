from unittest import mock, TestCase

from golem_sci.gntconverter import GNTConverter


class GNTConverterTest(TestCase):
    def setUp(self):
        self.sci = mock.Mock()
        self.converter = GNTConverter(self.sci)

    def test_flow(self):
        assert not self.converter.is_converting()

        amount = 123
        gate_address = '0xdead'
        self.sci.get_gate_address.return_value = None
        pending_tx_cb = []
        self.sci.on_transaction_confirmed.side_effect = \
            lambda hash, confs, cb: pending_tx_cb.append(cb)

        self.converter.convert(amount)
        assert self.converter.is_converting()
        self.sci.open_gate.assert_called_once_with()
        assert len(pending_tx_cb) == 1

        self.sci.get_gate_address.return_value = gate_address
        pending_tx_cb[0](mock.Mock())
        assert self.converter.is_converting()
        self.sci.transfer_gnt.assert_called_once_with(gate_address, amount)
        assert len(pending_tx_cb) == 2

        pending_tx_cb[1](mock.Mock())
        assert self.converter.is_converting()
        self.sci.transfer_from_gate.assert_called_once_with()
        assert len(pending_tx_cb) == 3

        pending_tx_cb[2](mock.Mock())
        assert not self.converter.is_converting()
