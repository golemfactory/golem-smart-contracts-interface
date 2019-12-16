import functools


# web3 just throws ValueError(response['error']) and this is the best we can
# do to check whether this is coming from there
def _is_jsonrpc_error(e: Exception) -> bool:
    if not isinstance(e, ValueError):
        return False
    if len(e.args) != 1:
        return False
    arg = e.args[0]
    if not isinstance(arg, dict):
        return False
    return len(arg) == 2 and 'message' in arg and 'code' in arg


def map_geth_error(e: Exception) -> Exception:
    if not _is_jsonrpc_error(e):
        return e
    message = e.args[0]['message']
    code = e.args[0]['code']
    error_class = GethError
    for key in _MESSAGE_MAP:
        if message.startswith(key):
            error_class = _MESSAGE_MAP[key]
            break
    return error_class(*e.args, code=code, message=message)


def errorize():
    def wrapped(f):
        @functools.wraps(f)
        def curry(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except ValueError as e:
                mapped = map_geth_error(e)
                if mapped is e:
                    raise
                raise mapped from e
        return curry
    return wrapped


class GethError(Exception):
    def __init__(self, *args, code, message, **kwargs):
        self.code = code
        self.message = message
        super().__init__(*args, **kwargs)

    def __str__(self):
        return self.message


class MissingTrieNode(GethError):
    pass


class KnownTransaction(GethError):
    pass


class NonceTooLow(GethError):
    pass


class FilterNotFound(GethError):
    pass


_MESSAGE_MAP = {
    'missing trie node': MissingTrieNode,
    'known transaction': KnownTransaction,
    'nonce too low': NonceTooLow,
    'filter not found': FilterNotFound,
}
