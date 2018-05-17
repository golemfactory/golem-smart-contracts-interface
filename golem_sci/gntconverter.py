from typing import Callable, Optional
import logging

from ethereum.utils import denoms

from .interface import SmartContractsInterface

logger = logging.getLogger("golem_sci.gnt_converter")


class GNTConverter:
    REQUIRED_CONFS = 2

    def __init__(self, sci: SmartContractsInterface):
        self._sci = sci
        self._gate_address: Optional[str] = None
        self._ongoing_conversion: bool = False
        self._amount_to_convert = 0
        self._cb: Optional[Callable[[], None]] = None

        # It may happen that we are in the middle of unfinished conversion
        # so we should pick it up and finalize
        self._update_gate_address()
        if self._gate_address is not None:
            gate_balance = self._sci.get_gnt_balance(self._gate_address)
            if gate_balance:
                logger.info(
                    "Gate has %f GNT, finishing previously started conversion",
                    gate_balance / denoms.ether,
                )
                self._ongoing_conversion = True
                self._transfer_from_gate()

    def convert(
            self,
            amount: int,
            cb: Optional[Callable[[], None]] = None) -> None:
        if self.is_converting():
            # This isn't a technical restriction but rather a simplification
            # for our use case
            raise Exception('Can process only single conversion at once')

        self._ongoing_conversion = True
        self._cb = cb
        self._amount_to_convert = amount

        self._process()

    def is_converting(self) -> bool:
        return self._ongoing_conversion

    def get_gate_balance(self) -> int:
        if not self.is_converting():
            return 0
        if not self._gate_address:
            return 0
        return self._sci.get_gnt_balance(self._gate_address)

    def _process(self) -> None:
        try:
            self._update_gate_address()

            if self._amount_to_convert > 0:
                # First step is to open the gate if it doesn't exist already
                if self._gate_address is None:
                    self._ensure_gate()
                    return
                # Next step is to transfer GNT to the gate
                self._transfer_to_gate()
                return

            # Last step is to transfer GNT from the gate, finalizing conversion
            if self.get_gate_balance() > 0:
                self._transfer_from_gate()
            else:
                self._conversion_finalized()
        except Exception:
            self._ongoing_conversion = False
            raise

    def _update_gate_address(self) -> None:
        if self._gate_address is not None:
            return
        self._gate_address = self._sci.get_gate_address()
        if self._gate_address and int(self._gate_address, 16) == 0:
            self._gate_address = None

    def _ensure_gate(self) -> None:
        tx_hash = self._sci.open_gate()
        logger.info('Opening gate %s', tx_hash)
        self._sci.on_transaction_confirmed(
            tx_hash,
            self.REQUIRED_CONFS,
            lambda _: self._process(),
        )

    def _transfer_to_gate(self) -> None:
        tx_hash = self._sci.transfer_gnt(
            self._gate_address,
            self._amount_to_convert,
        )
        logger.info(
            'Transfering %f GNT to the gate %s',
            self._amount_to_convert / denoms.ether,
            tx_hash,
        )

        def on_confirmed(receipt):
            if receipt.status:
                self._amount_to_convert = 0
            self._process()
        self._sci.on_transaction_confirmed(
            tx_hash,
            self.REQUIRED_CONFS,
            on_confirmed,
        )

    def _transfer_from_gate(self) -> None:
        tx_hash = self._sci.transfer_from_gate()
        logger.info('Transfering GNT from the gate %s', tx_hash)
        self._sci.on_transaction_confirmed(
            tx_hash,
            self.REQUIRED_CONFS,
            lambda _: self._process(),
        )

    def _conversion_finalized(self) -> None:
        logger.info('Conversion has been finalized')
        self._ongoing_conversion = False
        if self._cb:
            self._cb()
            self._cb = None
