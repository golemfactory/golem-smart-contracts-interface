from ethereum.utils import denoms


class BatchTransferEvent:
    def __init__(
            self,
            tx_hash: str,
            sender: str,
            receiver: str,
            amount: int,
            closure_time: int):
        self.tx_hash = tx_hash
        self.sender = sender
        self.receiver = receiver
        self.amount = amount
        self.closure_time = closure_time

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
