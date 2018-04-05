from unittest import mock, TestCase

from golem_sci.gntconverter import GNTConverter


class GNTConverterTest(TestCase):
    def setUp(self):
        self.sci = mock.Mock()

    def test_flow(self):
        self.sci.get_gate_address.return_value = None
        converter = GNTConverter(self.sci)
        assert not converter.is_converting()
        assert converter.get_gate_balance() == 0

        amount = 123
        gate_address = '0xdead'
        self.sci.get_gate_address.return_value = None
        pending_tx_cb = []
        self.sci.on_transaction_confirmed.side_effect = \
            lambda hash, confs, cb: pending_tx_cb.append(cb)

        converter.convert(amount)
        assert converter.is_converting()
        assert converter.get_gate_balance() == 0
        self.sci.open_gate.assert_called_once_with()
        assert len(pending_tx_cb) == 1

        self.sci.get_gate_address.return_value = gate_address
        pending_tx_cb[0](mock.Mock())
        assert converter.is_converting()
        converter.get_gate_balance()
        self.sci.get_gnt_balance.assert_called_once_with(gate_address)
        self.sci.transfer_gnt.assert_called_once_with(gate_address, amount)
        assert len(pending_tx_cb) == 2

        pending_tx_cb[1](mock.Mock())
        assert converter.is_converting()
        self.sci.transfer_from_gate.assert_called_once_with()
        assert len(pending_tx_cb) == 3

        pending_tx_cb[2](mock.Mock())
        assert not converter.is_converting()
        assert converter.get_gate_balance() == 0

    def test_unfinished_conversion(self):
        gate_address = '0xdead'
        self.sci.get_gate_address.return_value = gate_address
        self.sci.get_gnt_balance.return_value = 123
        converter = GNTConverter(self.sci)

        self.sci.get_gnt_balance.assert_called_once_with(gate_address)
        self.sci.transfer_from_gate.assert_called_once_with()
        assert converter.is_converting()
