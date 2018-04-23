from .interface import SmartContractsInterface
from .structs import Block


class BlocksHelper:
    def __init__(self, sci: SmartContractsInterface) -> None:
        self._sci = sci

    def get_first_block_after(self, timestamp: int) -> Block:
        """
        Returns block with smallest number for which
        `block.timestamp > timestamp` is satisfied.
        """
        lo = -1
        hi = self._sci.get_block_number()
        while lo + 1 < hi:
            mid = (lo + hi) // 2
            if self._sci.get_block_by_number(mid).timestamp > timestamp:
                hi = mid
            else:
                lo = mid
        res = self._sci.get_block_by_number(hi)
        if res.timestamp <= timestamp:
            raise ValueError(
                'There are currently no blocks after {}'.format(timestamp))
        return res