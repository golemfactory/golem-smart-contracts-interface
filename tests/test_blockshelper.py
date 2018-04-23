import unittest.mock as mock
import unittest

from golem_sci.blockshelper import BlocksHelper


class BlocksHelperTest(unittest.TestCase):
    def setUp(self):
        self.sci = mock.Mock()
        self.bh = BlocksHelper(self.sci)

    def test_get_first_block_after(self):
        blocks = []
        for i in range(9):
            block = mock.Mock()
            block.number = i
            block.timestamp = (i + 1) * 11
            blocks.append(block)
        self.sci.get_block_number.return_value = 8
        self.sci.get_block_by_number.side_effect = lambda number: blocks[number]

        assert self.bh.get_first_block_after(0) == blocks[0]
        assert self.bh.get_first_block_after(11) == blocks[1]
        assert self.bh.get_first_block_after(21) == blocks[1]
        assert self.bh.get_first_block_after(55) == blocks[5]
        assert self.bh.get_first_block_after(98) == blocks[8]
        with self.assertRaisesRegex(ValueError, 'no blocks after'):
            self.bh.get_first_block_after(99)
