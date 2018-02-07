from typing import Dict, Any

from ethereum.utils import denoms


class BatchTransferEvent:
    def __init__(self, raw_log: Dict[str, Any]):
        self.tx_hash = raw_log['transactionHash']
        self.sender = '0x' + raw_log['topics'][1][26:]
        self.receiver = '0x' + raw_log['topics'][2][26:]
        self.amount = int(raw_log['data'][2:66], 16)
        self.closure_time = int(raw_log['data'][66:130], 16)

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
    def __init__(
            self,
            tx_hash: str,
            requestor: str,
            provider: str,
            amount: int,
            subtask_id: str):
        self.tx_hash = tx_hash
        self.requestor = requestor
        self.provider = provider
        self.amount = amount
        self.subtask_id = subtask_id


class ForcedPaymentEvent:
    def __init__(
            self,
            tx_hash: str,
            requestor: str,
            provider: str,
            amount: int,
            closure_time: int):
        self.tx_hash = tx_hash
        self.requestor = requestor
        self.provider = provider
        self.amount = amount
        self.closure_time = closure_time


class CoverAdditionalVerificationEvent:
    def __init__(
            self,
            tx_hash: str,
            address: str,
            amount: int):
        self.tx_hash = tx_hash
        self.address = address
        self.amount = amount
