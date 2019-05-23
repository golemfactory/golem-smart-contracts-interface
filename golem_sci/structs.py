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
    def __init__(self, raw_receipt: Dict[str, Any]) -> None:
        self.tx_hash: str = raw_receipt['transactionHash'].hex()
        self.status: bool = raw_receipt['status'] == 1
        self.block_hash: str = raw_receipt['blockHash'].hex()
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


class DirectEthTransfer:
    def __init__(self, raw_tx: Dict[str, Any]) -> None:
        self.tx_hash: str = raw_tx['hash'].hex()
        self.from_address: str = raw_tx['from']
        self.to_address: str = raw_tx['to']
        self.amount: int = raw_tx['value']


class Payment:
    def __init__(self, payee: str, amount: int) -> None:
        self.payee: str = payee
        self.amount: int = amount
