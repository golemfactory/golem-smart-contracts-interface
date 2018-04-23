from typing import Any, Dict


class Block:
    def __init__(self, raw_block: Dict[str, Any]) -> None:
        self.number: int = raw_block['number']
        self.timestamp: int = raw_block['timestamp']
        self.gas_limit: int = raw_block['gasLimit']

    def __str__(self) -> str:
        return '<Block number: {} timestamp: {} gas limit: {}>'.format(
            self.number,
            self.timestamp,
            self.gas_limit,
        )


class TransactionReceipt:
    def __init__(self, raw_receipt: Dict[str, Any]):
        self.tx_hash: str = raw_receipt['transactionHash']
        self.status: bool = raw_receipt['status'] == 1
        self.block_hash: str = raw_receipt['blockHash']
        self.block_number: int = raw_receipt['blockNumber']
        self.gas_used: int = raw_receipt['gasUsed']

    def __str__(self) -> str:
        return '<TransactionReceipt hash: {} status: {} block number: {} '\
            'gas used: {}>'.format(
                self.tx_hash,
                self.status,
                self.block_number,
                self.gas_used,
            )