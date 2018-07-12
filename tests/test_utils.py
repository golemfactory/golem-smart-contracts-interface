import unittest

from golem_sci.utils import privkey_to_checksum_address


class UtilsTest(unittest.TestCase):
    def test_privkey_to_checksum_address(self):
        eth_address = privkey_to_checksum_address(
            b'call me highway call me conduit ')
        self.assertEqual(
            eth_address, '0xE6e819FA910f150800C91D218DFAD0C810F990F0')

    def test_privkey_to_checksum_address_fail(self):
        with self.assertRaises(ValueError):
            privkey_to_checksum_address(
                b'call me highway call me conduit '
                b'call my lightning rod scout catalyst observer'
            )
