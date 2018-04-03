from typing import Dict, Any

from ethereum.utils import denoms
from eth_utils import decode_hex


class BatchTransferEvent:
    def __init__(self, raw_log: Dict[str, Any]):
        self.tx_hash: str = raw_log['transactionHash']
        self.sender: str = '0x' + raw_log['topics'][1][26:]
        self.receiver: str = '0x' + raw_log['topics'][2][26:]
        self.amount: int = int(raw_log['data'][2:66], 16)
        self.closure_time: int = int(raw_log['data'][66:130], 16)

    def __str__(self) -> str:
        return '<BatchTransferEvent tx: {} sender: {} receiver: {} amount: {} '\
            'closure_time: {}>'.format(
                self.tx_hash,
                self.sender,
                self.receiver,
                self.amount / denoms.ether,
                self.closure_time,
            )


class ForcedSubtaskPaymentEvent:
    def __init__(self, raw_log: Dict[str, Any]):
        self.tx_hash: str = raw_log['transactionHash']
        self.requestor: str = '0x' + raw_log['topics'][1][26:]
        self.provider: str = '0x' + raw_log['topics'][2][26:]
        self.amount: int = int(raw_log['data'][2:66], 16)
        self.subtask_id: str = \
            decode_hex(raw_log['data'][66:130]).decode('utf-8').rstrip('\0')


class ForcedPaymentEvent:
    def __init__(self, raw_log: Dict[str, Any]):
        self.tx_hash: str = raw_log['transactionHash']
        self.requestor: str = '0x' + raw_log['topics'][1][26:]
        self.provider: str = '0x' + raw_log['topics'][2][26:]
        self.amount: int = int(raw_log['data'][2:66], 16)
        self.closure_time: int = int(raw_log['data'][66:130], 16)


class CoverAdditionalVerificationEvent:
    def __init__(
            self,
            tx_hash: str,
            address: str,
            amount: int):
        self.tx_hash = tx_hash
        self.address = address
        self.amount = amount
