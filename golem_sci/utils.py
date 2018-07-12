from ethereum.utils import privtoaddr
from eth_utils import encode_hex, to_checksum_address


def privkey_to_checksum_address(privkey: bytes) -> str:
    try:
        return to_checksum_address(encode_hex(privtoaddr(privkey)))
    except AssertionError:
        raise ValueError("not a valid private key")
