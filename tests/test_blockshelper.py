import unittest.mock as mock
import unittest

from golem_sci.blockshelper import BlocksHelper


class BlocksHelperTest(unittest.TestCase):
    def setUp(self):
        self.sci = mock.Mock()
        self.bh = BlocksHelper(self.sci)

    def test_get_latest_existing_block_at(self):
        blocks = []
        for i in range(9):
            block = mock.Mock()
            block.number = i
            block.timestamp = (i + 1) * 11
            blocks.append(block)
        self.sci.get_block_number.return_value = 8
        self.sci.get_block_by_number.side_effect = lambda number: blocks[number]

        assert self.bh.get_latest_existing_block_at(0) == blocks[0]
        assert self.bh.get_latest_existing_block_at(11) == blocks[1]
        assert self.bh.get_latest_existing_block_at(21) == blocks[1]
        assert self.bh.get_latest_existing_block_at(55) == blocks[5]
        assert self.bh.get_latest_existing_block_at(98) == blocks[8]
        assert self.bh.get_latest_existing_block_at(99) == blocks[8]
        assert self.bh.get_latest_existing_block_at(111) == blocks[8]
