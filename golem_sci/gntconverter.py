from typing import Optional
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

        # It may happen that we are in the middle of unfinished conversion
        # so we should pick it up and finalize
        self._update_gate_address()
        if self._gate_address is not None:
            gate_balance = self._sci.get_gnt_balance(self._gate_address)
            if gate_balance:
                logger.info(
                    "Gate has %f GNT, finishing previoiusly started conversion",
                    gate_balance / denoms.ether,
                )
                self._ongoing_conversion = True
                self._transfer_from_gate()

    def convert(self, amount: int):
        if self.is_converting():
            # This isn't a technical restriction but rather a simplification
            # for our use case
            raise Exception('Can process only single conversion at once')

        self._ongoing_conversion = True

        self._ensure_gate(amount)

    def is_converting(self) -> bool:
        return self._ongoing_conversion

    def _update_gate_address(self) -> None:
        if self._gate_address is not None:
            return
        self._gate_address = self._sci.get_gate_address()
        if self._gate_address and int(self._gate_address, 16) == 0:
            self._gate_address = None

    def _ensure_gate(self, amount: int) -> None:
        # First step is opening the gate if it's not already opened
        self._update_gate_address()
        if self._gate_address is None:
            tx_hash = self._sci.open_gate()
            logger.info('Opening gate %s', tx_hash)
            self._sci.on_transaction_confirmed(
                tx_hash,
                self.REQUIRED_CONFS,
                lambda _: self._ensure_gate(amount),
            )
            return

        self._transfer_to_gate(amount)

    def _transfer_to_gate(self, amount: int) -> None:
        # Second step is to transfer the desired amount of GNT to the gate
        tx_hash = self._sci.transfer_gnt(
            self._gate_address,
            amount,
        )
        logger.info(
            'Transfering %f GNT to the gate %s',
            amount / denoms.ether,
            tx_hash,
        )
        self._sci.on_transaction_confirmed(
            tx_hash,
            self.REQUIRED_CONFS,
            lambda _: self._transfer_from_gate(),
        )

    def _transfer_from_gate(self) -> None:
        # Last step is to transfer GNT from the gate to GNTB contract
        tx_hash = self._sci.transfer_from_gate()
        logger.info('Transfering GNT from the gate %s', tx_hash)
        self._sci.on_transaction_confirmed(
            tx_hash,
            self.REQUIRED_CONFS,
            lambda _: self._conversion_finalized(),
        )

    def _conversion_finalized(self) -> None:
        self._ongoing_conversion = False
        logger.info('Conversion has been finalized')
