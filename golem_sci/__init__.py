def _check_secp256k1_recovery():
    """
    secp256k1 library has optional "ECDSA pubkey recovery module", which is
    not built by default (requires ./configure --enable-module-recovery).

    secp256k1-py python module in setup.py searches for the secp256k1 library
    and uses it. If it's not installed, it builds one by itself, with pubkey
    recovery module enabled.

    Ethereum python module requires recovery module enabled in secp256k1-py.
    """

    import secp256k1
    if not secp256k1.HAS_RECOVERABLE:
        raise NotImplementedError(
            "secp256k1 is built without recovery module. "
            "See https://github.com/golemfactory/golem/issues/2168")


_check_secp256k1_recovery()

from .interface import SmartContractsInterface  # noqa

from .factory import (  # noqa
    new_sci,
    new_sci_ipc,
    new_sci_rpc,
)

from .gntconverter import GNTConverter  # noqa

from .structs import (  # noqa
    Block,
    Payment,
    TransactionReceipt,
)

from .events import (  # noqa
    BatchTransferEvent,
    ForcedPaymentEvent,
    ForcedSubtaskPaymentEvent,
    CoverAdditionalVerificationEvent,
)
