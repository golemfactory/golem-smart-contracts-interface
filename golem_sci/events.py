from typing import Dict, Any

from ethereum.utils import denoms
from eth_utils import decode_hex, to_checksum_address


class BatchTransferEvent:
    def __init__(self, raw_log: Dict[str, Any]) -> None:
        self.tx_hash: str = raw_log['transactionHash'].hex()
        self.sender: str = \
            to_checksum_address('0x' + raw_log['topics'][1].hex()[26:])
        self.receiver: str = \
            to_checksum_address('0x' + raw_log['topics'][2].hex()[26:])
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
    def __init__(self, raw_log: Dict[str, Any]) -> None:
        self.tx_hash: str = raw_log['transactionHash'].hex()
        self.requestor: str = \
            to_checksum_address('0x' + raw_log['topics'][1].hex()[26:])
        self.provider: str = \
            to_checksum_address('0x' + raw_log['topics'][2].hex()[26:])
        self.amount: int = int(raw_log['data'][2:66], 16)
        self.subtask_id: bytes = decode_hex(raw_log['data'][66:130])


class ForcedPaymentEvent:
    def __init__(self, raw_log: Dict[str, Any]) -> None:
        self.tx_hash: str = raw_log['transactionHash'].hex()
        self.requestor: str = \
            to_checksum_address('0x' + raw_log['topics'][1].hex()[26:])
        self.provider: str = \
            to_checksum_address('0x' + raw_log['topics'][2].hex()[26:])
        self.amount: int = int(raw_log['data'][2:66], 16)
        self.closure_time: int = int(raw_log['data'][66:130], 16)


class CoverAdditionalVerificationEvent:
    def __init__(self, raw_log: Dict[str, Any]) -> None:
        self.tx_hash: str = raw_log['transactionHash'].hex()
        self.address: str = \
            to_checksum_address('0x' + raw_log['topics'][1].hex()[26:])
        self.amount: int = int(raw_log['data'][2:66], 16)
        self.subtask_id: bytes = decode_hex(raw_log['data'][66:130])
