from typing import Any, List

from ethereum import abi
from ethereum.transactions import Transaction
from eth_utils import decode_hex


class ContractWrapper:
    def __init__(self, actor_address: str, contract):
        self._actor_address = actor_address
        self._contract = contract
        self._translator = abi.ContractTranslator(contract.abi)
        self.address = contract.address

    def call(self):
        return self._contract.call({'from': self._actor_address})

    def create_transaction(
            self,
            function_name: str,
            args: List[Any],
            nonce: int,
            gas_price: int,
            gas_limit: int) -> Transaction:
        data = self._translator.encode_function_call(function_name, args)
        return Transaction(
            nonce=nonce,
            gasprice=gas_price,
            startgas=gas_limit,
            to=decode_hex(self._contract.address),
            value=0,
            data=data,
        )

    def on(self, event_name: str, from_block, to_block, arg_filters):
        return self._contract.on(
            event_name,
            filter_params={
                'fromBlock': from_block,
                'toBlock': to_block,
                'filter': arg_filters,
            },
        ).filter_id
