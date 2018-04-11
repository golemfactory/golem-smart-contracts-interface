import json
import logging
import pytz
import rlp
import time
from calendar import timegm
from datetime import datetime

from ethereum.utils import zpad

logger = logging.getLogger('golem_sci.client')


class FilterNotFoundException(Exception):
    pass


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
        self._last_sync_check = time.time()
        self._sync = False

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
            last_block = self.web3.eth.getBlock('latest')
        except Exception as ex:
            logger.debug(ex)
            return False
        if isinstance(last_block, dict):
            timestamp = int(last_block['timestamp'])
        else:
            timestamp = last_block.timestamp
        return get_timestamp_utc() - timestamp > 120

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

    def send(self, transaction):
        """
        Sends signed Ethereum transaction.
        :return The 32 Bytes transaction hash as HEX string
        """
        raw_data = rlp.encode(transaction)
        hex_data = self.web3.toHex(raw_data)
        return self.web3.eth.sendRawTransaction(hex_data)

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
        try:
            return self.web3.eth.getBalance(account, block)
        except ValueError as e:
            logger.error("Ethereum RPC: {}".format(e))
            return None

    def get_gas_price(self) -> int:
        return self.web3.eth.gasPrice

    def call(self, _from=None, to=None, gas=90000, gas_price=3000, value=0,
             data=None, block=None):
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

    def get_block_number(self):
        return self.web3.eth.blockNumber

    def get_transaction(self, tx_hash):
        """
        Returns a transaction matching the given transaction hash.
        :param tx_hash: The transaction hash
        :return: Object - A transaction object
        """
        return self.web3.eth.getTransaction(tx_hash)

    def get_transaction_receipt(self, tx_hash):
        """
        Returns the receipt of a transaction by transaction hash.
        :param tx_hash: The transaction hash
        :return: Receipt of a transaction
        """
        return self.web3.eth.getTransactionReceipt(tx_hash)

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
            for i in range(len(topics)):
                topics[i] = Client.__add_padding(topics[i])
        obj = {
            'fromBlock': from_block,
            'toBlock': to_block,
            'address': address,
            'topics': topics
        }
        return self.web3.eth.filter(obj).filter_id

    def get_filter_changes(self, filter_id):
        """
        Polling method for a filter,
        which returns an array of logs which occurred since last poll
        :param filter_id: the filter id
        :return:
        Returns all new entries which occurred since the
        last call to this method for the given filter_id
        """
        return Client._convert_filter_not_found_error(
            lambda: self.web3.eth.getFilterChanges(filter_id),
        )

    def get_filter_logs(self, filter_id):
        """
        Polling method for a filter which returns an array of all matching logs
        :param filter_id: the filter id
        :return:
        Returns all entries which match the filter
        """
        return Client._convert_filter_not_found_error(
            lambda: self.web3.eth.getFilterLogs(filter_id),
        )

    @staticmethod
    def _convert_filter_not_found_error(f):
        try:
            return f()
        except ValueError as e:
            if e.args[0]['message'] == 'filter not found':
                raise FilterNotFoundException()
            raise e

    def get_logs(self,
                 from_block=None,
                 to_block=None,
                 address=None,
                 topics=None):
        """
        Retrieves logs based on filter options
        :param from_block: Integer block number,
        or "latest" for the last mined block
        or "pending", "earliest" for not yet mined transactions
        :param to_block: Integer block number,
        or "latest" for the last mined block
        or "pending", "earliest" for not yet mined transactions
        :param address:
        Contract address or a list of addresses from which logs should originate
        :param topics:
        Array of 32 Bytes DATA topics.
        Topics are order-dependent.
        Each topic can also be an array of DATA with "or" options
        topic[hash, from, to]
        The first topic is the hash of the signature of the event
        (e.g. Deposit(address,bytes32,uint256)),
        except you declared the event with the anonymous specifier.)
        :return: Returns log entries described by filter options
        """
        for i in range(len(topics)):
            topics[i] = Client.__add_padding(topics[i])
        filter_id = self.new_filter(from_block, to_block, address, topics)
        return self.get_filter_logs(filter_id)

    def contract(self, address, abi):
        return self.web3.eth.contract(address=address, abi=json.loads(abi))

    def wait_until_synchronized(self) -> bool:
        is_synchronized = False
        while not is_synchronized:
            try:
                is_synchronized = self.is_synchronized()
            except Exception as e:
                logger.error("Error "
                             "while syncing with eth blockchain: "
                             "{}".format(e))
                is_synchronized = False
            else:
                time.sleep(self.SYNC_CHECK_INTERVAL)

        return True

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
