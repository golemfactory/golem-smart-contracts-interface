import json
import logging
import time
from calendar import timegm
from datetime import datetime
from typing import Any, Dict, Union

from ethereum.utils import zpad
import pytz
import rlp
from web3.utils.filters import construct_event_filter_params

from . import exceptions

logger = logging.getLogger(__name__)


def datetime_to_timestamp(then):
    return timegm(then.utctimetuple()) + then.microsecond / 1000000.0


def get_timestamp_utc():
    now = datetime.now(pytz.utc)
    return datetime_to_timestamp(now)


class Client(object):
    """ RPC interface client for Ethereum node."""

    SYNC_CHECK_INTERVAL = 10

    def __init__(self, web3):
        self.web3 = web3
        # Set fake default account.
        self.web3.eth.defaultAccount = '\xff' * 20
        self._last_sync_check = 0
        self._sync = False
        self._is_stopped = False

    @exceptions.map_errors()
    def get_peer_count(self):
        """
        Get peers count
        :return: The number of peers currently connected to the client
        """
        return self.web3.net.peerCount

    def is_syncing(self):
        """
        :return: Returns either False if the node is not syncing, True otherwise
        """
        syncing = self.web3.eth.syncing
        if syncing:
            logger.info(
                "currentBlock: %r\t highestBlock: %r",
                syncing['currentBlock'],
                syncing['highestBlock'],
            )
            return syncing['currentBlock'] < syncing['highestBlock']

        # node may not have started syncing yet
        try:
            last_block = self.get_block('latest')
        except Exception as e:  # pylint: disable=broad-except
            logger.debug('Error while getting block. Ignoring', exc_info=e)
            return False
        if isinstance(last_block, dict):
            timestamp = int(last_block['timestamp'])
        else:
            timestamp = last_block.timestamp
        return get_timestamp_utc() - timestamp > 120

    @exceptions.map_errors()
    def get_block(
            self,
            block: Union[int, str],
            full_transactions: bool = False,
    ):
        return self.web3.eth.getBlock(block, full_transactions)

    @exceptions.map_errors()
    def get_transaction_count(self, address):
        """
        Returns the number of transactions that have been sent from account.
        Use `pending` block to account the transactions that haven't been mined
        yet. Otherwise it would be problematic to send more than one transaction
        in less than ~15 seconds span.
        :param address: account address
        :return: number of transactions
        """
        return self.web3.eth.getTransactionCount(address, 'pending')

    @exceptions.map_errors()
    def estimate_gas(self, tx: Dict[str, Any]) -> int:
        return self.web3.eth.estimateGas(tx)

    @exceptions.map_errors()
    def send(self, transaction) -> str:
        """
        Sends signed Ethereum transaction.
        :return The 32 Bytes transaction hash as HEX string
        """
        raw_data = rlp.encode(transaction)
        hex_data = self.web3.toHex(raw_data)
        return self.web3.eth.sendRawTransaction(hex_data).hex()

    @exceptions.map_errors()
    def get_balance(self, account, block=None):
        """
        Returns the balance of the given account
        at the block specified by block_identifier
        :param account: The address to get the balance of
        :param block: If you pass this parameter
        it will not use the default block
        set with web3.eth.defaultBlock
        :return: Balance
        """
        return self.web3.eth.getBalance(account, block)

    @exceptions.map_errors()
    def get_gas_price(self) -> int:
        return self.web3.eth.gasPrice

    @exceptions.map_errors()
    def call(  # pylint: disable=too-many-arguments
            self,
            _from=None,
            to=None,
            gas=90000,
            gas_price=3000,
            value=0,
            data=None,
            block=None,
    ):
        """
        Executes a message call transaction,
        which is directly executed in the VM of the node,
        but never mined into the blockchain
        :param _from: The address for the sending account
        :param to: The destination address of the message,
        left undefined for a contract-creation transaction
        :param gas: The value transferred for the transaction in Wei,
        also the endowment if it's a contract-creation transaction
        :param gas_price:
        The amount of gas to use for the transaction
        (unused gas is refunded)
        :param value:
        The price of gas for this transaction in wei,
        defaults to the mean network gas price
        :param data:
        Either a byte string containing the associated data of the message,
        or in the case of a contract-creation transaction,
        the initialisation code
        :param block:
        integer block number,
        or the string "latest", "earliest" or "pending"
        :return:
        The returned data of the call,
        e.g. a codes functions return value
        """
        obj = {
            'from': _from,
            'to': to,
            'gas': gas,
            'gasPrice': gas_price,
            'value': value,
            'data': data,
        }
        return self.web3.eth.call(obj, block)

    @exceptions.map_errors()
    def get_block_number(self):
        return self.web3.eth.blockNumber

    @exceptions.map_errors()
    def get_transaction(self, tx_hash):
        """
        Returns a transaction matching the given transaction hash.
        :param tx_hash: The transaction hash
        :return: Object - A transaction object
        """
        return self.web3.eth.getTransaction(tx_hash)

    @exceptions.map_errors()
    def get_transaction_receipt(self, tx_hash):
        """
        Returns the receipt of a transaction by transaction hash.
        :param tx_hash: The transaction hash
        :return: Receipt of a transaction
        """
        return self.web3.eth.getTransactionReceipt(tx_hash)

    @exceptions.map_errors()
    def new_filter(self, from_block="latest", to_block="latest", address=None,
                   topics=None):
        """
        Creates a filter object, based on filter options,
        to notify when the state changes (logs)
        :param from_block:
        Integer block number, or "latest" for the last mined block
        or "pending", "earliest" for not yet mined transactions
        :param to_block:
        Integer block number, or "latest" for the last mined block
        or "pending", "earliest" for not yet mined transactions
        :param address:
        Contract address or a list of addresses from which logs should originate
        :param topics:
        Array of 32 Bytes DATA topics. Topics are order-dependent.
        Each topic can also be an array of DATA with "or" options
        :return: filter id
        """
        if topics is not None:
            for i, topic in enumerate(topics[:]):
                topics[i] = self.__add_padding(topic)
        obj = {
            'fromBlock': from_block,
            'toBlock': to_block,
            'address': address,
            'topics': topics
        }
        return self.web3.eth.filter(obj).filter_id

    @exceptions.map_errors()
    def get_filter_changes(self, filter_id):
        """
        Polling method for a filter,
        which returns an array of logs which occurred since last poll
        :param filter_id: the filter id
        :return:
        Returns all new entries which occurred since the
        last call to this method for the given filter_id
        """
        return self.web3.eth.getFilterChanges(filter_id)

    @exceptions.map_errors()
    def get_filter_logs(self, filter_id):
        """
        Polling method for a filter which returns an array of all matching logs
        :param filter_id: the filter id
        :return:
        Returns all entries which match the filter
        """
        return self.web3.eth.getFilterLogs(filter_id)

    @exceptions.map_errors()
    def get_logs(  # pylint: disable=too-many-arguments
            self,
            contract,
            event_name: str,
            args,
            from_block: Union[int, str],
            to_block: Union[int, str]):
        event_abi = list(filter(
            lambda e: e['type'] == 'event' and e['name'] == event_name,
            contract.abi,
        ))[0]
        for name in args:
            assert any(name == event['name'] for event in event_abi['inputs'])
        _, filter_args = construct_event_filter_params(
            event_abi,
            contract_address=contract.address,
            argument_filters=args,
            fromBlock=from_block,
            toBlock=to_block,
        )
        return self.web3.eth.getLogs(filter_args)

    @exceptions.map_errors()
    def contract(self, address, abi):
        return self.web3.eth.contract(address=address, abi=json.loads(abi))

    def wait_until_synchronized(self):
        while not self._is_stopped:
            try:
                if self.is_synchronized():
                    return
            except Exception as e:  # pylint: disable=broad-except
                logger.error(
                    "Error while syncing with eth blockchain: %r", e)
            else:
                time.sleep(self.SYNC_CHECK_INTERVAL)

    def is_synchronized(self):
        """ Checks if the Ethereum node is in sync with the network."""
        if time.time() - self._last_sync_check <= self.SYNC_CHECK_INTERVAL:
            return self._sync
        self._last_sync_check = time.time()

        synced = True

        peers = self.get_peer_count()
        logger.debug("Geth peer count: %d", peers)
        if peers == 0:
            synced = False
        elif self.is_syncing():
            logger.info("Geth node is syncing...")
            synced = False

        if synced and not self._sync:
            logger.info("Geth node is synchronized")

        self._sync = synced
        return self._sync

    def stop(self):
        self._is_stopped = True

    @staticmethod
    def __add_padding(address):
        """
        Provide proper length of address and add 0x to it
        :param address: Address to validation
        :return: Padded address
        """
        if address is None:
            return address
        elif isinstance(address, str):
            if address.startswith('0x'):
                address = address[2:]
            address = '0x' + '0' * (64 - len(address)) + address
            address = address.encode()
        if isinstance(address, bytes):
            if address.startswith(b'0x'):
                return address
            return b'0x' + zpad(address, 32)
        raise TypeError('Address must be a string or a byte string')
