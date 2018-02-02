import json
import logging
from typing import List, Any, Optional

from ethereum import abi, utils, keys
from ethereum.transactions import Transaction

from golem_sci.client import Client
from eth_utils import decode_hex, encode_hex
from golem_sci import contracts

logger = logging.getLogger("golem_sci.token")


def encode_payments(payments):
    paymap = {}
    for p in payments:
        if p.payee in paymap:
            paymap[p.payee] += p.value
        else:
            paymap[p.payee] = p.value

    args = []
    value = 0
    for to, v in paymap.items():
        max_value = 2 ** 96
        if v >= max_value:
            raise ValueError("v should be less than {}".format(max_value))
        value += v
        v = utils.zpad(utils.int_to_big_endian(v), 12)
        pair = v + to
        if len(pair) != 32:
            raise ValueError(
                "Incorrect pair length: {}. Should be 32".format(len(pair)))
        args.append(pair)
    return args


class GNTWToken():
    # Gas price: 20 gwei, Homestead suggested gas price.
    GAS_PRICE = 20 * 10 ** 9

    # Total gas for a batchTransfer is BASE + len(payments) * PER_PAYMENT
    GAS_PER_PAYMENT = 30000
    # tx: 21000, balance substract: 5000, arithmetics < 800
    GAS_BATCH_PAYMENT_BASE = 21000 + 800 + 5000

    # keccak256(BatchTransfer(address,address,uint256,uint64))
    TRANSFER_EVENT_ID = '0x24310ec9df46c171fe9c6d6fe25cac6781e7fa8f153f8f72ce63037a4b38c4b6'  # noqa

    CREATE_PERSONAL_DEPOSIT_GAS = 320000
    PROCESS_DEPOSIT_GAS = 110000
    GNT_TRANSFER_GAS = 55000

    def __init__(self, client: Client):
        self._client = client
        self._gntw = abi.ContractTranslator(
            json.loads(contracts.GolemNetworkTokenWrapped.ABI))
        self._gnt = abi.ContractTranslator(
            json.loads(contracts.GolemNetworkToken.ABI))
        self._faucet = abi.ContractTranslator(json.loads(contracts.Faucet.ABI))
        self.GNTW_ADDRESS = contracts.GolemNetworkTokenWrapped.ADDRESS
        self.TESTGNT_ADDRESS = contracts.GolemNetworkToken.ADDRESS
        self.FAUCET_ADDRESS = contracts.Faucet.ADDRESS
        self._deposit_address = None
        self._deposit_address_created = False
        self._process_deposit_tx = None

    def get_gnt_balance(self, addr: str) -> Optional[int]:
        return self._get_balance(self._gnt, self.TESTGNT_ADDRESS, addr)

    def get_gntw_balance(self, addr: str) -> Optional[int]:
        return self._get_balance(self._gntw, self.GNTW_ADDRESS, addr)

    def get_balance(self, addr: str) -> int:
        gnt_balance = self.get_gnt_balance(addr)
        if gnt_balance is None:
            return None

        gntw_balance = self.get_gntw_balance(addr)
        if gntw_balance is None:
            return None

        return gnt_balance + gntw_balance

    def request_from_faucet(self, privkey: bytes) -> None:
        data = self._faucet.encode_function_call('create', [])
        self._send_transaction(privkey, self.FAUCET_ADDRESS, data, 90000)

    def batch_transfer(self,
                       privkey: bytes,
                       payments,
                       closure_time: int) -> Transaction:
        """
        Takes a list of payments to be made and returns prepared transaction
        for the batch payment. The transaction is not sent, but it is signed.
        It may return None when it's unable to make transaction at the moment,
        but this shouldn't be treated as an error. In case of GNTW sometimes
        we need to do some preparations (like convertion from GNT) before
        we can make a batch transfer.
        """
        if self._process_deposit_tx:
            hstr = encode_hex(self._process_deposit_tx)
            receipt = self._client.get_transaction_receipt(hstr)
            if not receipt:
                logger.info("Waiting to process deposit")
                return None
            self._process_deposit_tx = None

        addr = encode_hex(keys.privtoaddr(privkey))
        gntw_balance = self._get_balance(self._gntw, self.GNTW_ADDRESS, addr)
        if gntw_balance is None:
            return None
        total_value = sum([p.value for p in payments])
        if gntw_balance < total_value:
            logger.info("Not enough GNTW, trying to convert GNT. "
                        "GNTW: {}, total_value: {}"
                        .format(gntw_balance, total_value))
            self._convert_gnt(privkey)
            return None

        p = encode_payments(payments)
        data = self._gntw.encode_function_call('batchTransfer',
                                               [p, closure_time])
        gas = self.GAS_BATCH_PAYMENT_BASE + len(p) * self.GAS_PER_PAYMENT
        return self._create_transaction(addr, self.GNTW_ADDRESS, data, gas)

    def _get_balance(self, token_abi, token_address: str, addr: str) -> int:
        data = token_abi.encode_function_call('balanceOf', [decode_hex(addr)])
        r = self._client.call(
            _from=addr,
            to=token_address,
            data=encode_hex(data),
            block='pending')
        if r is None:
            return None
        return 0 if r == '0x' else int(r, 16)

    def _create_transaction(self,
                            sender: str,
                            token_address: str,
                            data,
                            gas: int) -> Transaction:
        nonce = self._client.get_transaction_count(sender)
        tx = Transaction(nonce,
                         self.GAS_PRICE,
                         gas,
                         to=decode_hex(token_address),
                         value=0,
                         data=data)
        return tx

    def _send_transaction(self,
                          privkey: bytes,
                          token_address: str,
                          data,
                          gas: int) -> Transaction:
        tx = self._create_transaction(
            encode_hex(keys.privtoaddr(privkey)),
            token_address,
            data,
            gas)
        tx.sign(privkey)
        self._client.send(tx)
        return tx

    def _get_deposit_address(self, privkey: bytes) -> bytes:
        if not self._deposit_address:
            addr_raw = keys.privtoaddr(privkey)
            data = self._gntw.encode_function_call(
                'getPersonalDepositAddress',
                [addr_raw])
            res = self._client.call(_from=encode_hex(addr_raw),
                                    to=self.GNTW_ADDRESS,
                                    data=encode_hex(data),
                                    block='pending')
            if int(res, 16) != 0:
                self._deposit_address = decode_hex(res)[-20:]
            elif not self._deposit_address_created:
                data = self._gntw.encode_function_call(
                    'createPersonalDepositAddress',
                    [])
                tx = self._send_transaction(privkey,
                                            self.GNTW_ADDRESS,
                                            data,
                                            self.CREATE_PERSONAL_DEPOSIT_GAS)
                logger.info("Create personal deposit address tx: {}"
                            .format(encode_hex(tx.hash)))
                self._deposit_address_created = True
        return self._deposit_address

    def _convert_gnt(self, privkey: bytes) -> None:
        gnt_balance = self._get_balance(
            self._gnt,
            self.TESTGNT_ADDRESS,
            encode_hex(keys.privtoaddr(privkey)))
        if gnt_balance is None:
            return

        logger.info("Converting {} GNT to GNTW".format(gnt_balance))
        pda = self._get_deposit_address(privkey)
        if not pda:
            logger.info("Not converting until deposit address is known")
            return

        data = self._gnt.encode_function_call(
            'transfer',
            [self._deposit_address, gnt_balance])
        tx = self._send_transaction(privkey,
                                    self.TESTGNT_ADDRESS,
                                    data,
                                    self.GNT_TRANSFER_GAS)
        logger.info("Transfer GNT to personal deposit tx: {}"
                    .format(encode_hex(tx.hash)))

        data = self._gntw.encode_function_call('processDeposit', [])
        tx = self._send_transaction(privkey,
                                    self.GNTW_ADDRESS,
                                    data,
                                    self.PROCESS_DEPOSIT_GAS)
        self._process_deposit_tx = tx.hash
        logger.info("Process deposit tx: {}".format(encode_hex(tx.hash)))
